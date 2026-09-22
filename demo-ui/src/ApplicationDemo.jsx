import { useState, useRef, useEffect, createElement } from 'react';
import './application.css';
import { newSessionId } from './sessionId';
import Icon from './Icon';

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

/* Buttons for the current question. Typed answers go through the composer. */
function Answer({ field, busy, onSubmit }) {
  const [picked, setPicked] = useState([]);
  useEffect(() => setPicked([]), [field?.id]);
  if (!field || field.type === 'submit') return null;
  if (field.type === 'file') return <FilePick field={field} busy={busy} onSubmit={onSubmit} />;
  if (field.type === 'choice' && field.multiple) {
    const toggle = (v) => setPicked(p => p.includes(v) ? p.filter(x => x !== v) : [...p, v]);
    return <div className="chat-choices inline checklist">
      {field.options.map(o =>
        <button className={`chip${picked.includes(o.value) ? ' picked' : ''}`} disabled={busy}
          key={o.value} aria-pressed={picked.includes(o.value)}
          onClick={() => toggle(o.value)}>
          {picked.includes(o.value) ? <Icon name="check" size={13} stroke={2.5} /> : null}
          {o.label}
        </button>)}
      <button className="chip primary" disabled={busy || !picked.length}
        onClick={() => onSubmit(picked.join(','))}>Confirm {picked.length ? `(${picked.length})` : ''}</button>
    </div>;
  }
  if (field.type === 'choice')
    return <div className="chat-choices inline">{field.options.map(o =>
      <button className="chip" disabled={busy} key={o.value} onClick={() => onSubmit(o.value)}>{o.label}</button>)}</div>;
  if (['boolean', 'bool'].includes(field.type))
    return <div className="chat-choices inline">{[['Yes', 'true'], ['No', 'false']].map(([label, v]) =>
      <button className="chip" key={v} disabled={busy} onClick={() => onSubmit(v)}>{label}</button>)}</div>;
  return null;
}

/* The chat composer. Everything typed goes here, answers and questions alike. */
function Composer({ field, busy, draft, setDraft, onSend, onAsk }) {
  const box = useRef(null);
  useEffect(() => { box.current?.focus(); }, [field?.id]);
  const long = ['longtext', 'textbox'].includes(field?.type);
  const hint = !field ? 'Type a message…'
    : field.type === 'file' ? 'Attach file above, or ask a question here…'
      : field.type === 'date' ? 'e.g. 2026-09'
        : ['int', 'integer', 'float'].includes(field.type) ? 'Enter a number, or describe in your own words…'
          : field.type === 'choice' ? 'Choose an option above, or describe in your own words…'
            : 'Type your answer here…';
  const send = (e) => { e.preventDefault(); if (draft.trim()) onSend(draft.trim()); };
  return <form className="composer" onSubmit={send}>
    {long
      ? <textarea ref={box} value={draft} maxLength={4000} placeholder={hint} disabled={busy}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) send(e); }} />
      : <input ref={box} value={draft} placeholder={hint} disabled={busy}
          onChange={e => setDraft(e.target.value)} />}
    <div className="composer-actions">
      <button type="button" className="chip ghost" disabled={busy || !draft.trim()}
        onClick={() => onAsk(draft.trim())}>Ask as question</button>
      <button type="submit" className="chat-send" disabled={busy || !draft.trim()}>
        {field?.type === 'file' ? 'Ask' : 'Send answer'}
      </button>
    </div>
  </form>;
}

/* Editing an earlier answer. When the person answered in their own words,
   those words are what gets edited; the reading is derived again from them. */
