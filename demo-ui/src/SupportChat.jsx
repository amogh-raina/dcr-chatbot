import { createElement, useEffect, useRef, useState } from 'react';
import Icon from './Icon';

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

function Reply({ data, active, onAction }) {
  const menus = data.navigation || [];
  const menu = menus.find(item => item.event_id === data.event_id) || menus.find(item => !item.is_home) || menus[0];
  const options = (menu?.options || []).filter(option => !isUtility(option));
  const matching = ['confirm_match', 'clarify_match'].includes(data.status);
  const button = (key, text, payload) => <button key={key} type="button" disabled={!active} onClick={() => onAction(payload, text)}>{text}</button>;
  return <div className="chat-row assistant"><div className="assistant-mark"><Icon name="message" size={16} /></div><div className="assistant-content">
    {data.status === 'answer' ? <Answer html={data.answer || data.response} /> : data.response && <div className="chat-bubble">{data.response}</div>}
    {data.follow_up && <p className="chat-follow-up">{data.follow_up}</p>}
    {matching && <>
      {data.status === 'confirm_match' && <p className="matched-question">{data.candidates?.[0]?.question}</p>}
      <div className="choice-grid">{(data.candidates || []).map(candidate => button(candidate.candidate_key, data.status === 'confirm_match' ? 'Yes, show the answer' : candidate.question, { action: 'confirm', match_id: data.match_id, candidate_key: candidate.candidate_key }))}
      {button('reject', 'No — let me rephrase', { action: 'reject', match_id: data.match_id })}</div>
    </>}
    {!matching && options.length > 0 && <>
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
  const submit = (payload, text) => { if (ready) request('/chat', payload, text); };
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
    <button ref={launcher} className="support-launcher" aria-label="Open SU-support" aria-expanded={open} onClick={show}><span className="launcher-symbol"><Icon name="message" size={27} /><i /></span><span>Ask SU-support</span></button>
    {open && <><section ref={panel} className="support-panel" style={{ "--panel-width": `${size.width}px`, "--panel-height": `${size.height}px` }} role="dialog" aria-modal="false" aria-label="SU-support chat" onKeyDown={keyboard}>
      <header className="support-header"><div className="support-brand"><span className="support-avatar"><Icon name="message" size={23} /></span><div><strong>SU-support</strong><span>Your disability allowance guide</span></div></div><div className="support-tools"><button type="button" className="support-tool size-toggle" aria-label="Adjust chat size" aria-expanded={sizing} onClick={() => setSizing(value => !value)}>↔</button><button autoFocus type="button" className="support-tool" aria-label="Start a new chat" onClick={initialize} disabled={busy}><Icon name="restart" size={20} /></button><button type="button" className="support-tool" aria-label="Close SU-support" onClick={close}><Icon name="close" size={22} /></button></div></header>
      {sizing && <div className="support-size-controls"><label>Width <input aria-label="Chat width" type="range" min="360" max="760" step="10" value={size.width} onChange={event => setSize(current => ({ ...current, width: Number(event.target.value) }))} /></label><label>Height <input aria-label="Chat height" type="range" min="440" max="900" step="10" value={size.height} onChange={event => setSize(current => ({ ...current, height: Number(event.target.value) }))} /></label><button onClick={() => setSize({ width: 480, height: 730 })}>Reset size</button></div>}
      <div className="support-messages" ref={scrollRef} role="log" aria-live="polite" aria-relevant="additions">
        <div className="chat-intro"><span className="intro-eyebrow">A LITTLE HELP, WHEN YOU NEED IT</span><h2>Let’s find your answer.</h2><p>Choose a topic or ask a question about disability allowance.</p></div>
        {messages.map((message, index) => message.data ? <Reply key={message.id} data={message.data} active={!disabled && index === messages.length - 1} onAction={submit} /> : <div key={message.id} className="chat-row user"><div className="chat-bubble">{message.text}</div></div>)}
        {busy && <div className="typing-indicator" role="status" aria-label="SU-support is replying"><span /><span /><span /></div>}
        {error && <div className="support-error" role="alert"><p>{error}</p><button type="button" onClick={initialize}>Start a new chat</button></div>}
      </div>
      <nav className="support-navigation" aria-label="Chat navigation"><button disabled={disabled} onClick={() => submit(back ? choicePayload(back.option, back.menu) : { action: 'topics' }, 'Back to topics')}>← Back to topics</button>{apply && <button disabled={disabled} onClick={() => submit(choicePayload(apply.option, apply.menu), label(apply.option))}>Proceed to application ↗</button>}</nav>
      <form className="support-composer" onSubmit={event => { event.preventDefault(); if (!input.trim() || disabled || busyRef.current) return; submit({ message: input.trim() }, input.trim()); setInput(''); }}><input ref={inputRef} value={input} onChange={event => setInput(event.target.value)} placeholder="Type your question…" aria-label="Message SU-support" disabled={disabled} /><button type="submit" aria-label="Send message" disabled={disabled || !input.trim()}><Icon name="send" size={20} /></button></form>
      <p className="support-note">Answers from the disability allowance FAQ</p>
    </section></>}
  </aside>;
}
