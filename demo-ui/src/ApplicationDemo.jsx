import { useState, useRef, useEffect, createElement } from 'react';
import './application.css';
import { newSessionId } from './sessionId';
import Icon from './Icon';
import ThemeToggle from './ThemeToggle';

// FAQ answers arrive as stored HTML. Render basic formatting, never scripts.
function AnswerBody({ html }) {
  const doc = new DOMParser().parseFromString(html || '', 'text/html');
  function render(node, key) {
    if (node.nodeType === 3) return node.textContent;
    if (node.nodeType !== 1 || ['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'TEMPLATE'].includes(node.tagName)) return null;
    const children = Array.from(node.childNodes, (child, i) => render(child, i));
    const tag = node.tagName.toLowerCase();
    if (!['p', 'br', 'strong', 'em', 'b', 'i', 'ul', 'ol', 'li', 'a'].includes(tag)) return children;
    const props = { key };
    if (tag === 'a') {
      const href = node.getAttribute('href') || '';
      if (/^(https?:\/\/|mailto:)/i.test(href.trim())) Object.assign(props, { href, target: '_blank', rel: 'noopener noreferrer' });
    }
    return createElement(tag, props, ...(tag === 'br' ? [] : children));
  }
  return <div className="faq-body">{Array.from(doc.body.childNodes, (n, i) => render(n, i))}</div>;
}

const graph = () => new URLSearchParams(location.search).get('graphid') || '2012701';
const demoUrl = (path) => `${path}?graphid=${encodeURIComponent(graph())}`;

export function MitIdDemo() {
  const [lang, setLang] = useState('da');
  const [activeTab, setActiveTab] = useState('mitid');

  function proceed() {
    sessionStorage.setItem('application-demo-continue', 'yes');
    location.assign(demoUrl('/application'));
  }

  return (
    <main className="nemlogin-portal">
      {/* Top Banner */}
      <header className="nemlogin-header">
        <div className="nemlogin-header-inner">
          <div className="nemlogin-brand">
            <div className="nemlogin-emblem">
              <svg viewBox="0 0 40 40" width="36" height="36" fill="none" aria-hidden="true">
                <circle cx="20" cy="20" r="20" fill="#0059B3" />
                <path d="M10 26h20v2.5H10V26Zm0-1.5h20l-2.4-8-5.6 4.5-2-7.5-2 7.5-5.6-4.5L10 24.5Z" fill="#FFFFFF" />
                <circle cx="20" cy="11.5" r="1.6" fill="#FFFFFF" />
                <circle cx="12.5" cy="16" r="1.3" fill="#FFFFFF" />
                <circle cx="27.5" cy="16" r="1.3" fill="#FFFFFF" />
              </svg>
            </div>
            <span className="nemlogin-title">Log-in</span>
          </div>

          <div className="nemlogin-lang-switch">
            <button
              type="button"
              className={`lang-btn ${lang === 'da' ? 'active' : ''}`}
              onClick={() => setLang('da')}
            >
              Dansk
            </button>
            <button
              type="button"
              className={`lang-btn ${lang === 'kl' ? 'active' : ''}`}
              onClick={() => setLang('kl')}
            >
              Kalaallisut
            </button>
            <button
              type="button"
              className={`lang-btn ${lang === 'en' ? 'active' : ''}`}
              onClick={() => setLang('en')}
            >
              English
            </button>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="nemlogin-tabs-bar">
        <div className="nemlogin-tabs-inner">
          <button
            type="button"
            className={`nemlogin-tab ${activeTab === 'mitid' ? 'active' : ''}`}
            onClick={() => setActiveTab('mitid')}
          >
            MitID
          </button>
          <button
            type="button"
            className={`nemlogin-tab ${activeTab === 'local' ? 'active' : ''}`}
            onClick={() => setActiveTab('local')}
          >
            {lang === 'da' ? 'Lokal login' : lang === 'kl' ? 'Najukkami iserneq' : 'Local login'}
          </button>
        </div>
      </div>

      {/* Main Container */}
      <div className="nemlogin-body">
        <div className="nemlogin-layout">
          {/* Left Column: MitID Card */}
          <div className="nemlogin-left">
            <div className="mitid-card">
              <div className="mitid-card-head">
                <h1 className="mitid-card-title">
                  {lang === 'da' ? 'Log på med MitID' : lang === 'kl' ? 'MitID atorlugu iserit' : 'Log on with MitID'}
                </h1>
                <div className="mitid-mark" aria-label="MitID logo">
                  <span className="mit-word">Mit</span>
                  <div className="mit-icon-graphic">
                    <span className="mit-dot-left" />
                    <span className="mit-dot-right" />
                    <span className="mit-smile" />
                  </div>
                </div>
              </div>

              <div className="mitid-action-row">
                <button type="button" className="mitid-continue-btn" onClick={proceed}>
                  <span>
                    {lang === 'da'
                      ? 'FORTSÆT TIL LOGIN'
                      : lang === 'kl'
                        ? 'INGERLAQQIGIT ISERLUGIT'
                        : 'CONTINUE TO LOGIN'}
                  </span>
                  <Icon name="arrow-right" size={18} stroke={2.5} />
                </button>
              </div>

              <div className="mitid-sim-box">
                <div className="sim-title">
                  <Icon name="info" size={15} />
                  <span>
                    {lang === 'da'
                      ? 'Simuleret demonstration for SU Handicaptillæg'
                      : 'Simulated demonstration for SU Disability Allowance'}
                  </span>
                </div>
                <p>
                  {lang === 'da'
                    ? 'Dette skærmbillede illustrerer det officielle NemLog-in trin. Ingen rigtige NemLog-in eller MitID oplysninger afkræves. Fortsæt for at afprøve ansøgningsforløbet med fiktive testdata.'
                    : 'This screen illustrates the authentic NemLog-in step. No real credentials will be requested. Continue to test the guided application flow using fictional demo data.'}
                </p>
              </div>

              <div className="mitid-bottom-link">
                <a href={demoUrl('/demo')}>
                  ← {lang === 'da' ? 'Tilbage til SU-support & FAQ' : 'Back to SU-support & FAQ'}
                </a>
              </div>
            </div>
          </div>

          {/* Right Column: Stacked Information Cards */}
          <div className="nemlogin-right">
            {/* Card 1: Operating status */}
            <section className="info-card-block">
              <div className="info-pill-tag">
                {lang === 'da' ? 'Driftsstatus' : 'Operating status'}
              </div>
              <div className="info-card-body status-body">
                <span className="status-live-dot" />
                <span>{lang === 'da' ? 'Normal drift' : 'Normal operation'}</span>
              </div>
            </section>

            {/* Card 2: Using MitID securely */}
            <section className="info-card-block">
              <div className="info-pill-tag">
                {lang === 'da' ? 'Brug MitID sikkert' : 'Using MitID securely'}
              </div>
              <div className="info-card-body">
                <p>
                  {lang === 'da'
                    ? 'Pas godt på dit MitID og hold altid dine MitID-oplysninger for dig selv. Få tips og gode råd om sikker brug.'
                    : 'Take good care of your MitID and always keep your MitID information to yourself. Get tips and advice on how to use MitID easily and safely.'}
                </p>
                <a href="#" className="info-link" onClick={(e) => e.preventDefault()}>
                  <span>{lang === 'da' ? 'Sikkerhed' : 'Security'}</span>
                  <Icon name="external" size={14} />
                </a>
              </div>
            </section>

            {/* Card 3: More information */}
            <section className="info-card-block">
              <div className="info-pill-tag">
                {lang === 'da' ? 'Mere information' : 'More information'}
              </div>
              <div className="info-card-body">
                <ul className="info-links-list">
                  <li>
                    <a href="#" onClick={(e) => e.preventDefault()}>
                      {lang === 'da' ? 'Hjælp til Login' : 'Help to Login'}
                      <Icon name="external" size={13} />
                    </a>
                  </li>
                  <li>
                    <a href="#" onClick={(e) => e.preventDefault()}>
                      {lang === 'da' ? 'Om NemLog-in' : 'About NemLog-in'}
                      <Icon name="external" size={13} />
                    </a>
                  </li>
                  <li>
                    <a href="#" onClick={(e) => e.preventDefault()}>
                      {lang === 'da' ? 'Mere om NemLog-in cookies' : 'More about NemLog-in cookies'}
                      <Icon name="external" size={13} />
                    </a>
                  </li>
                  <li>
                    <a href="#" onClick={(e) => e.preventDefault()}>
                      {lang === 'da' ? 'Læs om MitID' : 'Read about MitID'}
                      <Icon name="external" size={13} />
                    </a>
                  </li>
                  <li>
                    <a href="#" onClick={(e) => e.preventDefault()}>
                      {lang === 'da' ? 'Læs om MitID Erhverv' : 'Read about MitID Erhverv'}
                      <Icon name="external" size={13} />
                    </a>
                  </li>
                  <li>
                    <a href="#" onClick={(e) => e.preventDefault()}>
                      {lang === 'da' ? 'Tilgængelighedserklæring (på dansk)' : 'Accessibility statement (in Danish)'}
                      <Icon name="external" size={13} />
                    </a>
                  </li>
                </ul>
              </div>
            </section>

            {/* Card 4: How we process your personal data */}
            <section className="info-card-block">
              <div className="info-pill-tag">
                {lang === 'da' ? 'Sådan behandler vi dine personoplysninger' : 'How we process your personal data'}
              </div>
              <div className="info-card-body">
                <p>
                  {lang === 'da'
                    ? 'Digitaliseringsstyrelsen behandler dine personoplysninger, når du anvender NemLog-in til at bekræfte din identitet. Vi indhenter data fra dit MitID, herunder dit CPR-nummer. Af sikkerhedsmæssige årsager opbevares en log over din anvendelse af NemLog-in i 24 måneder.'
                    : 'The Agency for Digital Government processes your personal data when you use NemLog-in to verify your identity. We collect data from your MitID, including your CPR number. For security reasons, we store a record of your use of NemLog-in for 24 months.'}
                </p>
              </div>
            </section>
          </div>
        </div>
      </div>

      <footer className="nemlogin-footer">
        <p>Demonstration – Udviklet til test af DCR-understøttet ansøgningsproces for SU Handicaptillæg.</p>
      </footer>
    </main>
  );
}

/* Attaching one or more files. DCR records the activity; names are the value. */
function FilePick({ field, busy, onSubmit }) {
  const [files, setFiles] = useState([]);
  const [problem, setProblem] = useState('');
  const input = useRef(null);
  useEffect(() => { setFiles([]); setProblem(''); }, [field.id]);
  const max = field.max_files || 1;
  const exts = field.extensions || [];

  function choose(list) {
    const picked = Array.from(list || []);
    const bad = picked.filter(f => !exts.some(x => f.name.toLowerCase().endsWith(x)));
    const keep = picked.filter(f => !bad.includes(f));
    const merged = [...files, ...keep].filter((f, i, a) => a.findIndex(o => o.name === f.name) === i);
    setProblem(bad.length ? `Skipped ${bad.map(f => f.name).join(', ')} — only ${exts.join(' and ')} are accepted.`
      : merged.length > max ? `Only the first ${max} will be attached.` : '');
    setFiles(merged.slice(0, max));
    if (input.current) input.current.value = '';
  }

  return <div className="filepick">
    <button className="chip" disabled={busy} onClick={() => input.current?.click()}>
      {files.length ? 'Add another file' : max > 1 ? 'Choose files' : 'Choose file'}
    </button>
    <input ref={input} type="file" hidden multiple={max > 1} accept={exts.join(',')}
      onChange={e => choose(e.target.files)} />
    {files.length > 0 && <ul className="filelist">
      {files.map(f => <li key={f.name}>
        <span className="fname">{f.name}</span>
        <span className="fsize">{f.size < 1048576 ? `${Math.max(1, Math.round(f.size / 1024))} KB`
          : `${(f.size / 1048576).toFixed(1)} MB`}</span>
        <button className="fdrop" disabled={busy} aria-label={`Remove ${f.name}`}
          onClick={() => setFiles(files.filter(x => x !== f))}>✕</button>
      </li>)}
    </ul>}
    {problem && <p className="fnote warn">{problem}</p>}
    <p className="fnote">Accepted formats: {exts.join(', ')}{max > 1 ? ` · up to ${max} files` : ''}. No files are uploaded in this demo; only filenames are recorded in the DCR simulation.</p>
    {files.length > 0 && <button className="chip primary" disabled={busy}
      onClick={() => onSubmit(files.map(f => f.name).join(','))}>
      Attach {files.length} file{files.length > 1 ? 's' : ''}</button>}
  </div>;
}

/* Editing an earlier answer. When the person answered in their own words,
   those words are what gets edited; the reading is derived again from them. */
function EditAnswer({ entry, busy, initialWords = '', cancelLabel = 'Cancel', onSave, onDescribe, onCancel }) {
  const [value, setValue] = useState('');
  const [words, setWords] = useState(initialWords);
  const [picked, setPicked] = useState([]);
  const describable = ['choice', 'int', 'integer', 'float'].includes(entry.type);
  const cancel = <button className="chip ghost" type="button" disabled={busy} onClick={onCancel}>{cancelLabel}</button>;

  const inWords = describable && <form className={`edit-words${initialWords ? ' lead' : ''}`} onSubmit={e => {
      e.preventDefault(); if (words.trim()) onDescribe(entry.id, words.trim());
    }}>
    <label>{initialWords ? 'Your answer in your own words' : 'Or describe it in your own words'}</label>
    <div className="ask-row">
      <input autoFocus={!!initialWords} value={words} disabled={busy}
        placeholder="e.g. occurred after an accident" onChange={e => setWords(e.target.value)} />
      <button className="chip primary" type="submit" disabled={busy || !words.trim()}>Re-interpret</button>
    </div>
  </form>;

  const chips = entry.type === 'choice' && entry.multiple
    ? <div className="chat-choices edit-choices checklist">
        {entry.options.map(o => {
          const on = picked.includes(o.value);
          return <button className={`chip${on ? ' picked' : ''}`} key={o.value} disabled={busy}
            onClick={() => setPicked(p => on ? p.filter(x => x !== o.value) : [...p, o.value])}>
            {on ? <Icon name="check" size={13} stroke={2.5} /> : null}
            {o.label}
          </button>;
        })}
        <button className="chip primary" disabled={busy || !picked.length}
          onClick={() => onSave(picked.join(','))}>Confirm {picked.length ? `(${picked.length})` : ''}</button>
      </div>
    : entry.type === 'choice'
      ? <div className="chat-choices edit-choices">{entry.options.map(o =>
          <button className="chip" key={o.value} disabled={busy} onClick={() => onSave(o.value)}>{o.label}</button>)}</div>
      : ['boolean', 'bool'].includes(entry.type)
        ? <div className="chat-choices edit-choices">{[['Yes', 'true'], ['No', 'false']].map(([t, v]) =>
            <button className="chip" key={v} disabled={busy} onClick={() => onSave(v)}>{t}</button>)}</div>
        : null;

  if (chips) return <>
    {initialWords ? <>{inWords}<p className="edit-or">or choose directly</p>{chips}</> : <>{chips}{inWords}</>}
    <div className="chat-choices">{cancel}</div>
  </>;

  const kind = entry.type === 'date' ? 'month'
    : ['int', 'integer', 'float'].includes(entry.type) ? 'number'
      : entry.type === 'email' ? 'email' : 'text';
  const long = ['longtext', 'textbox'].includes(entry.type);
  return <form className="edit-form" onSubmit={e => { e.preventDefault(); if (value.trim()) onSave(value.trim()); }}>
    {long
      ? <textarea autoFocus value={value} maxLength={4000} onChange={e => setValue(e.target.value)} />
      : <input autoFocus type={kind} value={value}
          step={entry.type === 'float' ? 'any' : undefined}
          min={entry.hours ? 0 : undefined} max={entry.hours ? 168 : undefined}
          onChange={e => setValue(e.target.value)} />}
    <div className="chat-choices">
      <button className="chip primary" type="submit" disabled={busy || !value.trim()}>Save change</button>{cancel}
    </div>
  </form>;
}

// 5 parts of the application, shown as "Part n of 5". DCR does not say how many questions are left (later
// questions depend on earlier answers), so the part comes from the field id (fields of the Clean graph's Form0).
// An unknown field keeps the part of the last known one.
const STAGES = [
  { id: 1, title: 'About you' },
  { id: 2, title: 'Your impairment' },
  { id: 3, title: 'Work' },
  { id: 4, title: 'Documentation' },
  { id: 5, title: 'Check and send' },
];
const STAGE_OF_FIELD = {
  'Form0:Email': 0, 'Form0:Phone': 0, 'Form0:A1_1': 0,
  'Form0:A2': 1, 'Form0:Impairment_type': 1, 'Form0:Impairment_definition': 1, 'Form0:A14': 1,
  'Form0:Time_limited': 1, 'Form0:A17': 1,
  'Form0:Prev_work': 2, 'Form0:A15': 2, 'Form0:Plan_work_studies': 2, 'Form0:A16': 2,
  'Form0:Samtykke': 3, 'Form0:A5': 3, 'Form0:A11': 3,
  'Form0:A10': 4,
};

function stageOf(state, fieldId, last) {
  if (!state) return 0;
  if (['review', 'complete', 'declined'].includes(state.status)) return 4;
  if (fieldId in STAGE_OF_FIELD) return STAGE_OF_FIELD[fieldId];
  if (['file', 'demo_file'].includes(state.field?.type)) return 3;
  return last;
}

const wide = () => window.matchMedia?.('(min-width: 861px)').matches ?? true;
const SourceIcon = () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6" /></svg>;

// A typed answer that is only a number is submitted as it is. Only words are sent to be interpreted.
const PLAIN_NUMBER = /^[+-]?\d+(?:[.,]\d+)?$/;
const NUMERIC_TYPES = ['int', 'integer', 'float'];

/* The options of the current question, shown under it in the thread. A single choice is answered by clicking it
   (no Continue button); several choices are ticked and confirmed with Continue. */
function InlineChoices({ field, busy, onSubmit }) {
  const [picked, setPicked] = useState([]);
  useEffect(() => { setPicked([]); }, [field?.id]);
  if (!field) return null;
  if (field.type === 'file') return <FilePick field={field} busy={busy} onSubmit={onSubmit} />;
  const isBool = ['boolean', 'bool'].includes(field.type);
  const options = isBool ? [{ label: 'Yes', value: 'true' }, { label: 'No', value: 'false' }]
    : field.type === 'choice' ? field.options : null;
  if (!options) return null;
  const multi = field.type === 'choice' && field.multiple;
  if (!multi) {
    return <div className={`ap-choices${options.length === 2 ? ' pair' : ''}`} role="group" aria-label={field.label}>
      {options.map(o => <button key={o.value} type="button" className="ap-choice" disabled={busy}
        onClick={() => onSubmit(o.value)}>{o.label}</button>)}
    </div>;
  }
  const toggle = (v) => setPicked(p => p.includes(v) ? p.filter(x => x !== v) : [...p, v]);
  return <>
    <fieldset className="ap-options" disabled={busy}>
      <legend className="sr-only">{field.label}</legend>
      <p className="ap-hint">Select all that apply.</p>
      {options.map(o => <label className="ap-opt" key={o.value}>
        <input type="checkbox" name={`opt-${field.id}`} checked={picked.includes(o.value)} onChange={() => toggle(o.value)} />
        <span className="ap-opt-label">{o.label}</span>
      </label>)}
    </fieldset>
    <div className="ap-actions">
      <button type="button" className="ap-btn primary" disabled={busy || !picked.length}
        onClick={() => onSubmit(picked.join(','))}>Continue</button>
    </div>
  </>;
}

/* The message box at the bottom of the thread. It is always visible, so there is nothing to open: on a choice
   question it is the "none of these fit" route (words are read and suggested, the person confirms), on a number
   or text question it is the answer. A plain number is not interpreted (see send()). Nothing here changes what
   DCR asks. */
function Composer({ field, busy, value, onChange, onSend }) {
  const box = useRef(null);
  const hasOptions = !!field && (field.type === 'choice' || ['boolean', 'bool'].includes(field.type));
  useEffect(() => {
    // Do not pop up the keyboard on a phone for a question that is answered by tapping.
    if (!hasOptions) box.current?.focus({ preventScroll: true });
  }, [field?.id, hasOptions]);
  if (!field || ['file', 'submit', 'boolean', 'bool'].includes(field.type)) return null;
  const long = ['longtext', 'textbox'].includes(field.type);
  const choice = field.type === 'choice';
  const numeric = NUMERIC_TYPES.includes(field.type);
  const placeholder = choice ? 'None of these fit? Describe your situation'
    : numeric ? 'Type a number, or describe it in your own words'
      : field.type === 'date' ? 'For example 2026-09' : 'Type your answer';
  const label = choice ? 'Describe your situation in your own words' : field.label;
  const submit = (e) => {
    e?.preventDefault();
    const t = value.trim();
    if (t && !busy) onSend(t);
  };
  return <div className="ap-dock">
    <form className="ap-compose" onSubmit={submit}>
      {long
        ? <textarea ref={box} rows={3} value={value} maxLength={4000} disabled={busy} aria-label={label} placeholder={placeholder}
            onChange={e => onChange(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit(e); }} />
        : <input ref={box} value={value} maxLength={2000} disabled={busy} aria-label={label} placeholder={placeholder}
            autoComplete="off" inputMode={numeric ? 'decimal' : undefined} onChange={e => onChange(e.target.value)} />}
      <button type="submit" className="ap-send" aria-label="Send" disabled={busy || !value.trim()}>
        <Icon name="arrow-up" size={18} stroke={2} />
      </button>
    </form>
    {choice && <p className="ap-compose-hint">We suggest the option that fits. You confirm it before it is used.</p>}
  </div>;
}

const HELP_EXAMPLES = [
  { q: 'What documentation do I need?', s: 'Documents and who can issue them' },
  { q: 'Can I work while receiving handicaptillæg?', s: 'Rules on work and earnings' },
  { q: 'How long does the decision take?', s: 'After you have applied' }
];

/* Ask SU-support: questions about the rules, kept apart from the application so the form never changes because
   of a question. Anything typed here is a question. The panel follows the question on screen: each new question adds
   an "About this question" card (help text from DCR) with its suggested questions, and typed questions are searched
   with that question as context (the server searches the typed words first, then adds the field's question, then,
   if nothing was found, rewrites the question with the field and its help text). The applicant can switch the
   context off with the chip above the input. */
function HelpPanel({ thread, match, determination, busy, error, focusKey, scoped, canScope, onAsk, onRelated, onScope, onPick,
  onNone, onDetermine, onSkipDetermination, onPerson, onClose }) {
  const [draft, setDraft] = useState('');
  const box = useRef(null);
  const tail = useRef(null);
  useEffect(() => { if (focusKey > 0) box.current?.focus(); }, [focusKey]);
  useEffect(() => { tail.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [thread, match, determination]);
  const submit = (e) => {
    e.preventDefault();
    const text = draft.trim();
    if (text && !busy) { setDraft(''); onAsk(text); }
  };
  const lastField = [...thread].reverse().find(m => m.kind === 'field');
  const askedRelated = new Set(thread.filter(m => m.relatedId).map(m => m.relatedId));
  const started = thread.some(m => m.kind !== 'field') || !!match || !!determination;
  return <aside className="hp" aria-label="Ask SU-support" onKeyDown={e => { if (e.key === 'Escape') onClose(); }}>
    <div className="hp-grab" aria-hidden="true" />
    <header className="hp-head">
      <div>
        <h2 className="hp-name">Ask SU-support</h2>
        <p className="hp-sub">Answers from the SU guidelines. Asking never changes your answers.</p>
      </div>
      <button type="button" className="hp-close" onClick={onClose} aria-label="Hide Ask SU-support">
        <Icon name="close" size={20} />
      </button>
    </header>
    <div className="hp-scroll" role="log" aria-live="polite">
      {!lastField && !started && <div className="hp-greet">
        <h3>Hello there!</h3>
        <p>What would you like to know?</p>
      </div>}
      {!lastField && !started && !busy && <div className="hp-cards">
        {HELP_EXAMPLES.map(x => <button key={x.q} type="button" className="hp-card" onClick={() => onAsk(x.q)}>
          <b>{x.q}</b><span>{x.s}</span>
        </button>)}
      </div>}
      {thread.map(m => {
        if (m.kind === 'field') {
          if (m !== lastField) return <p key={m.key} className="hp-divider"><span>Earlier question</span>{m.label}</p>;
          const related = (m.help?.related || []).filter(r => !askedRelated.has(r.id));
          return <div key={m.key} className="hp-field">
            <section className="hp-about">
              <p className="hp-eyebrow">About this question</p>
              <h4>{m.label}</h4>
              {m.help?.html && <AnswerBody html={m.help.html} />}
            </section>
            {related.length > 0 && <>
              <p className="hp-eyebrow hp-sug-label">Common questions</p>
              <div className="hp-cards">
                {related.map(r => <button key={r.id} type="button" className="hp-card" disabled={busy}
                  onClick={() => onRelated(r.id, r.question)}><b>{r.question}</b></button>)}
              </div>
            </>}
          </div>;
        }
        if (m.kind === 'ask') return <div key={m.key} className="hp-user">
          <div className="hp-bubble">{m.text}</div>
          {m.searchedFor && <p className="hp-understood">Understood as: {m.searchedFor}</p>}
        </div>;
        if (m.kind === 'notice') return <p key={m.key} className="hp-note">{m.text}</p>;
        if (m.kind === 'determination') return <article key={m.key} className="hp-answer">
          <h4>{m.question}</h4>
          <p className="hp-understood">Your answer: {m.value}</p>
          {m.outcomes.map((html, i) => <AnswerBody key={i} html={html} />)}
        </article>;
        if (m.kind === 'handover') return <aside key={m.key} className="hp-handover" role="note">
          <Icon name="user" size={20} />
          <div><h4>Talk to a person</h4><AnswerBody html={m.html} /></div>
        </aside>;
        return <article key={m.key} className="hp-answer">
          <h4>{m.question}</h4>
          <AnswerBody html={m.text} />
          {m.citation && <span className="hp-source"><SourceIcon />Source: {m.citation}</span>}
        </article>;
      })}
      {match && <div className="hp-match">
        <p className="hp-match-q">{match.response}</p>
        <div className="hp-cards">
          {match.candidates.map(c => <button type="button" className="hp-card" key={c.candidate_key} disabled={busy}
            onClick={() => onPick(c.candidate_key, c.question)}><b>{c.question}</b></button>)}
        </div>
        {match.status === 'faq_confirm' && match.candidates.length === 1 && <button type="button" className="ap-btn primary"
          disabled={busy} onClick={() => onPick(match.candidates[0].candidate_key, match.candidates[0].question)}>Yes, show the answer</button>}
        <button type="button" className="ap-link" disabled={busy} onClick={onNone}>
          {match.candidates.length === 1 ? 'No, that is not it' : 'None of these'}
        </button>
      </div>}
      {determination && <div className="hp-match hp-followup">
        <p className="hp-eyebrow">{determination.text || 'One more question so the answer fits your situation (you can skip it):'}</p>
        <p className="hp-match-q">{determination.prompt.text}</p>
        <div className="hp-cards">
          {determination.prompt.options.map(o => <button type="button" className="hp-card" key={o.value} disabled={busy}
            onClick={() => onDetermine(o.value, o.label)}><b>{o.label}</b></button>)}
        </div>
        <button type="button" className="ap-link" disabled={busy} onClick={onSkipDetermination}>Skip</button>
      </div>}
      {busy && <div className="hp-typing" role="status" aria-label="Searching the FAQ"><i /><i /><i /></div>}
      {error && <p className="ap-error" role="alert">{error}</p>}
      <div ref={tail} />
    </div>
    <form className="hp-composer" onSubmit={submit}>
      <label htmlFor="hp-input" className="sr-only">Your question</label>
      <input id="hp-input" ref={box} value={draft} maxLength={2000} disabled={busy} autoComplete="off"
        placeholder={scoped ? 'Ask about this question' : 'Ask about the rules'}
        onChange={e => setDraft(e.target.value)} />
      <div className="hp-composer-row">
        {scoped
          ? <span className="hp-scope">About this question
              <button type="button" aria-label="Ask without the question on screen as context" onClick={() => onScope(false)}>
                <Icon name="close" size={12} />
              </button></span>
          : canScope
            ? <button type="button" className="hp-ctx-on" onClick={() => onScope(true)}>Ask about this question</button>
            : <span />}
        <button type="submit" className="hp-send" aria-label="Send question" disabled={busy || !draft.trim()}>
          <Icon name="arrow-up" size={18} stroke={2} />
        </button>
      </div>
    </form>
    <p className="hp-foot">Need a person? <button type="button" className="ap-link" disabled={busy} onClick={onPerson}>Talk to a person</button></p>
  </aside>;
}

export function ApplicationDemo() {
  const [state, setState] = useState(null);
  const [thread, setThread] = useState([]);
  const [match, setMatch] = useState(null);
  const [determination, setDetermination] = useState(null);   // the follow-up question that came with an answer
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');   // a problem with the answer itself, shown in the thread
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState('');
  const [interp, setInterp] = useState(null);
  const [helpOpen, setHelpOpen] = useState(wide);
  const [helpThread, setHelpThread] = useState([]);
  const [helpFocus, setHelpFocus] = useState(0);
  const [scopeOff, setScopeOff] = useState(false);
  const sid = useRef(null);
  if (sid.current === null) sid.current = newSessionId();
  const inflight = useRef(false);
  const tail = useRef(null);

  useEffect(() => { tail.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [thread, state, interp, formError, editing, busy]);

  useEffect(() => { setDraft(''); setFormError(''); }, [state?.field?.id]);

  const onField = !!state?.field && state.status === 'question';
  const helpScope = onField && !scopeOff ? { kind: 'field' } : null;

  const add = (entry) => setThread(t => [...t, { ...entry, key: `${t.length}-${entry.kind}` }]);
  const addHelp = (entry) => setHelpThread(t => [...t, { ...entry, key: `${t.length}-${entry.kind}` }]);

  // A question becomes a bubble the moment it is asked, so the conversation
  // reads as a thread from the first turn instead of a lone form card.
  const asked = useRef(null);
  useEffect(() => {
    const id = state?.prompt_id;
    if (!id || asked.current === id) return;
    asked.current = id;
    const text = state.status === 'review' ? 'Please review your answers below, and then send the demo application.' : state.field?.label;
    if (text) setThread(t => [...t, { kind: 'question', text, key: `${t.length}-question` }]);
  }, [state?.prompt_id, state?.status, state?.field?.label]);

  // The help panel follows the question on screen: a new question adds its card (help text and suggested
  // questions from DCR) to the panel thread and turns the question context back on.
  useEffect(() => {
    const field = state?.field;
    if (!field || state.status !== 'question') return;
    setScopeOff(false);
    setHelpThread(t => {
      const last = [...t].reverse().find(m => m.kind === 'field');
      if (last?.fieldId === field.id) return t;
      return [...t, { kind: 'field', fieldId: field.id, label: field.label, help: field.help, key: `${t.length}-field` }];
    });
  }, [state?.field, state?.status]);

  // local: the request is about the form (an answer, a change), so a problem is shown in the thread, not in Help.
  async function request(path, payload, local = false) {
    if (inflight.current) return null;
    inflight.current = true; setBusy(true); setError(''); setFormError('');
    try {
      const r = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Session-ID': sid.current },
        body: JSON.stringify(payload)
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Could not complete action.');
      return data;
    } catch (e) { (local ? setFormError : setError)(e.message); return null; }
    finally { inflight.current = false; setBusy(false); }
  }

  function start() {
    if (sessionStorage.getItem('application-demo-continue') !== 'yes') {
      location.assign(demoUrl('/mitid')); return;
    }
    request('/application/init', { graph_id: graph(), demo_continue: true }, true)
      .then(data => { if (data) { setThread([]); setState(data); } });
  }

  function answer(raw) {
    const field = state.field;
    const value = normalise(field, raw);
    const shown = field.type === 'choice'
      ? raw.split(',').map(v => field.options.find(o => o.value === v.trim())?.label ?? v.trim()).join(', ')
      : ['boolean', 'bool'].includes(field.type) ? (raw === 'true' ? 'Yes' : 'No') : raw;
    add({ kind: 'reply', text: field.type === 'submit' ? 'Send demo application' : shown, fieldId: field.id });
    request('/application/answer', { prompt_id: state.prompt_id, value,
      source: field.type === 'file' ? 'attachment' : 'chosen' }, true).then(data => {
      if (data) setState(data);
      else dropReply(field.id);
    });
  }

  const INTERPRETABLE = ['int', 'integer', 'float', 'choice'];

  // The composer is a plain text box, so month input arrives in whatever shape
  // the person types it. Accept the common ones and normalise to ISO.
  function normalise(field, text) {
    if (field?.type !== 'date') return text;
    const t = text.trim().replace(/[/.]/g, '-');
    let m;
    if ((m = t.match(/^(\d{4})-(\d{1,2})$/))) return `${m[1]}-${m[2].padStart(2, '0')}-01`;
    if ((m = t.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/)))
      return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`;
    if ((m = t.match(/^(\d{1,2})-(\d{4})$/))) return `${m[2]}-${m[1].padStart(2, '0')}-01`;
    if ((m = t.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/)))
      return `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
    return t;
  }

  // Typed into the composer. A question mark means they are asking, whatever
  // the current field type is: the question goes to the help panel. Everything
  // else is an answer to the field on screen.
  function send(text) {
    const field = state.field;
    setDraft(''); setInterp(null);
    if (/\?\s*$/.test(text)) { ask(text); return; }
    if (field?.type === 'file') { ask(text); return; }
    // A number the person typed is their answer: it is not read by the model and needs no confirmation.
    // The server still checks the range.
    if (NUMERIC_TYPES.includes(field?.type) && PLAIN_NUMBER.test(text)) {
      add({ kind: 'reply', text, fieldId: field.id });
      request('/application/answer', { prompt_id: state.prompt_id, value: text.replace(',', '.') }, true).then(data => {
        if (data) setState(data);
        else { dropReply(field.id); setDraft(text); }
      });
      return;
    }
    add({ kind: 'reply', text, fieldId: field?.id, typedText: text });
    if (field && INTERPRETABLE.includes(field.type)) {
      request('/application/interpret', { prompt_id: state.prompt_id, message: text }, true).then(data => {
        if (!data) { dropReply(field.id); setDraft(text); return; }
        if (data.status === 'interpreted') {
          setInterp(data);
        } else {
          // Not readable as an answer. It is not treated as a question either:
          // asking goes through the help panel only. The words go back into the box to be edited.
          dropReply(field.id); setDraft(text);
          add({ kind: 'notice', text: `${data.response || 'I could not read that as an answer.'} `
            + 'If it was a question about the rules, ask it in Help.' });
          if (data.handover?.html) { openHelp(); addHelp({ kind: 'handover', html: data.handover.html }); }
        }
      });
      return;
    }
    request('/application/answer', { prompt_id: state.prompt_id, value: normalise(field, text) }, true).then(data => {
      if (data) setState(data);
      else { dropReply(field.id); setDraft(text); }
    });
  }

  function confirmInterp(data) {
    const { value, field_id: target, display: shown } = data;
    const wasEdit = !!editing || !!data.wasEdit;
    const editTarget = data.editFieldId || editing || target;
    setInterp(null); setEditing(null);
    if (wasEdit) {
      request('/application/edit', { field_id: editTarget, value }, true).then(res => {
        if (res) rewind(editTarget, res);
      });
      return;
    }
    setThread(t => {
      const i = [...t].reverse().findIndex(m => m.kind === 'reply' && m.fieldId === target && m.typedText);
      if (i === -1) return [...t, { kind: 'reply', text: shown, fieldId: target, key: `${t.length}-reply` }];
      const at = t.length - 1 - i;
      return t.map((m, j) => j === at ? { ...m, interpreted: shown } : m);
    });
    request('/application/answer', { prompt_id: state.prompt_id, value, source: 'interpreted' }, true).then(res => {
      if (res) setState(res);
    });
  }

  function dropReply(target) {
    setThread(t => {
      const i = [...t].reverse().findIndex(m => m.kind === 'reply' && m.fieldId === target);
      if (i === -1) return t;
      const at = t.length - 1 - i;
      return t.filter((_, j) => j !== at);
    });
  }

  function rejectInterp() {
    if (interp?.field_id && !interp.wasEdit) {
      const target = interp.field_id;
      const typed = [...thread].reverse().find(m => m.kind === 'reply' && m.fieldId === target && m.typedText);
      if (typed) setDraft(typed.typedText);
      setThread(t => {
        const i = [...t].reverse().findIndex(m => m.kind === 'reply' && m.fieldId === target && m.typedText);
        if (i === -1) return t;
        const at = t.length - 1 - i;
        return t.filter((_, j) => j !== at);
      });
    }
    setInterp(null);
  }

  function describeEdit(fieldId, words) {
    request('/application/interpret', { field_id: fieldId, message: words }, true).then(data => {
      if (!data) return;
      if (data.status === 'interpreted') {
        setInterp({ ...data, wasEdit: true, editFieldId: fieldId });
      } else {
        add({ kind: 'notice', text: data.response || 'Could not interpret answer.' });
      }
    });
  }

  function rewind(fieldId, data) {
    setThread(t => {
      const at = t.findIndex(m => m.kind === 'reply' && m.fieldId === fieldId);
      const before = at === -1 ? t : t.slice(0, at);
      const a = (data.answers || []).find(x => x.id === fieldId);
      return a ? [...before, { kind: 'reply', text: a.value, fieldId, key: `${before.length}-reply` }] : before;
    });
    asked.current = null;
    setState(data);
  }

  function saveEdit(raw) {
    const entry = (state.answers || []).find(a => a.id === editing);
    const value = normalise(entry, raw);
    setEditing(null);
    request('/application/edit', { field_id: editing, value }, true).then(data => {
      if (data) rewind(editing, data);
    });
  }

  // aboutField: opened from "Ask SU-support about this question", which turns the question context back on.
  function openHelp(aboutField = false) {
    setHelpOpen(true); if (aboutField) setScopeOff(false); setHelpFocus(n => n + 1);
  }

  function showHelpResult(data) {
    if (data.handover?.html) addHelp({ kind: 'handover', html: data.handover.html });
    if (data.status === 'handover') return;
    if (['faq_no_match', 'faq_unavailable', 'faq_none', 'faq_out_of_scope'].includes(data.status)) {
      addHelp({ kind: 'notice', text: data.response }); return;
    }
    setMatch(data);
  }

  function showAnswer(data, question) {
    addHelp({ kind: 'faq', question: data.faq_question || question, text: data.faq_response,
      citation: data.faq_citation, faqId: data.faq_id });
    // Same field, new ticket: adopt it without asking the field again in the thread.
    asked.current = data.prompt_id;
    const { prompt, follow_up, ...view } = data;
    setState(view);
    // Spec 03: the follow-up determination of an answered FAQ is asked here, not in the chat.
    setDetermination(prompt?.kind === 'determination' ? { prompt, text: follow_up } : null);
  }

  function determine(value, text) {
    const issued = determination;
    setDetermination(null);
    request('/application/determination', { retrieval_prompt_id: issued.prompt.id, value }).then(data => {
      if (!data) return;
      addHelp({ kind: 'determination', question: data.answered?.question || issued.prompt.text,
        value: data.answered?.value || text, outcomes: data.outcomes || [] });
      if (data.prompt?.kind === 'determination') setDetermination({ prompt: data.prompt });
    });
  }

  function sendHelp(payload, shown) {
    setHelpOpen(true);
    setMatch(null);
    setDetermination(null);
    const key = Date.now();
    addHelp({ kind: 'ask', text: shown, id: key, relatedId: payload.related });
    request('/application/ask', payload).then(data => {
      if (!data) return;
      if (data.searched_for) {
        setHelpThread(t => t.map(m => (m.id === key ? { ...m, searchedFor: data.searched_for } : m)));
      }
      if (data.answered) {
        if (data.handover?.html) addHelp({ kind: 'handover', html: data.handover.html });
        showAnswer(data, shown); return;
      }
      showHelpResult(data);
      // Only for statements ("yes I worked 4 years"), not for questions. Shown after any reply that is not an answer.
      const looksLikeQuestion = /\?\s*$/.test(shown) || /^(what|how|why|when|where|who|which|can|could|do|does|did|is|are|will|would|should|may|must|if)\b/i.test(shown.trim());
      if (['faq_no_match', 'faq_confirm', 'faq_related', 'faq_clarify'].includes(data.status) && payload.scope === 'field' && !looksLikeQuestion) {
        addHelp({ kind: 'notice', text: 'If that was your answer to the question, enter it in the form instead. '
          + 'Here you can ask about the rules.' });
      }
    });
  }

  // Typed in the panel, or a '?' message from the form composer (no scope).
  function ask(message, scope = helpScope) {
    const payload = { message };
    if (scope?.kind === 'field') payload.scope = 'field';
    sendHelp(payload, message);
  }

  function askRelated(id, question) {
    sendHelp({ related: id }, question);
  }

  function confirmMatch(candidate_key, question) {
    const issued = match;
    setMatch(null);
    request('/application/confirm', { match_id: issued.match_id, candidate_key }).then(data => {
      if (data) showAnswer(data, question);
    });
  }

  function noneOfThese() {
    const issued = match;
    setMatch(null);
    request('/application/confirm', { match_id: issued.match_id, candidate_key: 'none' }).then(data => {
      if (data) showHelpResult(data);
    });
  }

  function talkToPerson() {
    openHelp();
    request('/application/handover', {}).then(data => { if (data) showHelpResult(data); });
  }

  const ended = state && ['complete', 'declined'].includes(state.status);
  const review = state && state.status === 'review';

  function handleReset() {
    if (window.confirm('Start a new demo and discard this screen’s answers?')) {
      setState(null); setThread([]); setMatch(null); setDetermination(null); setInterp(null); setError(''); setFormError(''); setDraft(''); sid.current = newSessionId();
      setHelpThread([]); setHelpOpen(wide());
    }
  }

  // Back / Change: the answer being changed is shown in place of the current question.
  const answers = state?.answers || [];
  const editIndex = editing ? answers.findIndex(a => a.id === editing) : -1;
  const editEntry = editIndex >= 0 ? answers[editIndex] : null;
  function goBack() {
    const to = editEntry ? editIndex - 1 : answers.length - 1;
    if (to >= 0) { setInterp(null); setEditing(answers[to].id); }
  }

  const lastStage = useRef(0);
  const lastQuestion = thread.map(m => m.kind).lastIndexOf('question');
  const lastNotice = thread.length && thread[thread.length - 1].kind === 'notice' ? thread[thread.length - 1] : null;
  const stage = stageOf(state, editEntry ? editEntry.id : state?.field?.id, lastStage.current);
  lastStage.current = stage;

  return (
    <main className={`ap${helpOpen && state ? ' ap-help' : ''}`}>
      <div className="ap-split">
        <section className="ap-main">
          <div className={`ap-inner${state && !ended ? ' ap-live' : ''}`}>
            <div className="ap-top">
              <a href={demoUrl('/demo')} className="ap-back"><Icon name="arrow-left" size={16} />Back to SU-support</a>
              <div className="ap-top-right">
                {state && <button type="button" className="ap-link ap-reset" disabled={busy} onClick={handleReset}>Start again</button>}
                <ThemeToggle />
                {state && !ended && !helpOpen && (
                  <button type="button" className="ap-open" aria-expanded={false} onClick={() => openHelp()}>
                    <Icon name="message" size={18} />Ask SU-support
                  </button>
                )}
              </div>
            </div>

            {!state && (
              <div className="ap-start">
                <h1 className="ap-title">Apply for disability allowance</h1>
                <p className="ap-lead">We ask one question at a time. You can ask about the rules at any point, and change an earlier answer.</p>
                <button className="ap-btn primary" disabled={busy} onClick={start}>Start the application</button>
                <p className="ap-demo">Demonstration only. Use fictional information. Answers go to the DCR simulation and file contents are not uploaded. Nothing is sent to an authority.</p>
                {formError && <p className="ap-error" role="alert">{formError}</p>}
              </div>
            )}

            {state && !ended && (
              <>
                <div className="ap-progress">
                  <p><span>Part {stage + 1} of {STAGES.length}</span><span>{STAGES[stage].title}</span></p>
                  <div className="ap-bar" role="progressbar" aria-valuemin={1} aria-valuemax={STAGES.length} aria-valuenow={stage + 1}>
                    <i style={{ width: `${((stage + 1) / STAGES.length) * 100}%` }} />
                  </div>
                </div>

                <div className="ap-chat" role="log" aria-label="Your application">
                  {thread.map((m, i) => {
                    if (m.kind === 'question') {
                      const now = i === lastQuestion && !thread.slice(i + 1).some(x => x.kind === 'reply') && !editEntry && !interp;
                      return now
                        ? <h2 key={m.key} className="ap-q now" id="ap-q">{m.text}</h2>
                        : <p key={m.key} className="ap-q">{m.text}</p>;
                    }
                    if (m.kind === 'reply') {
                      const changeable = !editEntry && !interp && answers.some(a => a.id === m.fieldId);
                      return <div key={m.key} className="ap-a">
                        <div className="ap-a-row">
                          {changeable && <button type="button" className="ap-edit" disabled={busy} title="Change this answer"
                            onClick={() => { setInterp(null); setEditing(m.fieldId); }}
                            aria-label={`Change answer: ${m.text}`}><Icon name="edit" size={16} /></button>}
                          <div className="ap-bubble">{m.interpreted || m.text}</div>
                        </div>
                        {m.interpreted && m.typedText && <small>You wrote: {m.typedText}</small>}
                      </div>;
                    }
                    return null;
                  })}

                  {editEntry && <div className="ap-edit-box">
                    <button type="button" className="ap-prev" disabled={busy || editIndex <= 0} onClick={goBack}>
                      <Icon name="arrow-left" size={16} />Previous question
                    </button>
                    <h2 className="ap-q now" id="ap-q">{editEntry.label}</h2>
                    <p className="ap-current">Your answer: <b>{editEntry.value}</b></p>
                    <p className="ap-hint">If you change it, the questions after it are asked again.</p>
                    {!interp && (editEntry.type === 'file'
                      ? <><FilePick field={editEntry} busy={busy} onSubmit={saveEdit} />
                          <div className="ap-actions"><button type="button" className="ap-link" disabled={busy} onClick={() => setEditing(null)}>Keep this answer</button></div></>
                      : <EditAnswer entry={editEntry} busy={busy} cancelLabel="Keep this answer"
                          initialWords={(thread.find(m => m.kind === 'reply' && m.fieldId === editEntry.id && m.typedText) || {}).typedText || ''}
                          onSave={saveEdit} onDescribe={describeEdit} onCancel={() => setEditing(null)} />)}
                  </div>}

                  {lastNotice && !interp && !editEntry && <p className="ap-notice" role="status">{lastNotice.text}</p>}

                  {!editEntry && !interp && (review
                    ? <div className="ap-actions">
                        <button className="ap-btn primary" disabled={busy} onClick={() => answer('send')}>Send demo application</button>
                      </div>
                    : <InlineChoices field={state.field} busy={busy} onSubmit={answer} />)}

                  {!editEntry && !interp && !review && !(helpOpen && helpScope) && (
                    <p className="ap-ask">
                      Not sure? <button type="button" className="ap-link" onClick={() => openHelp(true)}>Ask SU-support about this question</button>
                    </p>
                  )}

                  {interp && (
                    <div className="ap-interp" role="group" aria-label="Suggested answer">
                      <p className="ap-interp-label">Based on what you wrote, this option fits best</p>
                      <p className="ap-interp-value">{interp.display}</p>
                      <div className="ap-actions">
                        <button className="ap-btn primary" disabled={busy} onClick={() => confirmInterp(interp)}>Use this answer</button>
                        <button className="ap-link" disabled={busy} onClick={rejectInterp}>Not this</button>
                      </div>
                    </div>
                  )}

                  {busy && !helpOpen && thread.length > 0 && thread[thread.length - 1].kind === 'reply' &&
                    <div className="hp-typing" role="status" aria-label="Checking"><i /><i /><i /></div>}
                  {formError && <p className="ap-error" role="alert">{formError}</p>}
                  <div ref={tail} />
                </div>

                {!editEntry && !interp && !review && (
                  <Composer field={state.field} busy={busy} value={draft} onChange={setDraft} onSend={send} />
                )}
              </>
            )}

            {ended && (
              <div className="ap-done" role="status">
                <h1 className="ap-title">{state.status === 'complete' ? 'Demo complete' : 'Application not sent'}</h1>
                <p className="ap-lead">{state.response}</p>
                <p className="ap-demo">{state.demo_notice}</p>
                <a className="ap-btn secondary link" href={demoUrl('/demo')}>Return to the FAQ</a>
              </div>
            )}

            {error && !helpOpen && <p className="ap-error" role="alert">{error}</p>}
          </div>
        </section>

        {helpOpen && state && !ended && (
          <HelpPanel
            thread={helpThread}
            match={match}
            determination={determination}
            busy={busy}
            error={error}
            focusKey={helpFocus}
            scoped={!!helpScope}
            canScope={onField}
            onAsk={(t) => ask(t)}
            onRelated={askRelated}
            onScope={(on) => { setScopeOff(!on); setHelpFocus(n => n + 1); }}
            onPick={confirmMatch}
            onNone={noneOfThese}
            onDetermine={determine}
            onSkipDetermination={() => setDetermination(null)}
            onPerson={talkToPerson}
            onClose={() => setHelpOpen(false)}
          />
        )}
      </div>

      {helpOpen && state && !ended && <div className="ap-scrim" onClick={() => setHelpOpen(false)} aria-hidden="true" />}
    </main>
  );
}
