// Application thread check with a stateful mock backend: node preview/thread.mjs [outDir]
// Walks a short application (text, single choice, hours, multi choice, yes/no, review) and checks:
//  - a typed plain number is answered directly (no /application/interpret call, no suggestion step)
//  - words on a number question and on a choice question are interpreted and must be confirmed
//  - a single choice is answered by one click
//  - a server error on an answer is shown in the thread and the typed text comes back into the box
//  - an earlier answer can be changed from its bubble
import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { chromium } from 'playwright';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const OUT = path.resolve(process.argv[2] || path.join(HERE, 'shots-thread'));
fs.mkdirSync(OUT, { recursive: true });

const FIELDS = [
  { id: 'Form0:Email', label: 'What is your email address?', type: 'email' },
  { id: 'Form0:Impairment_type', label: 'What kind of impairment do you have?', type: 'choice',
    options: [{ label: 'Physical impairment', value: 'physical' }, { label: 'Mental health condition', value: 'mental' },
              { label: 'Sensory impairment', value: 'sensory' }, { label: 'Other', value: 'other' }],
    help: { html: '<p>Choose the group that fits best.</p>', related: [] } },
  { id: 'Form0:A16', label: 'How many hours a week can you work?', type: 'int', hours: true,
    help: { html: '<p>A whole number between 0 and 168.</p>', related: [] } },
  { id: 'Form0:A14', label: 'Which of these apply to you?', type: 'choice', multiple: true,
    options: [{ label: 'Permanent', value: 'perm' }, { label: 'Very limiting', value: 'lim' }, { label: 'Documented', value: 'doc' }],
    help: { html: '<p>Select all that apply.</p>', related: [] } },
  { id: 'Form0:Plan_work_studies', label: 'Do you plan to work besides your studies?', type: 'bool',
    help: { html: '<p>Paid work alongside studies.</p>', related: [] } }
];

let answers = [];
const calls = { interpret: 0, answer: 0 };
const view = () => {
  const i = answers.length;
  if (i >= FIELDS.length) return { application: true, status: 'review', prompt_id: `p${i}`, answers, form: [] };
  return { application: true, status: 'question', field: FIELDS[i], prompt_id: `p${i}`, answers, form: [] };
};
const label = (f, v) => f.type === 'choice' ? v.split(',').map(x => f.options.find(o => o.value === x)?.label ?? x).join(', ')
  : f.type === 'bool' ? (v === 'true' ? 'Yes' : 'No') : v;
const MOCKS = {
  '/application/init': () => { answers = []; return [200, view()]; },
  '/application/answer': (b) => {
    calls.answer++;
    const f = FIELDS[answers.length];
    if (f.type === 'int' && !(Number(b.value) >= 0 && Number(b.value) <= 168)) return [400, { error: 'Enter a number of hours between 0 and 168.' }];
    if (f.type === 'int' && !/^\d+$/.test(String(b.value))) return [400, { error: 'Enter a whole number of hours.' }];
    answers.push({ id: f.id, label: f.label, value: label(f, String(b.value)), type: f.type, options: f.options, multiple: f.multiple });
    return [200, view()];
  },
  '/application/interpret': (b) => {
    calls.interpret++;
    const f = FIELDS[answers.length];
    if (f.type === 'int') return [200, { application: true, status: 'interpreted', value: '6', display: '6', field_id: f.id, prompt_id: b.prompt_id }];
    return [200, { application: true, status: 'interpreted', value: 'physical', display: 'Physical impairment', field_id: f.id, prompt_id: b.prompt_id }];
  },
  '/application/edit': (b) => {
    const at = answers.findIndex(a => a.id === b.field_id);
    const f = FIELDS[at];
    answers = answers.slice(0, at);
    answers.push({ id: f.id, label: f.label, value: label(f, String(b.value)), type: f.type, options: f.options });
    return [200, view()];
  },
  '/application/ask': () => [200, { application: true, status: 'faq_no_match', response: 'No FAQ answers that.' }]
};
const TYPES = { '.js': 'text/javascript', '.css': 'text/css', '.gif': 'image/gif' };
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  if (req.method === 'POST' && MOCKS[url.pathname]) {
    let raw = ''; req.on('data', c => { raw += c; });
    req.on('end', () => {
      const [code, body] = MOCKS[url.pathname](JSON.parse(raw || '{}'));
      res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(body));
    });
    return;
  }
  const file = url.pathname.startsWith('/static/') ? path.join(ROOT, url.pathname) : path.join(ROOT, 'static/demo/index.html');
  try { res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'text/html' }); res.end(fs.readFileSync(file)); }
  catch { res.writeHead(404); res.end(); }
}).listen(0);
const base = `http://localhost:${server.address().port}`;

