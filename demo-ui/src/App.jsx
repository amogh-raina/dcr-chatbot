import { useEffect, useRef, useState } from 'react';

const GRAPH_ID = '2012526';
const SESSION_KEY = 'su-support-session-id';

const navItems = ['SU', 'SU loan', 'SU abroad', 'Disability allowance', 'Foreign citizen', 'Support for parents', 'Other grants', 'Rates', 'Contact'];
const cards = [
  ['Conditions for receiving disability allowance', 'See which conditions you must meet to receive disability allowance.', 'scale'],
  ['How to apply for disability allowance', 'Learn how to apply and what documentation to include.', 'cursor'],
  ['About documentation', 'Your documentation must describe how your disability affects your ability to work alongside study.', 'file'],
  ['How we assess applications', 'Read what we consider when assessing whether you meet the requirements.', 'search'],
  ['Questions and answers', 'Find answers to the most frequently asked questions about disability allowance.', 'help'],
  ['Status of case processing', 'See the current status of applications for disability allowance.', 'clock'],
  ['Contact', 'Find out how to contact us about disability allowance.', 'message'],
  ['Reduced tax-free amount', 'Your tax-free amount is reduced when you receive disability allowance.', 'card'],
];

function Icon({ name, size = 22, stroke = 1.8 }) {
  const paths = {
    menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
    search: <><circle cx="11" cy="11" r="6" /><path d="m16 16 4 4" /></>,
    close: <><path d="m6 6 12 12M18 6 6 18" /></>,
    chevron: <path d="m9 18 6-6-6-6" />,
    down: <path d="m6 9 6 6 6-6" />,
    pause: <><path d="M8 6v12M16 6v12" /></>,
    play: <path d="m9 6 9 6-9 6V6Z" />,
    message: <path d="M20 11.5a7.5 7.5 0 0 1-8 7.48 8.8 8.8 0 0 1-3.9-.97L4 19l1.15-3.45A7.32 7.32 0 0 1 4 11.5 7.5 7.5 0 0 1 12 4a7.5 7.5 0 0 1 8 7.5Z" />,
    restart: <><path d="M20 11a8 8 0 1 1-2.34-5.66" /><path d="M20 4v7h-7" /></>,
    send: <path d="m3 4 18 8-18 8 3-8-3-8Zm3 8h15" />,
    scale: <><path d="M12 3v18M5 7h14M4 20h16" /><path d="m7 7-3 7h6L7 7Zm10 0-3 7h6l-3-7Z" /></>,
    cursor: <path d="m5 3 13 8-6 1 4 7-3 2-4-7-4 4V3Z" />,
    file: <><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v5h5M10 13h5M10 17h5" /></>,
    help: <><circle cx="12" cy="12" r="9" /><path d="M9.7 9a2.5 2.5 0 1 1 4.25 1.8c-1.3 1.2-1.95 1.8-1.95 3.2M12 17h.01" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.5 2" /></>,
    card: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 10h18" /></>,
  };
  return <svg className={`icon icon-${name}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.message}</svg>;
}

function newId() {
  return globalThis.crypto?.randomUUID?.() || `su-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function getSessionId(reset = false) {
  if (reset) sessionStorage.removeItem(SESSION_KEY);
  let id = sessionStorage.getItem(SESSION_KEY);
  if (!id) {
    id = `session_${newId()}`;
    sessionStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [slide, setSlide] = useState(2);
  const [paused, setPaused] = useState(false);
  return <main>
    <header className="site-header">
      <div className="utility-row">
        <div className="agency-mark" aria-label="Danish Agency for Higher Education and Science"><span className="crown">♕</span><span>Danish Agency for<br />Higher Education and Science</span></div>
        <div className="utility-links"><button className="mysu">mySU</button><a href="#contact">Contact</a><a href="#news">News</a><a href="#questions">Questions and answers</a><button className="icon-button search-button" aria-label="Open search" aria-expanded={searchOpen} onClick={() => setSearchOpen((value) => !value)}><Icon name={searchOpen ? 'close' : 'search'} /></button></div>
        <button className="mobile-menu icon-button" aria-label="Open navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen((value) => !value)}><Icon name={menuOpen ? 'close' : 'menu'} /></button>
      </div>
      {searchOpen && <form className="search-panel" onSubmit={(event) => event.preventDefault()}><Icon name="search" size={19} /><input autoFocus placeholder="What are you looking for?" aria-label="Search SU" /><button type="submit">Search</button></form>}
      <nav className={`main-nav ${menuOpen ? 'open' : ''}`}>{navItems.map((item) => <a key={item} href={item === 'Disability allowance' ? '#content' : '#'} className={item === 'Disability allowance' ? 'active' : ''}>{item}</a>)}</nav>
    </header>
    <section className="hero-shell" id="content">
      <div className="breadcrumb">You are here: <a href="#top">Front</a> <span>|</span> Disability allowance</div>
      <div className="hero">
        <div className="hero-copy">
          <h1>{slide === 0 ? 'Minimum requirements for your documentation' : slide === 1 ? 'Watch webinar about disability allowance' : 'Disability allowance'}</h1>
          {slide === 2 ? <><p>Disability allowance is for students in:</p><ul><li>higher education</li><li>Danish vocational education (EUD)</li></ul><p>who have a permanent mental or physical disability that makes it virtually impossible to hold a student job.</p></> : <p>{slide === 0 ? 'If you are applying for disability allowance, your documentation must meet some new minimum requirements.' : 'In the webinar we discuss who can apply, how to apply, and documentation requirements.'}</p>}
        </div>
        <div className={`hero-photo slide-${slide}`} aria-label="Students studying outdoors"><div className="photo-overlay">{slide === 0 ? 'Read about the requirements' : slide === 1 ? 'Watch webinar' : ''}</div><div className="slider-controls"><button aria-label={paused ? 'Play slideshow' : 'Pause slideshow'} onClick={() => setPaused((value) => !value)}><Icon name={paused ? 'play' : 'pause'} size={17} /></button>{[0, 1, 2].map((item) => <button key={item} onClick={() => setSlide(item)} className={`dot ${slide === item ? 'current' : ''}`} aria-label={`Show slide ${item + 1}`} />)}</div></div>
      </div>
    </section>
    <section className="card-area"><div className="cards">{cards.map(([title, description, icon]) => <article className="info-card" key={title}><Icon name={icon} size={48} stroke={1.35} /><h2><a href="#questions"><Icon name="chevron" size={20} />{title}</a></h2><p>{description}</p></article>)}</div>
      <div className="knowledge"><div><span className="eyebrow">WORTH KNOWING</span><h2>Reduced tax-free amount</h2><p>When you receive disability allowance, your tax-free amount is reduced. The allowance compensates for the income you could have earned from a student job.</p><p>The reduced amount also gives you an opportunity to test your working ability for a limited period.</p></div><article className="rates"><h2><a href="#rates"><Icon name="chevron" size={20} />Disability allowance rates</a></h2><p>See current and previous years&apos; rates for disability allowance.</p></article></div>
    </section>
    <section className="reform"><h2>Reform of the SU system in higher education</h2><p>New rules have been adopted for SU for higher education and private education.</p><p>The new rules will affect your SU from January 2027 if you start a new higher education on 1 July 2025 or later.</p><p>Get guidance from your educational institution so that you can plan your education and SU in relation to the new SU rules.</p></section>
    <footer id="contact">{[['Practical information', ['Your responsibility', 'Power of attorney', 'Complaint', 'Digital Post', 'Information about you']], ['More information', ['Links', 'About SU', 'Questions and answers', 'Contact', 'Paragraphs']], ['About su.dk', ['Accessibility statement', 'About su.dk', 'Feedback']]].map(([heading, links]) => <div key={heading}><h2>{heading}</h2>{links.map((link) => <a href="#" key={link}><Icon name="chevron" size={17} />{link}</a>)}</div>)}</footer>
    <SupportChat />
  </main>;
}

function SupportChat() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([{ id: 'welcome', kind: 'intro' }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef(null);
  const scrollRef = useRef(null);

  const request = async (path, body) => {
    const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Session-ID': getSessionId() }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'SU-support could not complete that request.');
    return data;
  };

  const initialize = async (reset = false) => {
    setLoading(true); setBusy(false); setError('');
    if (reset) getSessionId(true);
    try {
      const data = await request('/init', { graph_id: GRAPH_ID });
      setMessages([{ id: 'welcome', kind: 'intro' }, { id: newId(), kind: 'assistant', data }]);
    } catch (requestError) {
      setError(requestError.message || 'SU-support could not start. Please try again.');
    } finally { setLoading(false); }
  };

  useEffect(() => { initialize(); }, []);
  useEffect(() => {
    const onKeyDown = (event) => { if (event.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
  useEffect(() => { if (open) requestAnimationFrame(() => inputRef.current?.focus()); }, [open]);
  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }, [messages, loading, busy, error]);

  const submit = async (payload, label, endpoint = '/chat') => {
    if (busy || loading) return;
    setBusy(true); setError('');
    if (label) setMessages((current) => [...current, { id: newId(), kind: 'user', text: label }]);
    try {
      const data = await request(endpoint, { ...payload, request_id: newId() });
      setMessages((current) => [...current, { id: newId(), kind: 'assistant', data }]);
    } catch (requestError) {
      setError(requestError.message || 'SU-support could not complete that request.');
    } finally { setBusy(false); }
  };

  const sendText = async (event) => {
    event.preventDefault();
    const message = input.trim();
    if (!message) return;
    setInput('');
    await submit({ action: 'ask', message }, message);
  };

  return <aside className="support-widget">
    <button className="support-launcher" aria-label="Open SU-support" aria-expanded={open} onClick={() => setOpen(true)}><Icon name="message" size={27} /></button>
    {open && <section className="support-panel" role="dialog" aria-modal="true" aria-label="SU-support chat">
      <header className="support-header"><div className="support-brand"><span className="support-avatar"><Icon name="message" size={19} /></span><div><strong>SU-support</strong><span>Disability allowance guide</span></div></div><div className="support-tools"><button type="button" className="support-tool" aria-label="Restart SU-support" onClick={() => initialize(true)} disabled={loading || busy}><Icon name="restart" size={21} /></button><button type="button" className="support-tool" aria-label="Close SU-support" onClick={() => setOpen(false)}><Icon name="close" size={23} /></button></div></header>
      <div className="support-messages" ref={scrollRef} aria-live="polite">
        {messages.map((message, index) => <ChatMessage key={message.id} message={message} active={index === messages.length - 1} disabled={loading || busy} onAction={submit} />)}
        {loading && <div className="typing-indicator" aria-label="Loading answers"><span /><span /><span /></div>}
        {busy && <div className="typing-indicator" aria-label="SU-support is replying"><span /><span /><span /></div>}
        {error && <div className="support-error"><p>{error}</p><button type="button" onClick={() => initialize(true)}>Try again</button></div>}
      </div>
      <form className="support-composer" onSubmit={sendText}><input ref={inputRef} value={input} onChange={(event) => setInput(event.target.value)} placeholder={loading ? 'Loading SU-support…' : 'Type your question…'} aria-label="Message SU-support" disabled={loading || busy} /><button type="submit" aria-label="Send message" disabled={loading || busy || !input.trim()}><Icon name="send" size={20} /></button></form>
      <p className="support-note">SU-support provides guidance based on the disability allowance FAQ.</p>
    </section>}
  </aside>;
}

function ChatMessage({ message, active, disabled, onAction }) {
  if (message.kind === 'intro') return <div className="chat-row assistant"><div className="assistant-mark"><Icon name="message" size={17} /></div><div className="chat-bubble intro-bubble">Hi, I&apos;m SU-support. I can help you find answers about disability allowance.</div></div>;
  if (message.kind === 'user') return <div className="chat-row user"><div className="chat-bubble">{message.text}</div></div>;
  const data = message.data;
  const canAct = active && !disabled && !data.handoff;
  const controls = [];
  if (data.confirmation) {
    controls.push(<button key="yes" type="button" onClick={() => onAction({ token: data.confirmation.token, accept: true }, 'Yes', '/faq/confirm')} disabled={!canAct}>Yes</button>);
    controls.push(<button key="no" type="button" onClick={() => onAction({ token: data.confirmation.token, accept: false }, 'No', '/faq/confirm')} disabled={!canAct}>No</button>);
  } else if (!data.handoff) {
    const choices = data.screen === 'topics' ? data.topics : data.suggestions;
    (choices || []).forEach((choice) => controls.push(<button key={choice.value} type="button" onClick={() => onAction({ action: data.screen === 'topics' ? 'topic' : 'question', value: choice.value }, choice.label)} disabled={!canAct}>{choice.label}</button>));
    controls.push(<button key="topics" type="button" className="quiet-choice" onClick={() => onAction({ action: 'topics' }, 'Change topic')} disabled={!canAct}>Change topic</button>);
    controls.push(<button key="history" type="button" className="quiet-choice" onClick={() => onAction({ action: 'history' }, 'Previously viewed')} disabled={!canAct}>Previously viewed</button>);
    controls.push(<button key="apply" type="button" className="quiet-choice" onClick={() => onAction({ action: 'apply' }, 'Proceed to application')} disabled={!canAct}>Proceed to application</button>);
  }
  return <div className="chat-row assistant"><div className="assistant-mark"><Icon name="message" size={17} /></div><div className="assistant-content">{data.topic && data.screen === 'questions' && <p className="topic-label">{data.topic}</p>}{data.answer && <div className="answer-card"><strong>{data.answer.question}</strong><p>{data.answer.text}</p>{data.answer.sources && <details><summary>Sources</summary><p>{data.answer.sources}</p></details>}</div>}<div className="chat-bubble">{data.response}</div>{controls.length > 0 && <div className="choice-grid">{controls}</div>}</div></div>;
}

export default App;
