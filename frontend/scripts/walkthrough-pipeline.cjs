// Browser walkthrough of P3 to P7 on the scripted mock. P1 and P2 are done through the API to save time;
// everything after is clicked in the UI: review and apply findings, code, tests (run for real), deployment,
// the consistency check and a change request whose next step opens the requirements with the change filled in.
// Needs both servers running on a fresh workspace. Usage (from frontend/):
//   node scripts/walkthrough-pipeline.cjs <screenshot-folder> [light|dark]
const { chromium } = require('playwright');
const out = process.argv[2];
const scheme = process.argv[3] || 'light';
const API = 'http://localhost:8810/api';
const post = (path, body) =>
  fetch(API + path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body ?? {}) }).then(async (r) => {
    if (!r.ok) throw new Error(`${path}: ${r.status} ${await r.text()}`);
    return r.json();
  });
const act = (pid, phase, action, input = {}) => post(`/projects/${pid}/phases/${phase}/actions/${action}`, { input });

(async () => {
  const project = await post('/projects', { name: 'Team todo' });
  const pid = project.id;
  await act(pid, 'requirements', 'start', { description: 'A small to-do app for a team.' });
  await act(pid, 'requirements', 'answer', { answers: 'Q1: Command line' });
  await post(`/projects/${pid}/phases/requirements/approve`);
  await act(pid, 'design', 'generate');
  await post(`/projects/${pid}/phases/design/approve`);

  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: scheme });
  const p = await ctx.newPage();
  p.on('pageerror', (e) => console.log('PAGEERROR', e.message));
  p.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE', m.text()); });
  const snap = async (n, full = false) => { await p.waitForTimeout(500); await p.screenshot({ path: `${out}/${n}.png`, fullPage: full }); };
  const idle = async () => { await p.waitForTimeout(300); await p.waitForSelector('.msg-working', { state: 'detached', timeout: 60000 }); await p.waitForTimeout(400); };
  const step = async (title) => { await p.click(`.side-steps button:has-text("${title}")`); await p.waitForTimeout(600); };
  const approve = async () => { await p.click('.next button:has-text("Approve")'); await idle(); };

  await p.goto('http://localhost:5190');
  await p.evaluate((id) => localStorage.setItem('wings.project', id), pid);
  await p.goto('http://localhost:5190');
  await p.waitForTimeout(800);
  await step('Design refinement');
  await snap('10-refinement-empty');
  await p.click('.suggestion');
  await idle();
  await snap('11-review');
  await p.click('.doc button:has-text("Apply")');
  await idle();
  await snap('12-refined');
  await approve();

  await step('Code generation');
  await p.click('.suggestion');
  await idle();
  await snap('13-code');
  await p.click('.file-list button:has-text("todo/service.py")');
  await snap('13b-code-service');
  await approve();

  await step('Testing');
  await p.click('.suggestion');
  await idle();
  await snap('14-tests-written');
  await p.click('.msg-next button:has-text("Run tests")');
  await idle();
  await snap('15-tests-run');
  await approve();

  await step('Deployment');
  await p.click('.suggestion');
  await idle();
  await snap('16-deployment');
  await approve();

  await step('Maintenance');
  await snap('17-maintenance-empty');
  await p.click('.composer-actions button:has-text("Check consistency")');
  await p.click('.composer button[type=submit]');
  await idle();
  await snap('18-consistency');
  await p.click('.composer-actions button:has-text("Request a change")');
  await p.fill('.composer textarea', 'Tasks need a priority, and the list should show the most important first.');
  await p.click('.composer button[type=submit]');
  await idle();
  await snap('19-change');
  await p.click('.msg-next button:has-text("Update the requirements")');
  await p.waitForTimeout(800);
  await snap('20-change-prefilled-in-requirements');
  await p.click('.composer button[type=submit]');
  await idle();
  await snap('21-requirements-revised-later-phases-stale');

  await p.click('.side-nav button:has-text("Traceability")');
  await snap('22-trace', true);

  await p.setViewportSize({ width: 390, height: 844 });
  await step('Code generation').catch(() => undefined);
  await p.click('.pane-switch button:has-text("Results")').catch(() => undefined);
  await snap('23-phone-code');
  await b.close();
})().catch((e) => { console.error(e); process.exit(1); });
