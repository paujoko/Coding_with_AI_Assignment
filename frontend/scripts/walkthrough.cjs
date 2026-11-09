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
  await snap('01-start', false);
  // Attach a brief on the start page, as a developer with a written spec would.
  const brief = require('path').join(out, 'brief.md');
  require('fs').writeFileSync(brief, '# Brief\nA to-do app for a team. Tasks have a title, a due date and someone assigned.\n');
  await p.setInputFiles('.home input[type=file]', brief);
  await p.fill('.home textarea', 'A small to-do app for a team. Tasks have a title, a due date and someone assigned.');
  await snap('01b-start-with-file', false);
  await p.click('.home button.send');
  await p.waitForTimeout(1500);
  await snap('02-questions', false);
  const qs = p.locator('.question');
  for (let i = 0; i < await qs.count(); i++) await qs.nth(i).locator('.option').first().click();
  await snap('03-answers-picked', false);
  await p.click('.composer button[type=submit]');
  await p.waitForTimeout(1500);
  await snap('04-requirements', false);
  await p.click('.next button:has-text("Approve")');
  await p.waitForTimeout(600);
  await snap('04b-approved', false);
  await p.click('.next button:has-text("Go to")');
  await p.waitForTimeout(600);
  await snap('04c-design-empty', false);
  // Drag a file over the page: the drop overlay appears.
  await p.evaluate(() => {
    const dt = new DataTransfer();
    dt.items.add(new File(['notes'], 'notes.md', { type: 'text/markdown' }));
    window.dispatchEvent(new DragEvent('dragenter', { dataTransfer: dt }));
  });
  await snap('04d-dropzone', false);
  await p.evaluate(() => {
    const dt = new DataTransfer();
    dt.items.add(new File(['Use a layered design.'], 'notes.md', { type: 'text/markdown' }));
    window.dispatchEvent(new DragEvent('drop', { dataTransfer: dt }));
  });
  await p.waitForTimeout(800);
  await snap('04e-design-file-attached', false);
  await p.click('.composer button[type=submit]');
  await p.waitForTimeout(5000);
  await snap('05-design', false);
  await p.click('.side-nav button:has-text("How it works")');
  await snap('05c-help', false);
  await p.keyboard.press('Escape');
  await p.click('.side-nav button:has-text("Traceability")');
  await snap('06-trace', false);
  await p.click('.side-nav button:has-text("Activity")');
  await snap('07-activity', false);
  // Change scenario: revise the requirements, the design goes out of date.
  await p.locator('.step').nth(0).click();
  await p.waitForTimeout(500);
  await p.click('.next button:has-text("Reopen")');
  await p.waitForTimeout(500);
  await p.locator('.composer-actions button:has-text("Revise")').click();
  await p.fill('.composer textarea', 'Add tags to tasks');
  await p.click('.composer button[type=submit]');
  await p.waitForTimeout(1500);
  await p.locator('.step').nth(1).click();
  await snap('08-stale', false);
  await p.locator('.step').nth(4).click();
  await snap('09-planned', false);
  await p.setViewportSize({ width: 390, height: 844 });
  await p.locator('.step').nth(0).click();
  await snap('10-mobile-chat', false);
  await p.click('.pane-switch button:has-text("Results")');
  await snap('11-mobile-results', false);
  await b.close();
})();
