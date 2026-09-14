import { useState, useRef } from 'react';
import './application.css';
const graph = () => new URLSearchParams(location.search).get('graphid') || '2012701';
const demoUrl = (path) => `${path}?graphid=${encodeURIComponent(graph())}`;
export function MitIdDemo() {
  const [help, setHelp] = useState(false);
  const [lang,setLang] = useState('en');
  const da=lang==='da';
  function proceed(){sessionStorage.setItem('application-demo-continue','yes');location.assign(demoUrl('/application'));}
  return <main className="mitid-page"><header className="mitid-header"><div className="nemlog-logo"><span className="nem-mark">N</span>NemLog-in</div><label>🌐 <select aria-label="Language" value={lang} onChange={e=>setLang(e.target.value)}><option value="en">English</option><option value="da">Dansk</option></select></label></header>
    <section className="mitid-body"><div className="mitid-card"><div className="mitid-logo"><span className="mitid-dot"/><strong>MitID</strong></div><h1>{da?'Log ind med MitID':'Log in with MitID'}</h1><p className="intro">{da?'Demonstration af login før ansøgningen.':'A preview of the login step before your application.'}</p><div className="demo-note">{da?'Kun en demo. Ingen godkendelse eller indsamling af loginoplysninger.':'Visual-only demo — no authentication or collection of login details.'}</div><button className="continue" onClick={proceed}>{da?'Fortsæt demo':'Continue demo'}</button><button className="help-toggle" aria-expanded={help} onClick={()=>setHelp(!help)}>{da?'Hvordan fungerer demoen?':'How does this demo work?'} <span>⌄</span></button>{help&&<p className="demo-message">{da?'Du skal ikke åbne MitID eller oplyse loginoplysninger. Næste side viser ansøgningen på engelsk.':'You do not need the MitID app or any credentials. Continue to try the application using fictional information only.'}</p>}<div className="divider"/><p className="small"><a href={demoUrl('/demo')}>{da?'Tilbage til FAQ':'Back to the FAQ'}</a></p></div></section><footer className="mitid-footer">Independent demonstration — not a MitID or NemLog-in service.</footer></main>;
}
function Field({field,busy,onSubmit}){
 const [value,setValue]=useState('');
 const send=(e)=>{e.preventDefault();onSubmit(value);};
 if(field.type==='choice')return <div className="application-options">{field.options.map(o=><button disabled={busy} key={o.value} onClick={()=>onSubmit(o.value)}>{o.label}</button>)}</div>;
 if(['boolean','bool'].includes(field.type))return <div className="application-options">{[['Yes','true'],['No','false']].map(([label,v])=><button key={v} disabled={busy} onClick={()=>onSubmit(v)}>{label}</button>)}</div>;
 const kind=field.type==='date'?'month':['int','integer','float'].includes(field.type)?'number':field.type==='email'?'email':'text';
 return <form className="application-input" onSubmit={send}><label htmlFor="application-value">{field.type==='demo_file'?'Demo attachment filename':'Your answer'}</label>{['longtext','textbox'].includes(field.type)?<textarea id="application-value" required maxLength={4000} value={value} onChange={e=>setValue(e.target.value)}/>:<input autoFocus id="application-value" required type={kind} value={value} step={field.type==='float'?'any':undefined} min={field.hours?0:undefined} max={field.hours?168:undefined} maxLength={field.type==='demo_file'?200:field.type==='text'?50:undefined} onChange={e=>setValue(e.target.value)}/>}
 {field.type==='demo_file'&&<><p>No upload takes place. Enter a fictional filename or select a sample file; only its name is recorded.</p><input aria-label="Choose a sample attachment" type="file" onChange={e=>setValue(e.target.files?.[0]?.name||'')}/></>}
 <button disabled={busy||!value.trim()} type="submit">Continue →</button></form>;
}
export function ApplicationDemo(){
 const [state,setState]=useState(null);const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 const sid=useRef(crypto.randomUUID());const inflight=useRef(false);
 async function request(path,payload){if(inflight.current)return;inflight.current=true;setBusy(true);setError('');try{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Session-ID':sid.current},body:JSON.stringify(payload)});const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not continue.');setState(data);}catch(e){setError(e.message);}finally{inflight.current=false;setBusy(false);}}
 function start(){if(sessionStorage.getItem('application-demo-continue')!=='yes'){location.assign(demoUrl('/mitid'));return;}request('/application/init',{graph_id:graph(),demo_continue:true});}
 function answer(value){if(state.field.type==='date')value+='-01';request('/application/answer',{prompt_id:state.prompt_id,value});}
 const ended=state&&['complete','declined'].includes(state.status);
 return <main className="application-page"><header className="application-header"><a href={demoUrl('/demo')}>← SU-support</a><span>APPLICATION DEMO</span></header><section className="application-shell"><p className="application-eyebrow">ONE STEP AT A TIME</p><h1>Apply for disability allowance</h1><p className="application-notice">Demonstration only. Use fictional information. Answers are sent to the DCR simulation; file contents are not uploaded. Nothing is submitted to an authority.</p>
 {!state&&<div className="application-card"><h2>Ready to try the application?</h2><p>We’ll guide you through the questions and let you review your answers before sending the demo.</p><button disabled={busy} onClick={start}>Start demo application →</button></div>}
 {state&&!ended&&<>{state.answers?.length>0&&<details className="application-history" open={state.status==='review'}><summary>Your answers ({state.answers.length})</summary><dl>{state.answers.map((a,i)=><div key={i}><dt>{a.label}</dt><dd>{a.value}</dd></div>)}</dl></details>}<div className="application-card" key={state.prompt_id}><h2>{state.field.label}</h2>{state.status==='review'?<><p>Please review your answers above. To change them, start a new demo application.</p><button disabled={busy} onClick={()=>answer('send')}>Send demo application</button></>:<Field field={state.field} busy={busy} onSubmit={answer}/>}</div></>}
 {ended&&<div className="application-card application-success" role="status"><span className="application-tick">{state.status==='complete'?'✓':'—'}</span><h2>{state.status==='complete'?'Demo complete':'Application not sent'}</h2><p>{state.response}</p><strong>{state.demo_notice}</strong><p><a href={demoUrl('/demo')}>Return to the FAQ →</a></p></div>}
 {error&&<p className="application-error" role="alert">{error}</p>}{busy&&<p role="status">Checking the next step…</p>}{state&&<button className="application-reset" disabled={busy} onClick={()=>{if(window.confirm('Start a new demo and discard this screen’s answers?')){setState(null);setError('');sid.current=crypto.randomUUID();}}}>Start again</button>}</section></main>;
}