const ok = (cond, msg) => { console.log(`${cond ? 'PASS' : 'FAIL'}  ${msg}`); if (!cond) process.exitCode = 1; };
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
for (const [width, height, name] of [[1440, 900, 'wide'], [390, 844, 'phone']]) {
  answers = []; calls.interpret = 0; calls.answer = 0;
  const page = await browser.newPage({ viewport: { width, height } });
  await page.route('**/fonts.googleapis.com/**', r => r.abort());
  page.on('pageerror', e => { console.log(`PAGE ERROR (${name}):`, e.message); process.exitCode = 1; });
  const shot = (s) => page.screenshot({ path: path.join(OUT, `${name}-${s}.png`) });
  await page.goto(`${base}/application?graphid=1`);
  await page.evaluate(() => sessionStorage.setItem('application-demo-continue', 'yes'));
  await page.reload();
  await page.getByRole('button', { name: 'Start the application' }).click();
  await page.waitForTimeout(300);

  // 1 text answer
  await page.getByLabel('What is your email address?').fill('test@example.dk');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await page.waitForTimeout(300);

  // 2 single choice: the own-words box is visible without opening anything
  const box = page.getByLabel('Describe your situation in your own words');
  ok(await box.isVisible(), `${name}: own-words box visible on a choice question`);
  await shot('1-choice');
  // fixed frame: the page itself does not scroll, the message box is at the bottom, the question sits right above it
  const frame = await page.evaluate(() => {
    const dock = document.querySelector('.ap-dock').getBoundingClientRect();
    const _q = document.querySelector('.ap-chat .ap-q:last-of-type');
    const opts = document.querySelector('.ap-choices')?.getBoundingClientRect();
    return { page: document.documentElement.scrollHeight - innerHeight, dockGap: innerHeight - dock.bottom, optsBottom: opts?.bottom, dockTop: dock.top };
  });
  ok(frame.page <= 1, `${name}: page does not scroll (${frame.page}px over)`);
  ok(frame.dockGap < 40, `${name}: message box sits at the bottom (${Math.round(frame.dockGap)}px from the edge)`);
  ok(frame.dockTop - frame.optsBottom < 140, `${name}: options sit close above the message box (${Math.round(frame.dockTop - frame.optsBottom)}px)`);
  await box.fill('it began after a car accident');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await page.waitForTimeout(300); await shot('2-suggestion');
  ok(calls.interpret === 1, `${name}: words on a choice question are interpreted`);
  ok(await page.getByText('Based on what you wrote').isVisible(), `${name}: suggestion needs confirmation`);
  await page.getByRole('button', { name: 'Use this answer' }).click();
  await page.waitForTimeout(300);

  // 3 hours: words are interpreted and confirmed; a plain number is not
  const hoursInput = page.getByLabel('How many hours a week can you work?');
  await hoursInput.fill('about six hours a week');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await page.waitForTimeout(300); await shot('2b-number-words');
  ok(calls.interpret === 2, `${name}: words on a number question are interpreted`);
  ok(await page.getByText('Based on what you wrote').isVisible(), `${name}: number suggestion needs confirmation`);
  await page.getByRole('button', { name: 'Not this' }).click();
  await page.waitForTimeout(200);
  ok((await hoursInput.inputValue()) === 'about six hours a week', `${name}: words come back into the box after Not this`);
  const before = calls.interpret;
  await page.getByLabel('How many hours a week can you work?').fill('500');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await page.waitForTimeout(300); await shot('3-hours-error');
  ok(calls.interpret === before, `${name}: a plain number is not interpreted`);
  ok(await page.getByRole('alert').filter({ hasText: 'between 0 and 168' }).isVisible(), `${name}: range error shown in the thread`);
  ok((await page.getByLabel('How many hours a week can you work?').inputValue()) === '500', `${name}: typed number stays in the box after an error`);
  await page.getByLabel('How many hours a week can you work?').fill('6');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await page.waitForTimeout(300);
  ok(calls.interpret === before, `${name}: valid plain number answered with no interpret call`);
  ok(!(await page.getByText('Based on what you wrote').count()), `${name}: no suggestion step for a plain number`);

  // 4 multi choice: tick, Continue
  await page.getByText('Permanent').click();
  await page.getByText('Documented').click();
  await shot('4-multi');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.waitForTimeout(300);

  // 5 yes/no: one click
  await page.getByRole('button', { name: 'Yes', exact: true }).click();
  await page.waitForTimeout(300); await shot('5-review');
  ok(await page.getByRole('button', { name: 'Send demo application' }).isVisible(), `${name}: review reached`);

  const end = await page.evaluate(() => {
    const chat = document.querySelector('.ap-chat'); const btn = [...document.querySelectorAll('.ap-chat button')].find(b => b.textContent === 'Send demo application').getBoundingClientRect();
    const c = chat.getBoundingClientRect();
    return { page: document.documentElement.scrollHeight - innerHeight, chatScrolls: chat.scrollHeight > chat.clientHeight, newest: btn.bottom <= c.bottom + 1 && btn.top >= c.top };
  });
  ok(end.page <= 1, `${name}: page still does not scroll at review`);
  ok(end.newest, `${name}: newest item is in view without scrolling by hand`);
  const topBtn = await page.getByRole('button', { name: 'Start again' }).boundingBox();
  ok(topBtn && topBtn.y < 120, `${name}: Start again is in the top bar`);

  // change an earlier answer from its bubble
  const editBtn = page.getByRole('button', { name: /Change answer: 6/ });
  const opacity = () => editBtn.evaluate(e => getComputedStyle(e).opacity);
  await page.mouse.move(5, 5);
  const idle = await opacity();
  await page.locator('.ap-a', { hasText: /^6$/ }).hover();
  await page.waitForTimeout(250);
  const hover = await opacity();
  await shot('5b-hover-edit');
  ok(idle === '0' && hover === '1', `${name}: edit icon appears only on hover (idle ${idle}, hover ${hover})`);
  ok((await page.getByRole('button', { name: 'Change', exact: true }).count()) === 0, `${name}: no text Change links`);
  const gap = await page.evaluate(() => { const i = document.querySelector('.ap-inner').getBoundingClientRect(), h = document.querySelector('.hp')?.getBoundingClientRect(); return h ? Math.round(h.left - i.right) : null; });
  if (gap !== null) ok(gap <= 48, `${name}: gap between application column and Ask SU-support is ${gap}px`);
  await editBtn.click();
  await page.waitForTimeout(300); await shot('6-change');
  await page.locator('.edit-form input').fill('12');
  await page.getByRole('button', { name: 'Save change' }).click();
  await page.waitForTimeout(400); await shot('7-after-change');
  ok(await page.locator('.ap-bubble', { hasText: /^12$/ }).count() === 1, `${name}: changed answer shows in the thread`);
  await page.close();
}
await browser.close(); server.close();
