// UI preview with a mocked backend: no DCR, FAQ API, tunnel or OpenAI needed.
//
//   cd demo-ui && npm run build            # builds into ../static/demo
//   node preview/preview.mjs [outDir]      # default outDir: preview/shots
//
// Install with npm ci, then npx playwright install chromium.
// Serves ../static/demo, answers the app's endpoints with the canned replies below, and takes screenshots of
// the FAQ chat (/demo) and the application Help panel (/application) at wide, mid and phone widths.
// Edit MOCKS to try other turn shapes; the shapes match app.py / retrieval_runtime.py / application_runtime.py.
import { chromium } from 'playwright';
import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');            // repo root
const OUT = path.resolve(process.argv[2] || path.join(HERE, 'shots'));
fs.mkdirSync(OUT, { recursive: true });

const FAQ_ANSWER = {
  faq_id: 'FAQ_21', question: 'Which documentation do I need to attach with my application to meet the minimum requirements?',
  html: '<p>The documentation you attach must, as a minimum, include records from your GP, a specialist doctor, a hospital or an outpatient clinic.</p><p>It must describe your permanent impairment and be current for it.</p>',
  citation: 'Vejledning nr 9577, Section 4.1'
};
const FIELD = {
  id: 'Form0:Plan_work_studies', label: 'Do you plan to work besides your studies?', type: 'choice',
  options: [{ label: 'Yes', value: 'true' }, { label: 'No', value: 'false' }],
  help: {
    topic: 'impairment_and_work_capacity',
    html: '<p>Whether you plan to take paid work alongside your studies. The supplement is for students whose impairment very significantly limits their ability to take paid work while studying, so planned work is part of the assessment.</p><ul><li><strong>Yes</strong>: You plan paid work of any amount. You will be asked how many hours.</li><li><strong>No</strong>: You do not plan paid work alongside your studies.</li></ul>',
    related: [
      { id: 'FAQ_16', question: 'How much work capacity typically counts against getting the supplement?' },
      { id: 'FAQ_38', question: "How does receiving handicaptillæg affect how much I'm allowed to earn on the side (fribeløb)?" },
      { id: 'FAQ_P09', question: 'May I do voluntary work?' }]
  }
};
const VIEW = { application: true, status: 'question', field: FIELD, prompt_id: 'p1',
  answers: [{ id: 'Form0:Email', label: 'Email', value: 'test@example.dk' }], form: [] };
const NEXT = { ...VIEW, prompt_id: 'p3', field: {
  id: 'Form0:A16', label: 'How many hours a week do you plan to work?', type: 'float',
  help: { topic: 'payment_work_and_changes', html: '<p>Your planned weekly hours of paid work during term time.</p>',
    related: [{ id: 'FAQ_16', question: 'How much work capacity typically counts against getting the supplement?' }] } },
  answers: [...VIEW.answers, { id: FIELD.id, label: FIELD.label, value: 'Yes', raw: 'true', type: 'choice', options: FIELD.options }] };
const ANSWERED = { ...VIEW, prompt_id: 'p2', answered: true, faq_id: 'FAQ_16',
  faq_question: 'How much work capacity typically counts against getting the supplement?',
  faq_response: '<p>As a starting point, if you are able to work around 5-6 hours a week during term time, you are not considered entitled.</p>',
  faq_citation: 'Vejledning nr 9577, Section 3.4.4' };