function EditAnswer({ entry, busy, initialWords = '', onSave, onDescribe, onCancel }) {
  const [value, setValue] = useState('');
  const [words, setWords] = useState(initialWords);
  const [picked, setPicked] = useState([]);
  const describable = ['choice', 'int', 'integer', 'float'].includes(entry.type);
  const cancel = <button className="chip ghost" type="button" disabled={busy} onClick={onCancel}>Cancel</button>;

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

/* One question drawn as a real control: every option visible, chosen ones marked. */
function FormControl({ row }) {
  const chosen = String(row.raw ?? '').split(',').map(s => s.trim()).filter(Boolean);
  const muted = row.state !== 'answered';

  if (row.options?.length) {
    const multi = row.multiple;
    return <ul className={`fld-options${multi ? ' multi' : ''}`}>
      {row.options.map(o => {
        const on = chosen.includes(o.value);
        return <li key={o.value} className={on ? 'on' : ''}>
          <span className={multi ? 'box' : 'dot'} aria-hidden="true">
            {on ? (multi ? <Icon name="check" size={10} stroke={3} /> : '') : ''}
          </span>
          <span className="opt-label">{o.label}</span>
        </li>;
      })}
    </ul>;
  }

  if (['boolean', 'bool'].includes(row.type))
    return <ul className="fld-options">
      {[['Yes', 'true'], ['No', 'false']].map(([label, v]) =>
        <li key={v} className={chosen.includes(v) ? 'on' : ''}>
          <span className="dot" aria-hidden="true" /><span className="opt-label">{label}</span>
        </li>)}
    </ul>;

  const long = ['longtext', 'textbox'].includes(row.type);
  if (row.type === 'file') {
    const names = String(row.value || '').split(',').map(s => s.trim()).filter(Boolean);
    return <ul className="fld-files">
      {names.length ? names.map(n => <li key={n}><Icon name="file" size={14} />{n}</li>)
        : <li className="none"><Icon name="file" size={14} />No files attached</li>}
    </ul>;
  }
  const unit = row.hours ? 'hours / week' : row.type === 'date' ? 'month' : null;
  return <div className={`fld-input${long ? ' tall' : ''}${muted ? ' muted' : ''}`}>
    <span className="fld-text">{row.value || (row.state === 'answered' ? '—' : '')}</span>
    {unit && <span className="fld-unit">{unit}</span>}
  </div>;
}

/* The application drawn as a form: every question, every option, what was chosen. */
function FormPanel({ answers, form, current, editing, busy, onEdit, onSave, onDescribe, onCancel, onClose }) {
  const [showAll, setShowAll] = useState(true);
  const byId = Object.fromEntries(answers.map(a => [a.id, a]));

  const rows = (form?.length ? form : []).map(f => {
    const a = byId[f.id];
    return {
      ...f, ...(a || {}),
      state: a ? 'answered' : f.pending ? 'current' : f.included ? 'upcoming' : 'excluded'
    };
  });
  const shown = showAll ? rows : rows.filter(r => r.state === 'answered' || r.state === 'current');
  const done = rows.filter(r => r.state === 'answered').length;
  const live = rows.filter(r => r.state !== 'excluded').length;

  return <aside className="form-panel" aria-label="Application form overview">
    <header className="form-panel-head">
      <div className="fp-title">
        <span className="form-panel-eyebrow">SU · DISABILITY ALLOWANCE</span>
        <h2>Form overview</h2>
      </div>
      <button className="form-panel-close" aria-label="Close form overview" onClick={onClose}>✕</button>
    </header>

    <div className="fp-progress">
      <div className="fp-bar"><i style={{ width: `${live ? (done / live) * 100 : 0}%` }} /></div>
      <span>{done} of {live} answered</span>
      <button className="form-scope" aria-pressed={showAll}
        onClick={() => setShowAll(v => !v)}>{showAll ? 'Answered only' : 'All questions'}</button>
    </div>

    <div className="form-panel-body">
      {shown.length === 0 && <p className="form-empty">No fields answered yet.</p>}
      {shown.map((row, i) => <section className={`fld ${row.state}`} key={row.id}>
        <div className="fld-head">
          <span className="fld-num">{String(i + 1).padStart(2, '0')}</span>
          <label className="fld-label">{row.label}</label>
          {row.state === 'answered' && !editing &&
            <button className="form-edit" disabled={busy} onClick={() => onEdit(row.id)} aria-label="Edit answer" title="Edit answer">
              <Icon name="edit" size={13} stroke={2} />
            </button>}
          {row.state === 'current' && <span className="fld-pill now">Current</span>}
          {row.state === 'upcoming' && <span className="fld-pill">Upcoming</span>}
          {row.state === 'excluded' && <span className="fld-pill off">Not relevant</span>}
        </div>
        {editing === row.id && row.state === 'answered'
          ? <EditAnswer entry={row} busy={busy} onSave={onSave} onDescribe={onDescribe} onCancel={onCancel} />
          : <FormControl row={row} />}
        {row.state === 'excluded' &&
          <p className="fld-why">Excluded based on a previous answer.</p>}
      </section>)}
    </div>

    <footer className="form-panel-foot">Demonstration preview. Nothing is submitted to public authorities.</footer>
  </aside>;
}

// 5 logical stages of the SU disability allowance workflow
const STAGES = [
  { id: 1, title: 'Studieoplysninger', subtitle: 'Indskrivning & uddannelsessted' },
  { id: 2, title: 'Funktionsnedsættelse', subtitle: 'Lidelsens art & varighed' },
  { id: 3, title: 'Arbejdsevne & job', subtitle: 'Erhvervserfaring & timer' },
  { id: 4, title: 'Lægelig dokumentation', subtitle: 'Speciallægeerklæring' },
  { id: 5, title: 'Gennemse & bekræft', subtitle: 'Samlet oversigt & kvittering' },
];

function getStageIndex(state) {
  if (!state) return 0;
  if (state.status === 'review' || state.status === 'complete' || state.status === 'declined') return 4;
  const f = state.field;
  if (!f) return 0;
  const t = (f.type || '').toLowerCase();
  const l = (f.label || '').toLowerCase();
  if (t === 'file' || t === 'demo_file' || l.includes('dokumentation') || l.includes('fil') || l.includes('attest') || l.includes('læge') || l.includes('attach')) return 3;
  if (l.includes('arbejde') || l.includes('job') || l.includes('timer') || l.includes('hour') || l.includes('beskæftigelse')) return 2;
  if (l.includes('funktionsnedsættelse') || l.includes('varig') || l.includes('medfødt') || l.includes('tillaeg') || l.includes('impairment') || l.includes('lidelse') || l.includes('diagnose')) return 1;
  return 0;
}

// Left sidebar: anchors the phases and documentation guidelines exactly as requested
function ApplicationSidebar({ state, answeredCount, onReset, busy }) {
  const currentStage = getStageIndex(state);
  const ended = state && ['complete', 'declined'].includes(state.status);

  return (
    <aside className="application-sidebar" aria-label="Faser i ansøgningen og vejledning">
      {/* 5-Stage Stepper Roadmap */}
      <div className="sidebar-card stepper-card">
        <div className="stepper-header">
          <h3>Faser i ansøgningen</h3>
          {state && <span className="stepper-badge">{answeredCount} svar</span>}
        </div>
        <ol className="stepper-list">
          {STAGES.map((stage, idx) => {
            const isCompleted = currentStage > idx || ended;
            const isCurrent = currentStage === idx && !ended;
            return (
              <li
                key={stage.id}
                className={`stepper-item ${isCompleted ? 'completed' : ''} ${isCurrent ? 'current' : ''}`}
              >
                <span className="stepper-marker" aria-hidden="true">
                  {isCompleted ? <Icon name="check" size={12} stroke={3} /> : stage.id}
                </span>
                <div className="stepper-text">
                  <span className="stepper-title">{stage.title}</span>
                  <span className="stepper-subtitle">{stage.subtitle}</span>
                </div>
                {isCurrent && <span className="stepper-now-indicator">I gang</span>}
              </li>
            );
          })}
        </ol>
      </div>

      {/* Guidelines & Documentation Help */}
      <div className="sidebar-card guide-card">
        <h4><Icon name="info" size={15} /> Krav til dokumentation</h4>
        <p>
          Dokumentationen skal beskrive dine <em>konkrete funktionstab</em> i relation til at varetage et studiejob.
          En lægelig diagnose alene er sjældent tilstrækkelig.
        </p>
      </div>

      {/* Support Hotline */}
      <div className="sidebar-card contact-card">
        <h4>Spørgsmål til SU?</h4>
        <p className="contact-text">Man–fre 9.00–15.00 · Tlf. 72 31 79 00</p>
      </div>

      {/* Quick sidebar actions: Save session & Start again */}
      <div className="sidebar-actions">
        {state && (
          <>
            <button
              type="button"
              className="sidebar-save-btn"
              title="Save session (demo preview)"
              onClick={() => {
                alert('Session saved. (Demo preview: progress is stored in your current browser session)');
              }}
            >
              <Icon name="save" size={15} stroke={2} />
              <span>Save session</span>
            </button>
            <button
              type="button"
              className="sidebar-reset-btn"
              disabled={busy}
              onClick={onReset}
            >
              <Icon name="restart" size={14} />
              <span>Start again</span>
            </button>
          </>
        )}
      </div>
    </aside>
  );
}

export function ApplicationDemo() {
  const [state, setState] = useState(null);
  const [thread, setThread] = useState([]);
  const [match, setMatch] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState('');
  const [interp, setInterp] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const sid = useRef(null);
  if (sid.current === null) sid.current = newSessionId();
  const inflight = useRef(false);
  const tail = useRef(null);

  useEffect(() => { tail.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [thread, state, match]);

  const add = (entry) => setThread(t => [...t, { ...entry, key: `${t.length}-${entry.kind}` }]);

  // A question becomes a bubble the moment it is asked, so the conversation
  // reads as a thread from the first turn instead of a lone form card.
  const asked = useRef(null);
  useEffect(() => {
    const id = state?.prompt_id;
    if (!id || asked.current === id) return;
    asked.current = id;
    const text = state.status === 'review' ? 'Please review your answers below, and then send the demo application.' : state.field?.label;
    if (text) setThread(t => [...t, { kind: 'question', text, key: `${t.length}-question` }]);
  }, [state?.prompt_id]);

  async function request(path, payload) {
    if (inflight.current) return null;
    inflight.current = true; setBusy(true); setError('');
    try {
      const r = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Session-ID': sid.current },
        body: JSON.stringify(payload)
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'Could not complete action.');
      return data;
    } catch (e) { setError(e.message); return null; }
    finally { inflight.current = false; setBusy(false); }
  }

  function start() {
    if (sessionStorage.getItem('application-demo-continue') !== 'yes') {
      location.assign(demoUrl('/mitid')); return;
    }
    request('/application/init', { graph_id: graph(), demo_continue: true })
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
      source: field.type === 'file' ? 'attachment' : 'chosen' }).then(data => {
      if (data) setState(data);
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
  // the current field type is; that is the reliable route to the FAQ and does
  // not depend on finding the button.
  function send(text) {
    const field = state.field;
    setDraft(''); setInterp(null);
    if (/\?\s*$/.test(text)) { ask(text); return; }
    if (field?.type === 'file') { ask(text); return; }
    add({ kind: 'reply', text, fieldId: field?.id, typedText: text });
    if (field && INTERPRETABLE.includes(field.type)) {
      request('/application/interpret', { prompt_id: state.prompt_id, message: text }).then(data => {
        if (!data) return;
        if (data.status === 'interpreted') {
          setInterp(data);
        } else {
          askNow(text);
        }
      });
      return;
    }
    request('/application/answer', { prompt_id: state.prompt_id, value: normalise(field, text) }).then(data => {
      if (data) setState(data);
    });
  }

  function confirmInterp(data) {
    const { value, field_id: target, display: shown } = data;
    const wasEdit = !!editing || !!data.wasEdit;
    const editTarget = data.editFieldId || editing || target;
    setInterp(null); setEditing(null);
    if (wasEdit) {
      request('/application/edit', { field_id: editTarget, value }).then(res => {
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
    request('/application/answer', { prompt_id: state.prompt_id, value, source: 'interpreted' }).then(res => {
      if (res) setState(res);
    });
  }

  function rejectInterp() {
    if (interp?.field_id && !interp.wasEdit) {
      const target = interp.field_id;
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
    request('/application/interpret', { field_id: fieldId, message: words }).then(data => {
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
    request('/application/edit', { field_id: editing, value }).then(data => {
      if (data) rewind(editing, data);
    });
  }

  function askNow(message) {
    request('/application/ask', { message }).then(data => {
      if (!data) return;
      if (data.status === 'faq_no_match') { add({ kind: 'notice', text: data.response }); return; }
      setMatch(data);
    });
  }

  function ask(message) {
    add({ kind: 'ask', text: message });
    askNow(message);
  }

  function confirmMatch(candidate_key, question) {
    setMatch(null);
    request('/application/confirm', { match_id: match.match_id, candidate_key }).then(data => {
      if (!data) return;
      add({ kind: 'faq', question: data.faq_question || question, text: data.faq_response });
      setState(data);
    });
  }

  const ended = state && ['complete', 'declined'].includes(state.status);
  const review = state && state.status === 'review';

  function handleReset() {
    if (window.confirm('Start a new demo and discard this screen’s answers?')) {
      setState(null); setThread([]); setMatch(null); setInterp(null); setError(''); sid.current = newSessionId();
    }
  }

  return (
    <main className={`application-page ${showForm ? 'with-form' : ''}`}>
      {/* Top Application Bar */}
      <header className="application-header">
        <div className="app-header-left">
          <a href={demoUrl('/demo')} className="back-link">
            <Icon name="chevron" size={16} />
            <span>← Back to SU-support</span>
          </a>
          <span className="app-header-divider">|</span>
          <span className="app-header-title">APPLICATION DEMO</span>
        </div>
        <div className="app-header-right">
          {state && !ended && (
            <button
              type="button"
              className="header-form-toggle"
              aria-pressed={showForm}
              onClick={() => setShowForm((v) => !v)}
            >
              <Icon name="card" size={15} />
              <span>{showForm ? 'Hide form' : 'View form'}</span>
            </button>
          )}
        </div>
      </header>

      {/* Grid Layout: Normal (Sidebar + Center) vs Form Open (50% Application + 50% Form) */}
      <div className="application-layout-grid">
        {/* Left Column: Phases and Documentation (hidden when form is open) */}
        {!showForm && (
          <ApplicationSidebar
            state={state}
            answeredCount={state?.answers?.length || 0}
            onReset={handleReset}
            busy={busy}
          />
        )}

        {/* Center / Left Half: The Guided Conversational Interface */}
        <section className="application-shell">
          <div className="application-topline">
            {state && !ended && (
              <span className="dialog-status-pill">
                <span className="live-dot" /> Active session
              </span>
            )}
          </div>

          <h1 className="application-title">Apply for disability allowance</h1>
          <p className="application-notice">
            <Icon name="info" size={16} />
            <span>
              Demonstration only. Use fictional information. Answers are sent to the DCR simulation; file contents are not uploaded. Nothing is submitted to an authority.
            </span>
          </p>

          {!state && (
            <div className="application-start-card">
              <h2>Ready to try the application?</h2>
              <p>
                We’ll guide you through the questions one step at a time. You can ask questions about the rules or
                change previous answers whenever you like.
              </p>
              <button className="primary-start-btn" disabled={busy} onClick={start}>
                Start demo application →
              </button>
            </div>
          )}

          {state && (
            <div className="chat">
              {thread.map((m) => {
                if (m.kind === 'question') {
                  return (
                    <div key={m.key} className="bubble bot">
                      {m.text}
                    </div>
                  );
                }

                if (m.kind === 'reply') {
                  const entry = (state.answers || []).find((a) => a.id === m.fieldId);
                  if (editing && editing === m.fieldId && entry) {
                    return (
                      <div key={m.key} className="bubble bot editing">
                        <span className="edit-tag">Editing answer · {entry.label}</span>
                        <EditAnswer
                          entry={entry}
                          busy={busy}
                          initialWords={m.typedText || ''}
                          onSave={saveEdit}
                          onDescribe={describeEdit}
                          onCancel={() => setEditing(null)}
                        />
                      </div>
                    );
                  }

                  return (
                    <div key={m.key} className="turn-user">
                      <div className="bubble user">
                        <span className="user-reply-text">{m.text}</span>
                        {entry && !editing && !ended && (
                          <button
                            className="edit-link"
                            disabled={busy}
                            onClick={() => setEditing(m.fieldId)}
                            aria-label="Edit answer"
                            title="Edit answer"
                          >
                            <Icon name="edit" size={13} stroke={2} />
                          </button>
                        )}
                      </div>
                      {m.interpreted && (
                        <p className="read-as">
                          <span className="read-as-label">Interpreted as:</span> {m.interpreted}
                        </p>
                      )}
                    </div>
                  );
                }

                if (m.kind === 'ask') {
                  return (
                    <div key={m.key} className="bubble user aside">
                      <span className="aside-tag">Question for FAQ</span>
                      {m.text}
                    </div>
                  );
                }

                if (m.kind === 'notice') {
                  return (
                    <div key={m.key} className="bubble bot notice">
                      {m.text}
                    </div>
                  );
                }

                return (
                  <div key={m.key} className="bubble bot faq">
                    <span className="faq-tag">From FAQ · {m.question}</span>
                    <AnswerBody html={m.text} />
                  </div>
                );
              })}

              {!ended &&
                !match &&
                !interp &&
                (review ? (
                  <div className="chat-choices">
                    <button className="chip primary send-btn" disabled={busy} onClick={() => answer('send')}>
                      Send demo application
                    </button>
                  </div>
                ) : (
                  <Answer field={state.field} busy={busy} onSubmit={answer} />
                ))}

              {interp && (
                <div className="bubble bot interp">
                  <span className="interp-eyebrow">Suggested answer based on your description</span>
                  <span className="faq-tag">{interp.display}</span>
                  <div className="chat-choices" style={{ marginTop: '12px' }}>
                    <button className="chip primary" disabled={busy} onClick={() => confirmInterp(interp)}>
                      Use this answer
                    </button>
                    <button className="chip ghost" disabled={busy} onClick={rejectInterp}>
                      Choose another
                    </button>
                  </div>
                </div>
              )}

              {match && (
                <div className="bubble bot match">
                  <p className="chat-question">{match.response}</p>
                  <div className="chat-choices">
                    {match.candidates.map((c) => (
                      <button
                        className="chip"
                        key={c.candidate_key}
                        disabled={busy}
                        onClick={() => confirmMatch(c.candidate_key, c.question)}
                      >
                        {c.question}
                      </button>
                    ))}
                    <button className="chip ghost" disabled={busy} onClick={() => setMatch(null)}>
                      None of these
                    </button>
                  </div>
                </div>
              )}

              {ended && (
                <div className="application-card application-success" role="status">
                  <span className="application-tick">{state.status === 'complete' ? '✓' : '—'}</span>
                  <h2>{state.status === 'complete' ? 'Demo complete' : 'Application not sent'}</h2>
                  <p>{state.response}</p>
                  <strong className="success-demo-notice">{state.demo_notice}</strong>
                  <p>
                    <a href={demoUrl('/demo')} className="return-faq-link">
                      Return to the FAQ →
                    </a>
                  </p>
                </div>
              )}

              <div ref={tail} />
            </div>
          )}

          {state && !ended && !match && !editing && !interp && (
            <Composer
              field={state.field}
              busy={busy}
              draft={draft}
              setDraft={setDraft}
              onSend={send}
              onAsk={(t) => {
                setDraft('');
                ask(t);
              }}
            />
          )}

          {state?.answers?.length > 0 && !showForm && (
            <details className="application-history" open={review}>
              <summary>Your answers ({state.answers.length})</summary>
              <dl>
                {state.answers.map((a, i) => (
                  <div key={i}>
                    <dt>{a.label}</dt>
                    <dd>{a.value}</dd>
                  </div>
                ))}
              </dl>
            </details>
          )}

          {error && <p className="application-error" role="alert">{error}</p>}
          {busy && <p className="chat-busy" role="status">Checking next step…</p>}
        </section>

        {/* Right Half: Live Form Review Panel (when toggled on) */}
        {showForm && state && (
          <FormPanel
            answers={state.answers || []}
            form={state.form || []}
            current={!ended && !review ? state.field : null}
            editing={editing}
            busy={busy}
            onEdit={setEditing}
            onSave={saveEdit}
            onDescribe={describeEdit}
            onCancel={() => setEditing(null)}
            onClose={() => setShowForm(false)}
          />
        )}
      </div>
    </main>
  );
}
