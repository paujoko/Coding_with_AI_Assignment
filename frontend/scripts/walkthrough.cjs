// Browser walkthrough on the scripted mock: P1 questions, requirements, design, trace, activity,
// the change scenario (revise requirements -> design out of date) and a phone-width view.
// Needs a fresh backend workspace and both servers running. Usage (from frontend/):
//   node scripts/walkthrough.cjs <screenshot-folder> [light|dark]
// Playwright must be installed (npm i -D playwright, or a global install).
const { chromium } = require('playwright');
const out = process.argv[2];
const scheme = process.argv[3] || 'light';
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: scheme });
  const p = await ctx.newPage();
  p.on('pageerror', e => console.log('PAGEERROR', e.message));
  p.on('console', m => { if (m.type() === 'error') console.log('CONSOLE', m.text()); });
  const snap = async (n, full = true) => { await p.waitForTimeout(400); await p.screenshot({ path: `${out}/${n}.png`, fullPage: full }); };
  await p.goto('http://localhost:5190');
  await snap('01-start');
  await p.fill('input[placeholder="Team to-do list"]', 'Team to-do list');
  await p.fill('textarea', 'A small to-do app for a team. Tasks have a title, a due date and someone assigned.');
  await p.click('button:has-text("Create and start")');
  await p.waitForTimeout(1500);
  await snap('02-questions', false);
  const qs = p.locator('.question');
  for (let i = 0; i < await qs.count(); i++) await qs.nth(i).locator('.option').first().click();
  await snap('03-answers-picked', false);
  await p.click('.composer button[type=submit]');
  await p.waitForTimeout(1500);
  await snap('04-requirements');
  await p.click('button:has-text("Approve requirements")');
  await p.waitForTimeout(600);
  await p.locator('.station').nth(1).click();
  await p.waitForTimeout(600);
  await p.click('.composer button[type=submit]');
  await p.waitForTimeout(5000);
  await snap('05-design', false);
  await snap('05b-design-full');
  await p.click('.views button:has-text("Traceability")');
  await snap('06-trace');
  await p.click('.views button:has-text("Activity")');
  await snap('07-activity');
  // change requirements -> design out of date
  await p.locator('.station').nth(0).click();
  await p.waitForTimeout(500);
  await p.click('button:has-text("Reopen for changes")');
  await p.waitForTimeout(500);
  await p.locator('.composer-actions button:has-text("Revise")').click();
  await p.fill('.composer textarea', 'Add tags to tasks');
  await p.click('.composer button[type=submit]');
  await p.waitForTimeout(1500);
  await p.locator('.station').nth(1).click();
  await snap('08-stale', false);
  await p.locator('.station').nth(4).click();
  await snap('09-planned', false);
  await p.setViewportSize({ width: 390, height: 844 });
  await p.locator('.station').nth(0).click();
  await snap('10-mobile');
  await b.close();
})();