const MOCKS = {
  '/init': { faq: true, retrieval: true, status: 'welcome',
    response: "<p>Hi, I'm here to help with questions about handicaptillæg, the SU disability supplement for students in Denmark.</p><p>I can answer questions about who can get it, your impairment and ability to work, medical documentation, how to apply, and payments. Type your question in your own words, or pick one of the examples below.</p><p>I cannot assess your own case, give medical advice, or answer questions about other benefits. I am still learning, so I may sometimes get a question wrong.</p>",
    examples: [{ id: 'FAQ_01', question: 'What is handicaptillæg and who is it for?' },
               { id: 'FAQ_21', question: 'Which documentation do I need to attach with my application to meet the minimum requirements?' },
               { id: 'FAQ_P01', question: 'How do I apply?' }] },
  // /chat: an answer for questions and examples; the goodbye for {action: 'end'} (idle timeout);
  // a Confirm for a message containing "confirm", a related offer for "related" (spec 01 turn shapes)
  // "person" gives the handover reply of reason 1; "nothing" a miss that carries the handover block (reason 2).
  '/chat': (body) => /person/.test(body.message || '')
    ? { faq: true, retrieval: true, status: 'handover', response: '',
        handover: { reason: 1, html: '<p>A person can help you better with this.</p><p>For questions about your own case, use the contact options and opening hours published on SU.dk.</p>' } }
    : /nothing/.test(body.message || '')
      ? { faq: true, retrieval: true, status: 'no_match', response: '<p>I could not find an answer to that in the FAQ.</p>',
          actions: [{ action: 'rephrase', label: 'Rephrase my question' }],
          handover: { reason: 2, html: '<p>For questions about your own case, use the contact options and opening hours published on SU.dk.</p>' } }
    : body.action === 'end'
    ? { faq: true, retrieval: true, status: 'ended', response: '<p>Thank you for your questions. You can come back and ask another question at any time.</p>' }
    : /confirm/.test(body.message || '')
      ? { faq: true, retrieval: true, status: 'confirm', response: 'Is this what you are asking?',
          prompt: { id: 'c1', kind: 'confirm', text: 'Can I appeal a decision about handicaptillæg?',
            options: [{ value: 'FAQ_41', label: 'Yes, show the answer' }, { value: 'none', label: 'No, that is not it' }] } }
      : /related/.test(body.message || '')
        ? { faq: true, retrieval: true, status: 'options', related: true,
            response: 'No FAQ answers exactly this. This one is on the same topic and may help:',
            prompt: { id: 'r1', kind: 'options', text: 'Which of these is closest to your question?',
              options: [{ value: 'FAQ_P08', label: 'How long will processing take?' }, { value: 'none', label: 'None of these' }] } }
        : body.action === 'reply' && body.value === 'none'
          ? { faq: true, retrieval: true, status: 'rephrase', response: 'Could you rephrase your question? A few more words about your situation help.' }
          : { faq: true, retrieval: true, status: 'answer', response: '', answer: FAQ_ANSWER },
  '/application/init': VIEW,
  // a suggested question (related) or a single match is answered directly; a typed question here gets options
  // Spec 01 shapes: a message containing "confirm" or "hours a week" (a statement) gets a Confirm, "related" gets a
  // related offer; any other typed question gets options.
  '/application/ask': (body) => body.related ? ANSWERED
    : /weather/.test(body.message || '') ? { application: true, status: 'faq_out_of_scope', response: 'That is outside what I can help with. I answer questions about handicaptillæg.' }
    : /determination/.test(body.message || '') ? { ...ANSWERED, follow_up: 'One more question so the answer fits your situation (you can skip it):',
      prompt: { id: 'd1', kind: 'determination', text: 'Have you already received a decision on your application?',
        options: [{ value: 'true', label: 'Yes' }, { value: 'false', label: 'No' }] } }
    : /confirm|hours a week/.test(body.message || '') ? { application: true, status: 'faq_confirm', match_id: 'm2',
      response: 'Is this what you are asking?', candidates: [{ candidate_key: 'FAQ_P08', question: 'How long will processing take?' }] }
    : /related/.test(body.message || '') ? { application: true, status: 'faq_related', related: true, match_id: 'm3',
      response: 'No FAQ answers exactly this. This one is on the same topic and may help:',
      candidates: [{ candidate_key: 'FAQ_P08', question: 'How long will processing take?' }] }
    : { application: true, status: 'faq_clarify', match_id: 'm1',
    response: 'I found a few questions that may fit. Which one is closest?',
    searched_for: 'Does planning a few hours of student work count against me?',
    candidates: [{ candidate_key: 'FAQ_16', question: 'How much work capacity typically counts against getting the supplement?' },
                 { candidate_key: 'FAQ_P09', question: 'May I do voluntary work?' }] },
  '/application/confirm': (body) => body.candidate_key === 'none'
    ? { application: true, status: 'faq_none', response: 'Try asking in other words, for example with the situation you are in.' }
    : ANSWERED,
  // The panel's follow-up determination (spec 03): the outcome texts DCR makes pending, and the answer given
  '/application/determination': { faq: true, retrieval: true, application: true, status: 'determination_result', response: '',
    outcomes: ['<p>If you have received a decision, you have four weeks from the date on it to appeal.</p>'],
    answered: { question: 'Have you already received a decision on your application?', value: 'Yes' } },
  '/application/answer': NEXT,
  '/application/handover': { application: true, status: 'handover', response: '',
    handover: { reason: 1, html: '<p>A person can help you better with this.</p><p>For questions about your own case, use the contact options and opening hours published on SU.dk.</p>' } }
};

const TYPES = { '.js': 'text/javascript', '.css': 'text/css', '.gif': 'image/gif', '.svg': 'image/svg+xml', '.png': 'image/png' };
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  if (req.method === 'POST' && MOCKS[url.pathname]) {
    let raw = '';
    req.on('data', chunk => { raw += chunk; });
    req.on('end', () => {
      const mock = MOCKS[url.pathname];
      const reply = typeof mock === 'function' ? mock(JSON.parse(raw || '{}')) : mock;
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(reply));
    });
    return;
  }
  const file = url.pathname.startsWith('/static/') ? path.join(ROOT, url.pathname) : path.join(ROOT, 'static/demo/index.html');
  try {
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'text/html' });
    res.end(fs.readFileSync(file));
  } catch { res.writeHead(404); res.end(); }
}).listen(0);
const base = `http://localhost:${server.address().port}`;

