import { createElement, useEffect, useRef, useState } from 'react';
import Icon from './Icon';
import botIcon from './assets/icons8-bot.gif';

const newId = () => globalThis.crypto?.randomUUID?.() || `su-${Date.now()}-${Math.random()}`;
const label = (option) => option.question || '';
const isUtility = (option) => ['back to topics', 'proceed to application'].includes(label(option).trim().toLowerCase());
const choicePayload = (option, menu) => ({ event_id: option.event_id || menu.event_id, value: option.value });

// Preserve API answer text and basic formatting without allowing executable HTML.
function Answer({ html }) {
  const document = new DOMParser().parseFromString(html || '', 'text/html');
  function render(node, key) {
    if (node.nodeType === 3) return node.textContent;
    if (node.nodeType !== 1 || ['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'TEMPLATE'].includes(node.tagName)) return null;
    const children = Array.from(node.childNodes, (child, index) => render(child, index));
    const tag = node.tagName.toLowerCase();
    if (!['p', 'br', 'strong', 'em', 'b', 'i', 'ul', 'ol', 'li', 'a'].includes(tag)) return children;
    const props = { key };
    if (tag === 'a') {
      const href = node.getAttribute('href') || '';
      if (/^(https?:\/\/|mailto:)/i.test(href.trim())) Object.assign(props, { href, target: '_blank', rel: 'noopener noreferrer' });
    }
    return createElement(tag, props, ...(tag === 'br' ? [] : children));
  }
  return <div className="answer-card">{Array.from(document.body.childNodes, (node, index) => render(node, index))}</div>;
}

// An application question rendered as a chat turn. Choices become buttons;
// everything else takes a typed answer.
function ApplicationField({ data, active, onAction }) {
  const [value, setValue] = useState('');
  const field = data.field;
  useEffect(() => setValue(''), [data.prompt_id]);
  const send = (raw) => onAction({ prompt_id: data.prompt_id, value: field.type === 'date' ? `${raw}-01` : raw },
                                 field.type === 'choice' ? (field.options.find(o => o.value === raw)?.label ?? raw)
                                 : ['bool', 'boolean'].includes(field.type) ? (raw === 'true' ? 'Yes' : 'No') : raw);
  if (field.type === 'submit')
    return <div className="choice-grid"><button type="button" disabled={!active} onClick={() => send('send')}>Send demo application</button></div>;
  if (field.type === 'choice')
    return <div className="choice-grid">{field.options.map(o =>
      <button key={o.value} type="button" disabled={!active} onClick={() => send(o.value)}>{o.label}</button>)}</div>;
  if (['bool', 'boolean'].includes(field.type))
    return <div className="choice-grid">{[['Yes', 'true'], ['No', 'false']].map(([text, v]) =>
      <button key={v} type="button" disabled={!active} onClick={() => send(v)}>{text}</button>)}</div>;
  const kind = field.type === 'date' ? 'month'
    : ['int', 'integer', 'float'].includes(field.type) ? 'number'
      : field.type === 'email' ? 'email' : 'text';
  const long = ['longtext', 'textbox'].includes(field.type);
  return <form className="application-turn" onSubmit={e => { e.preventDefault(); if (value.trim()) send(value.trim()); }}>
    {long
      ? <textarea value={value} maxLength={4000} disabled={!active} onChange={e => setValue(e.target.value)} />
      : <input type={kind} value={value} disabled={!active}
          step={field.type === 'float' ? 'any' : undefined}
          min={field.hours ? 0 : undefined} max={field.hours ? 168 : undefined}
          maxLength={field.type === 'demo_file' ? 200 : field.type === 'text' ? 50 : undefined}
          onChange={e => setValue(e.target.value)} />}
    <button type="submit" disabled={!active || !value.trim()}>Continue</button>
  </form>;
}

function Reply({ data, active, onAction }) {
  const menus = data.navigation || [];
  const menu = menus.find(item => item.event_id === data.event_id) || menus.find(item => !item.is_home) || menus[0];
  const options = (menu?.options || []).filter(option => !isUtility(option));
  const matching = ['confirm_match', 'clarify_match'].includes(data.status);
  const applying = data.application === true && !!data.field;
  const finished = data.application === true && ['complete', 'declined'].includes(data.status);
  const button = (key, text, payload) => <button key={key} type="button" disabled={!active} onClick={() => onAction(payload, text)}>{text}</button>;
  return <div className="chat-row assistant"><div className="assistant-mark"><img src={botIcon} width="18" height="18" alt="" /></div><div className="assistant-content">
    {data.status === 'answer' ? <Answer html={data.answer || data.response} /> : applying ? <div className="chat-bubble">{data.field.label}</div> : data.response && <div className="chat-bubble">{data.response}</div>}
    {applying && <ApplicationField data={data} active={active} onAction={onAction} />}
    {finished && <p className="chat-follow-up">{data.demo_notice}</p>}
    {data.follow_up && <p className="chat-follow-up">{data.follow_up}</p>}
    {matching && <>
      {data.status === 'confirm_match' && <p className="matched-question">{data.candidates?.[0]?.question}</p>}
      <div className="choice-grid">{(data.candidates || []).map(candidate => button(candidate.candidate_key, data.status === 'confirm_match' ? 'Yes, show the answer' : candidate.question, { action: 'confirm', match_id: data.match_id, candidate_key: candidate.candidate_key }))}
      {button('reject', 'No — let me rephrase', { action: 'reject', match_id: data.match_id })}</div>
    </>}
    {!matching && !applying && options.length > 0 && <>
      {data.status === 'answer' && !data.topic_explored && !menu.is_home && <p className="topic-label">More questions about {data.topic_name || 'this topic'}</p>}
      <div className={`choice-grid ${menu.is_home ? 'topic-choices' : ''}`}>{options.map(option => button(`${option.event_id}:${option.value}`, label(option), choicePayload(option, menu)))}</div>
    </>}
    {data.actions?.length > 0 && <div className="choice-grid">{data.actions.filter(item => item.action !== 'topics').map(item => button(item.action, item.label, { action: item.action }))}</div>}
  </div></div>;
}

export default function SupportChat() {
  const [open, setOpen] = useState(false);
  const [sizing, setSizing] = useState(false);
  const [size, setSize] = useState({ width: 480, height: 730 });
  const SIZE_LIMITS = { minWidth: 360, maxWidth: 760, minHeight: 440, maxHeight: 900 };
  const dragFrom = useRef(null);

  // The panel is anchored bottom-right, so the grip sits on the top-left
  // corner and dragging away from the anchor grows it. Clamped to the same
  // bounds as the sliders, and to the viewport.
  function gripDown(event) {
    event.preventDefault();
    dragFrom.current = { x: event.clientX, y: event.clientY, ...size };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function gripMove(event) {
    const from = dragFrom.current;
    if (!from) return;
    const clamp = (value, low, high) => Math.min(Math.max(value, low), high);
    setSize({
      width: clamp(from.width + (from.x - event.clientX), SIZE_LIMITS.minWidth,
                   Math.min(SIZE_LIMITS.maxWidth, window.innerWidth - 48)),
      height: clamp(from.height + (from.y - event.clientY), SIZE_LIMITS.minHeight,
                    Math.min(SIZE_LIMITS.maxHeight, window.innerHeight - 120))
    });
  }
  const gripUp = () => { dragFrom.current = null; };
  const [messages, setMessages] = useState([]);
  const [navigation, setNavigation] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const session = useRef(newId());
  const busyRef = useRef(false);
  const initialized = useRef(false);
  const controller = useRef(null);
  const launcher = useRef(null);
  const panel = useRef(null);
  const inputRef = useRef(null);
  const scrollRef = useRef(null);

  async function request(path, payload, text) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError('');
    if (text) setMessages(current => [...current, { id: newId(), text }]);
    const abort = new AbortController(); controller.current = abort;
    try {
      const response = await fetch(path, { method: 'POST', signal: abort.signal, headers: { 'Content-Type': 'application/json', 'X-Session-ID': session.current }, body: JSON.stringify(payload) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'The chat could not complete your request.');
      if (!data.faq) throw new Error('This chat needs a FAQ graph. Please check the selected graph.');
      setMessages(current => [...current, { id: newId(), data }]);
      if (data.navigation) setNavigation(data.navigation);
      setReady(!data.error_code);
      if (data.error_code) setError('Please start a new chat to continue.');
    } catch (failure) {
      if (failure.name !== 'AbortError') { setError('We couldn’t complete that request. Please start a new chat to continue.'); setReady(false); }
    } finally {
      busyRef.current = false; setBusy(false);
    }
  }
  function initialize() {
    if (busyRef.current) return;
    initialized.current = true; session.current = newId(); setReady(false); setMessages([]); setNavigation([]); setInput('');
    const graph = new URLSearchParams(window.location.search).get('graphid') || '2012701';
    request('/init', { graph_id: graph });
  }
  function show() { setOpen(true); if (!initialized.current) initialize(); }
  function close() { setOpen(false); launcher.current?.focus(); }
  const submit = (payload, text) => {
    if (!ready) return;
    // Proceeding to the application leaves the chat entirely: MitID first, then
    // the application start page, then the conversational application. The FAQ
    // simulation is deliberately left untouched; /application/init starts its
    // own. The inline handover below remains only as a safety net.
    if (text?.trim().toLowerCase() === 'proceed to application') {
      const graph = new URLSearchParams(window.location.search).get('graphid') || '2012701';
      window.location.assign(`/mitid?graphid=${encodeURIComponent(graph)}`);
      return;
    }
    request('/chat', payload, text);
  };
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => { if (open) { if (!busy && ready) inputRef.current?.focus(); else panel.current?.querySelector('button:not(:disabled)')?.focus(); } }, [open, busy, ready]);
  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = messages.length <= 1 ? 0 : scrollRef.current.scrollHeight; }, [open, messages, busy, error]);
  function keyboard(event) {
    if (event.key === 'Escape') { event.preventDefault(); close(); }

  }
  const allOptions = navigation.flatMap(menu => (menu.options || []).map(option => ({ option, menu })));
  const back = allOptions.find(({ option }) => label(option).trim().toLowerCase() === 'back to topics');
  const apply = allOptions.find(({ option }) => label(option).trim().toLowerCase() === 'proceed to application');
  const disabled = busy || !ready;
  return <aside className="support-widget">
    <button ref={launcher} className="support-launcher" aria-label="Open SU-support" aria-expanded={open} onClick={show}>
      <span className="launcher-bot-wrap">
        <img src={botIcon} width="30" height="30" alt="" />
      </span>
      <span className="launcher-label">Ask SU-support</span>
    </button>
    {open && <><section ref={panel} className="support-panel" style={{ "--panel-width": `${size.width}px`, "--panel-height": `${size.height}px` }} role="dialog" aria-modal="false" aria-label="SU-support chat" onKeyDown={keyboard}>
      <div className="resize-grip" role="separator" aria-label="Resize chat" title="Drag to resize"
        onPointerDown={gripDown} onPointerMove={gripMove} onPointerUp={gripUp} onPointerCancel={gripUp} />
      <header className="support-header">
        <div className="support-brand">
          <span className="support-avatar">
            <img src={botIcon} width="26" height="26" alt="" />
          </span>
          <div>
            <strong>SU-support</strong>
            <span>Your disability allowance guide · Online</span>
          </div>
        </div>
        <div className="support-tools">
          <button type="button" className="support-tool size-toggle" aria-label="Adjust chat size" aria-expanded={sizing} onClick={() => setSizing(value => !value)}>↔</button>
          <button autoFocus type="button" className="support-tool" aria-label="Start a new chat" onClick={initialize} disabled={busy}><Icon name="restart" size={20} /></button>
          <button type="button" className="support-tool" aria-label="Close SU-support" onClick={close}><Icon name="close" size={22} /></button>
        </div>
      </header>
      {sizing && <div className="support-size-controls"><label>Width <input aria-label="Chat width" type="range" min="360" max="760" step="10" value={size.width} onChange={event => setSize(current => ({ ...current, width: Number(event.target.value) }))} /></label><label>Height <input aria-label="Chat height" type="range" min="440" max="900" step="10" value={size.height} onChange={event => setSize(current => ({ ...current, height: Number(event.target.value) }))} /></label><button onClick={() => setSize({ width: 480, height: 730 })}>Reset size</button></div>}
      <div className="support-messages" ref={scrollRef} role="log" aria-live="polite" aria-relevant="additions">
        <div className="chat-intro"><h2>Let’s find your answer.</h2><p>Choose a topic or ask a question about disability allowance.</p></div>
        {messages.map((message, index) => message.data ? <Reply key={message.id} data={message.data} active={!disabled && index === messages.length - 1} onAction={submit} /> : <div key={message.id} className="chat-row user"><div className="chat-bubble">{message.text}</div></div>)}
        {busy && <div className="typing-indicator" role="status" aria-label="SU-support is replying"><span /><span /><span /></div>}
        {error && <div className="support-error" role="alert"><p>{error}</p><button type="button" onClick={initialize}>Start a new chat</button></div>}
      </div>
      <nav className="support-navigation" aria-label="Chat navigation"><button disabled={disabled} onClick={() => submit(back ? choicePayload(back.option, back.menu) : { action: 'topics' }, 'Back to topics')}>← Back to topics</button>{apply && <button className="apply" disabled={disabled} onClick={() => submit(choicePayload(apply.option, apply.menu), label(apply.option))}>Proceed to application ↗</button>}</nav>
      <form className="support-composer" onSubmit={event => { event.preventDefault(); if (!input.trim() || disabled || busyRef.current) return; submit({ message: input.trim() }, input.trim()); setInput(''); }}><input ref={inputRef} value={input} onChange={event => setInput(event.target.value)} placeholder="Type your question…" aria-label="Message SU-support" disabled={disabled} /><button type="submit" aria-label="Send message" disabled={disabled || !input.trim()}><Icon name="send" size={20} /></button></form>
      <p className="support-note">Official answers from the disability allowance FAQ</p>
    </section></>}
  </aside>;
}
