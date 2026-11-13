// Mock backend server for browsing the built UI by hand: node preview/serve.mjs, then open http://localhost:4173/demo or /application
// UI preview with a mocked backend: no DCR, FAQ API, tunnel or OpenAI needed.
//
//   cd demo-ui && npm run build            # builds into ../static/demo
//   node preview/preview.mjs [outDir]      # default outDir: preview/shots
//
// Needs Playwright (npm i --no-save playwright; on macOS also `npx playwright install chromium`).
// Serves ../static/demo, answers the app's endpoints with the canned replies below, and takes screenshots of
// the FAQ chat (/demo) and the application Help panel (/application) at wide, mid and phone widths.
// Edit MOCKS to try other turn shapes; the shapes match app.py / retrieval_runtime.py / application_runtime.py.
import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');            // repo root
const _OUT = path.resolve(process.argv[2] || path.join(HERE, 'shots'));


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

const MOCKS = {
  '/init': { faq: true, retrieval: true, status: 'welcome',
    response: "<p>Hi, I'm here to help with questions about handicaptillæg, the SU disability supplement for students in Denmark.</p><p>I can answer questions about who can get it, your impairment and ability to work, medical documentation, how to apply, and payments. Type your question in your own words, or pick one of the examples below.</p><p>I cannot assess your own case, give medical advice, or answer questions about other benefits. I am still learning, so I may sometimes get a question wrong.</p>",
    examples: [{ id: 'FAQ_01', question: 'What is handicaptillæg and who is it for?' },
               { id: 'FAQ_21', question: 'Which documentation do I need to attach with my application to meet the minimum requirements?' },
               { id: 'FAQ_P01', question: 'How do I apply?' }] },
  // /chat: an answer for questions and examples; the goodbye for {action: 'end'} (idle timeout)
  '/chat': (body) => body.action === 'end'
    ? { faq: true, retrieval: true, status: 'ended', response: '<p>Thank you for your questions. You can come back and ask another question at any time.</p>' }
    : { faq: true, retrieval: true, status: 'answer', response: '', answer: FAQ_ANSWER },
  '/application/init': VIEW,
  '/application/ask': { application: true, status: 'faq_clarify', match_id: 'm1',
    response: 'I found a few questions that may fit. Which one is closest?',
    searched_for: 'Do you plan to work besides your studies? what do I put here?',
    candidates: [{ candidate_key: 'FAQ_16', question: 'How much work capacity typically counts against getting the supplement?' },
                 { candidate_key: 'FAQ_P09', question: 'May I do voluntary work?' }] },
  '/application/confirm': { ...VIEW, prompt_id: 'p2', faq_id: 'FAQ_16',
    faq_question: 'How much work capacity typically counts against getting the supplement?',
    faq_response: '<p>As a starting point, if you are able to work around 5-6 hours a week during term time, you are not considered entitled.</p>',
    faq_citation: 'Vejledning nr 9577, Section 3.4.4' },
  '/application/handover': { application: true, status: 'handover', response: '',
    handover: { reason: 1, html: '<p>A person can help you better with this.</p><p>For questions about your own case, use the contact options and opening hours published on SU.dk.</p>' } }
};

const TYPES = { '.js': 'text/javascript', '.css': 'text/css', '.gif': 'image/gif', '.svg': 'image/svg+xml', '.png': 'image/png' };
http.createServer((req, res) => {
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
}).listen(4173);
console.log('http://localhost:4173');