const WIDTHS = [[1440, 900, 'wide'], [1024, 800, 'mid'], [390, 844, 'phone']];
const browser = await chromium.launch();
for (const [width, height, name] of WIDTHS) {
  const page = await browser.newPage({ viewport: { width, height } });
  await page.route('**/fonts.googleapis.com/**', r => r.abort());
  page.on('pageerror', e => { console.log(`PAGE ERROR (${name}):`, e.message); process.exitCode = 1; });    // 5.6: no console error
  page.on('console', m => { if (m.type() === 'error' && !/fonts|ERR_FAILED/.test(m.text())) console.log(`CONSOLE ERROR (${name}):`, m.text()); });
  const shot = (step) => page.screenshot({ path: path.join(OUT, `${name}-${step}.png`) });

  // FAQ chat (the clock is installed so the idle timeout can be fast-forwarded)
  await page.clock.install();
  await page.goto(`${base}/demo?graphid=1`);
  await page.getByLabel('Open SU-support').click();
  await page.waitForTimeout(400); await shot('faq-1-welcome');
  await page.getByRole('button', { name: 'What is handicaptillæg and who is it for?' }).click();
  await page.waitForTimeout(400); await shot('faq-2-answer');
  await page.getByLabel('Message SU-support').fill('please confirm');
  await page.getByRole('button', { name: 'Send message' }).click();
  await page.waitForTimeout(400); await shot('faq-2b-confirm');           // the matched question and the two buttons
  await page.getByRole('button', { name: 'No, that is not it' }).click();
  await page.waitForTimeout(400); await shot('faq-2c-rephrase');
  await page.getByLabel('Message SU-support').fill('I found nothing useful');
  await page.getByRole('button', { name: 'Send message' }).click();
  await page.waitForTimeout(400); await shot('faq-2d-miss-with-handover');    // the amber handover block under the reply
  await page.getByLabel('Message SU-support').fill('can I talk to a person');
  await page.getByRole('button', { name: 'Send message' }).click();
  await page.waitForTimeout(400); await shot('faq-2e-person-request');
  await page.clock.runFor(121000);
  await page.waitForTimeout(400); await shot('faq-3-idle-ended');

  // Application + Help panel
  await page.goto(`${base}/application?graphid=1`);
  await page.evaluate(() => sessionStorage.setItem('application-demo-continue', 'yes'));
  await page.reload();
  await page.getByRole('button', { name: 'Start the application' }).click();
  await page.waitForTimeout(300); await shot('app-1-field');
  // wide screens open the panel with the question as context; phones open it from the link
  const about = page.getByRole('button', { name: 'Ask SU-support about this question' });
  if (await about.count()) await about.click();
  await page.waitForTimeout(300); await shot('app-2-help-card');
  await page.getByRole('button', { name: 'May I do voluntary work?' }).click();
  await page.waitForTimeout(300); await shot('app-3-related-answer');
  await page.getByLabel('Your question').fill('what if I only work a little?');
  await page.getByRole('button', { name: 'Send question' }).click();
  await page.waitForTimeout(300); await shot('app-4-options');
  await page.locator('.hp-match .hp-card').first().click();
  await page.waitForTimeout(300); await shot('app-5-answer');
  await page.getByLabel('Your question').fill('can you confirm how this works');
  await page.getByRole('button', { name: 'Send question' }).click();
  await page.waitForTimeout(300); await shot('app-5b-confirm');           // card, "Yes, show the answer", "No, that is not it"
  await page.getByRole('button', { name: 'Yes, show the answer' }).click();
  await page.waitForTimeout(300);
  await page.getByLabel('Your question').fill('related topic please');
  await page.getByRole('button', { name: 'Send question' }).click();
  await page.waitForTimeout(300); await shot('app-5c-related');           // the related offer text
  await page.getByRole('button', { name: 'No, that is not it' }).click();
  await page.waitForTimeout(300);
  await page.getByLabel('Your question').fill('what is the weather like');
  await page.getByRole('button', { name: 'Send question' }).click();
  await page.waitForTimeout(300); await shot('app-5d-out-of-scope');          // a notice, no search
  await page.getByLabel('Your question').fill('determination please');
  await page.getByRole('button', { name: 'Send question' }).click();
  await page.waitForTimeout(300); await shot('app-5e-determination-prompt');  // the answer, then the follow-up question
  await page.locator('.hp-followup').getByRole('button', { name: 'Yes', exact: true }).click();
  await page.waitForTimeout(300); await shot('app-5f-determination-result');
  await page.getByRole('button', { name: 'Talk to a person' }).click();
  await page.waitForTimeout(300); await shot('app-6-handover');
  if (width > 860) {   // on phones the sheet covers the form
    await page.getByRole('button', { name: 'Hide Ask SU-support' }).click();
    await page.locator('.ap-choice').first().click();
    await page.waitForTimeout(300); await shot('app-7-next-question');
    await page.getByRole('button', { name: 'Change answer: Yes' }).click();
    await page.waitForTimeout(300); await shot('app-8-previous-question');
  }
  await page.close();
}
await browser.close();
server.close();
console.log(`screenshots in ${OUT}`);
