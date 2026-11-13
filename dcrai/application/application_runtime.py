"""Demo application fields driven only by the live DCR event API.
No LLM, local XML, real authentication, file contents, or external submission.
"""
from datetime import date
import math
import logging
import re
import secrets
import threading
import dcrai.dcr.dcr_repository as repo
import dcrai.observability.interaction_log as ilog
import dcrai.observability.turn_trace as turn_trace
from dcrai.application import panel_context
from dcrai import registry
from dcrai.llm import openchat
import dcrai.llm.retrieval_llm as llm
import dcrai.chat.retrieval_runtime as rr
import dcrai.chat.outcome as oc
import dcrai.chat.outcome_runtime as ort
from dcrai.chat.faq_runtime import groups, choices

log = logging.getLogger(__name__)

class ApplicationError(ValueError):
    pass

APPLICATION_TAGS={'ApplicationField','ApplicationComplete','ApplicationDeclined'}

def is_application_event(e):
    tags = groups(e)
    if tags & {'ApplicationField', 'ApplicationComplete', 'ApplicationDeclined'}:
        return True
    eid = str(e.get('id', ''))
    return eid.startswith(('Form0:', 'Application:')) and eid not in ('Form0', 'Application')

def is_application_terminal(e):
    tags = groups(e)
    if tags & {'ApplicationComplete', 'ApplicationDeclined'}:
        return True
    eid = str(e.get('id', ''))
    return eid.endswith((':Complete', ':Declined', ':ApplicationComplete', ':ApplicationDeclined'))

# Diagnostic escape hatch. With APPLICATION_ENABLED_FALLBACK=1 the handler
# falls back to a single included+enabled step when nothing is pending, which
# is how the demo behaved before. It exists to walk past the entry defect and
# observe whether responses *inside* Form0 set pending. Leave it off normally:
# running on the fallback hides exactly the bug we are chasing.
ENABLED_FALLBACK=registry.flag('APPLICATION_ENABLED_FALLBACK')

def application_marking(payload):
    """Fingerprint only application events.

    faq_runtime.marking() covers every event, so answering an FAQ question
    mid-application would change it and invalidate the pending prompt. The
    application's own state is unchanged by an FAQ interjection, and the graph
    has no relation in either direction between the FAQ layer and Form0.
    """
    fields=('id','enabled','included','pending','executed','value','choiceValues','label')
    return sorted([{k:e.get(k) for k in fields} for e in payload['events']
                   if is_application_event(e) or is_application_terminal(e)], key=lambda e:e['id'])

def fetch(state):
    payload=repo.get_raw_events(state)
    if not isinstance(payload,dict) or not isinstance(payload.get('events'),list) or not all(isinstance(e,dict) for e in payload['events']):
        raise ApplicationError('DCR did not return application fields.')
    return payload

def active(e):
    return e.get('included') is True and e.get('enabled') is True and e.get('pending') is True

# Mirrors the extension rule on the file events in the graph. The event API
# does not expose validationRules, so this list has to be kept in step by hand.
UPLOAD_EXTENSIONS=('.pdf','.docx')
MAX_UPLOADS=8

# Titles and tag order are shared with the FAQ chat.
faq_titles=rr.faq_titles
ordered_tags=rr.ordered_tags

def help_card(e):
    """Field help from the live event: description (help text, option meanings) and HelpFAQ/Topic tags."""
    tags=ordered_tags(e); titles=faq_titles()
    related=[dict(id=t.split(':',1)[1],question=titles[t.split(':',1)[1]]) for t in tags
             if t.startswith('HelpFAQ:') and t.split(':',1)[1] in titles]
    topic=next((t.split(':',1)[1] for t in tags if t.startswith('Topic:')),None)
    return dict(html=e.get('description') or '',topic=topic,related=related)

def describe(e):
    tags=groups(e); dtype=e.get('dataType','').lower()
    if 'ApplicationDemoFile' in tags: dtype='demo_file'
    if 'ApplicationSubmit' in tags or dtype == 'button' or str(e.get('id', '')).endswith(':A10'): dtype='submit'
    supported={'date','text','longtext','textbox','email','int','integer','float','choice','boolean','bool','file','demo_file','submit','button'}
    if dtype == 'button': dtype = 'submit'
    if dtype not in supported: raise ApplicationError('This field type is not supported by the demo: '+dtype)
    is_hours = 'ApplicationHours' in tags or 'hour' in e.get('label', '').lower() or 'timer' in e.get('label', '').lower()
    result=dict(id=e['id'],label=e.get('label',''),type=dtype,hours=is_hours,help=help_card(e))
    if dtype in ('choice','file'):
        # The event API exposes no "multiple" flag, so several values are
        # declared with an ApplicationMulti tag on the event or hydrated from XML.
        result['multiple']='ApplicationMulti' in tags or str(e.get('multiple','')).lower()=='true' or str(e.get('id','')).endswith(':A11')
    if dtype=='choice':
        result['options']=[dict(label=c['question'],value=c['value']) for c in choices(e)]
    if dtype=='file':
        result['extensions']=list(UPLOAD_EXTENSIONS)
        result['max_files']=MAX_UPLOADS if result.get('multiple') else 1
    return result

def form_shape(payload):
    """Every application question with its current standing.

    Lets the form view show the whole shape of the application, including
    questions not yet reached and ones the person's answers ruled out, which a
    transcript of answers alone cannot convey.
    """
    rows=[]
    for e in sorted(payload['events'],key=lambda x:x.get('sequence') if isinstance(x.get('sequence'),int) else 0):
        if not is_application_event(e) or is_application_terminal(e): continue
        tags=groups(e)
        if 'ApplicationSubmit' in tags or e.get('dataType') == 'button' or str(e.get('id', '')).endswith(':A10'): continue
        row=dict(id=e['id'],label=e.get('label',''),
                 included=e.get('included') is True,
                 pending=e.get('pending') is True,
                 answered=bool(e.get('executed')))
        # Carry the control shape so the form view can draw every question,
        # including ones not yet reached, with its real options.
        try:
            described=describe(e)
            row['type']=described['type']
            row['multiple']=described.get('multiple',False)
            if described.get('options'):row['options']=described['options']
        except ApplicationError:
            row['type']='text'
        rows.append(row)
    return rows

def view(state,payload):
    if state.get('application_result'):
        return state['application_result']
    available=[e for e in payload['events'] if e.get('included') is True
               and e.get('enabled') is True and (is_application_event(e) or is_application_terminal(e))]
    # DCR decides what is asked next. The obligation is the question; an event
    # that is merely enabled is not one.
    pending=[e for e in available if e.get('pending') is True]
    waiting=[]
    if len(pending)>1:
        # After an edit the chain is re-fired, but a response only ever adds an
        # obligation: the questions that followed stay pending from before.
        # Re-asked questions carry an execution timestamp, leftovers do not, so
        # the re-asked one is the one to put next. Sequence breaks any tie.
        def order(e):
            return (0 if e.get('executed') else 1,
                    e.get('sequence') if isinstance(e.get('sequence'),int) else 0)
        pending=sorted(pending,key=order)
        log.info('Application resolving %s pending steps, asking %s first (waiting: %s)',
                 len(pending),pending[0]['id'],', '.join(e['id'] for e in pending[1:]))
        waiting=pending[1:]
    answered_ids={a['id'] for a in state.get('application_answers',[])}
    unanswered=[e for e in available if not e.get('executed') and e['id'] not in answered_ids]
    candidates=pending if pending else unanswered
    if len(candidates)!=1:
        # Omit field labels, entered values, descriptions and credentials.
        diagnostic=[dict(id=e.get('id'), type=e.get('type'), data_type=e.get('dataType'),
                         included=e.get('included'), enabled=e.get('enabled'),
                         pending=e.get('pending'), tags=sorted(groups(e)))
                    for e in payload['events']]
        # Every key the API actually returns, for the application container and
        # its fields only. The seven keys above hide whatever the engine uses to
        # express a nested or subprocess obligation.
        raw=[{k:v for k,v in e.items() if k not in ('label','value','displayValue','description','choiceValues')}
             for e in payload['events']
             if str(e.get('id','')).startswith('Form0')]
        log.error('Application raw application events graph=%s simulation=%s keys=%s events=%s',
                  state.get('graph_id'), state.get('simulation_id'),
                  sorted({k for e in payload['events'] for k in e}), raw)
        log.error('Application marking mismatch graph=%s simulation=%s available=%s pending=%s events=%s',
                  state.get('graph_id'), state.get('simulation_id'), len(available), len(candidates), diagnostic)
        raise ApplicationError(f'DCR returned {len(candidates)} pending application steps; expected one. See the Application marking mismatch diagnostic in the terminal.')
    selected=candidates[0]
    log.info('Application step event=%s mode=%s included_enabled=%s',
             selected['id'], 'pending' if pending else 'sole_enabled', len(available))
    if is_application_terminal(selected):
        state.pop('application_prompt',None)
        if not repo.execute_raw_event(state,selected['id'],''):
            raise ApplicationError('DCR could not acknowledge the final demo message.')
        status='complete' if ('ApplicationComplete' in groups(selected) or str(selected.get('id', '')).endswith((':Complete', ':ApplicationComplete'))) else 'declined'
        ilog.record(state,'finished',status=status,
                    answers=[dict(field=a['id'],label=a['label'],value=a['value'],raw=a.get('raw'))
                             for a in state.get('application_answers',[])])
        state['application_result'] = dict(application=True,status=status,response=selected['label'],demo_notice='Demonstration only. Nothing was submitted and no e-Boks message will be sent.')
        return state['application_result']
    fields=[selected]
    field=describe(fields[0]);ticket=secrets.token_urlsafe(24)
    asked=ilog.counter(state,'shown',field['id'])
    ilog.record(state,'question',field=field['id'],label=field['label'],type=field['type'],
                multiple=field.get('multiple'),options=[o['value'] for o in field.get('options',[])] or None,
                pending_count=len(pending) or None,asked_count=asked,
                waiting=[e['id'] for e in waiting] or None)
    ilog.mark_question(state)
    state['application_prompt']=dict(ticket=ticket,marking=application_marking(payload),field=field)
    return dict(application=True,status='review' if field['type']=='submit' else 'question',field=field,prompt_id=ticket,answers=state.get('application_answers',[]),form=form_shape(payload))

def start(state):
    payload=fetch(state)
    eid, value = None, None
    forms=[e for e in payload['events'] if 'ApplicationForm' in groups(e) or e.get('id') in ('Form0', 'Application')]
    if forms:
        links=[g for g in groups(forms[0]) if g.startswith('ApplicationStart:')]
        if links:
            _,eid,value=links[0].split(':',2)
    if not eid or not value:
        for e in payload['events']:
            if e.get('enabled') is True and ('FAQHome' in groups(e) or e.get('id') == 'FAQ_Home'):
                action_terms = ('proceed to application', 'start application', 'go to application',
                                'ansøg om handicaptillæg', 'gå til ansøgning', 'proceed', 'ansøg')
                for term in action_terms:
                    for c in choices(e):
                        if term in c['question'].lower():
                            eid, value = e['id'], c['value']
                            break
                    if eid:
                        break
                if eid:
                    break
    if eid and value:
        home=next((e for e in payload['events'] if e['id']==eid),None)
        if not home or home.get('enabled') is not True:
            raise ApplicationError('The application entry is not available.')
        if not repo.execute_raw_event(state,eid,value):raise ApplicationError('DCR could not start the application.')
        log.info('Application entry executed graph=%s simulation=%s event=%s',
                 state.get('graph_id'), state.get('simulation_id'), eid)
    else:
        # Graphs without an entry event (the retrieval graph): Form0 is open from the start of the application
        # session, and DCR's marking alone decides the first field. view() fails loudly if it is not exactly one.
        log.info('Application has no entry event; form open from the start graph=%s simulation=%s',
                 state.get('graph_id'), state.get('simulation_id'))
    if state.get('interaction'):
        state['interaction']['shown'] = {}
    state['application_answers']=[]
    # Spec 03: the panel searches through its own events when the graph has them (older graphs: the chat's), keeps
    # the outcome counters of its session, and opens its own session event.
    state['panel_search']=rr.event(payload,'Help_UserQuestion') is not None
    state['outcome']=dict(clarified=0,misses=0,handover_shown=False)
    session=rr.event(payload,'Session_Panel')
    if session is not None and session.get('enabled') is True:
        if not repo.execute_raw_event(state,'Session_Panel',''):
            log.warning('Could not execute Session_Panel; the panel search input stays closed')
    return view(state,fetch(state))

def validated(field,value):
    dtype=field['type']
    if not isinstance(value,str):raise ApplicationError('Please enter a valid value.')
    value=value.strip()
    if dtype=='submit':
        if value!='send':raise ApplicationError('Please confirm sending the demo application.')
        return '', 'Send demo application'
    if not value or len(value)>4000:raise ApplicationError('Enter a value of 1–4000 characters.')
    display=value
    if dtype=='choice':
        allowed={o['value']:o['label'] for o in field['options']}
        if field.get('multiple'):
            # Serialised as a comma-separated list of option values. Verify
            # against a live checklist before relying on this elsewhere.
            picked=[p.strip() for p in value.split(',') if p.strip()]
            if not picked:raise ApplicationError('Choose at least one option.')
            unknown=[p for p in picked if p not in allowed]
            if unknown:raise ApplicationError('Choose from the displayed options.')
            seen=[]
            for p in picked:
                if p not in seen:seen.append(p)
            value=','.join(seen);display=', '.join(allowed[p] for p in seen)
        else:
            if value not in allowed:raise ApplicationError('Choose one of the displayed options.')
            display=allowed[value]
    elif dtype in ('bool','boolean'):
        if value not in ('true','false'):raise ApplicationError('Choose Yes or No.')
    elif dtype=='date':
        # Accept a bare month from the conversational composer.
        if re.fullmatch(r'\d{4}-\d{2}',value):value=value+'-01'
        try:date.fromisoformat(value)
        except ValueError:raise ApplicationError('Enter a month as YYYY-MM, for example 2026-09.')
    elif dtype in ('int','integer','float'):
        try:number=float(value)
        except ValueError:raise ApplicationError('Enter a number.')
        if not math.isfinite(number) or (dtype in ('int','integer') and not number.is_integer()):raise ApplicationError('Enter a valid number.')
        if field['hours'] and not 0<=number<=168:raise ApplicationError('Hours per week must be between 0 and 168.')
    elif dtype=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ApplicationError('Enter a valid email address.')
    elif dtype=='file':
        # DCR records the upload activity; the host owns the bytes. The value
        # sent to DCR is the filename, or a comma-separated list of them.
        names=[p.strip() for p in value.split(',') if p.strip()]
        if not names:raise ApplicationError('Choose at least one file.')
        if len(names)>(MAX_UPLOADS if field.get('multiple') else 1):
            raise ApplicationError(f'Attach up to {MAX_UPLOADS if field.get("multiple") else 1} file(s).')
        for n in names:
            if len(n)>200 or '/' in n or '\\' in n:
                raise ApplicationError('Use filenames only, up to 200 characters.')
            if not n.lower().endswith(UPLOAD_EXTENSIONS):
                raise ApplicationError('Files must be '+' or '.join(UPLOAD_EXTENSIONS)+'.')
        value=','.join(names);display=', '.join(names)
    elif dtype=='demo_file':
        if len(value)>200 or '/' in value or '\\' in value:raise ApplicationError('Use a filename only, up to 200 characters.')
    elif dtype=='text' and len(value)>50:raise ApplicationError('Use up to 50 characters for this field.')
    return value,display

def answer(state,data,source='typed'):
    issued=state.get('application_prompt')
    if not issued or data.get('prompt_id')!=issued['ticket']:raise ApplicationError('This question has changed. Reload the application.')
    payload=fetch(state)
    if application_marking(payload)!=issued['marking']:raise ApplicationError('DCR state changed. Reload the application.')
    field=issued['field']
    try:
        value,display=validated(field,data.get('value'))
    except ApplicationError as error:
        ilog.counter(state,'rejections',field['id'])
        ilog.record(state,'rejected',field=field['id'],reason=str(error),value=data.get('value'))
        raise
    if not repo.execute_raw_event(state,field['id'],value):raise ApplicationError('DCR could not save this answer. Please retry.')
    state.pop('application_prompt',None)
    if field['type']!='submit':
        ilog.record(state,'answer',field=field['id'],label=field['label'],type=field['type'],
                    value=value,display=display,source=source,
                    attempts=ilog.peek(state,'attempts',field['id']) or None,
                    rejections=ilog.peek(state,'rejections',field['id']) or None,
                    seconds_on_question=ilog.seconds_on_question(state))
        ilog.clear(state,field['id'])
        state.setdefault('application_values',{})[field['id']]=value
        state['application_answers'].append(record(field,display,value))
    return view(state,fetch(state))

def record(field,display,raw=''):
    """Transcript entry carrying what the UI needs to re-ask and re-draw this question.

    raw is the machine value DCR holds; display is the human text. The form view
    matches options on raw, because display carries labels, not values.
    """
    entry=dict(id=field['id'],label=field['label'],value=display,raw=raw,
               type=field['type'],hours=field.get('hours',False))
    if field.get('multiple'):entry['multiple']=True
    if field.get('options'):entry['options']=field['options']
    for key in ('extensions','max_files'):   # a file answer can be attached again when going back
        if field.get(key):entry[key]=field[key]
    return entry

def replayable(event,stored):
    """Kept for reference: values the person already gave, still valid for a field.

    Unused since editing began rewinding rather than re-applying answers forward.
    """
    if stored is None: return False
    try: described=describe(event)
    except ApplicationError: return False
    if described['type']=='submit': return False
    # A changed branch can change the option set, so a stored choice may no
    # longer be offered. Then it is a genuinely new question.
    if described['type']=='choice':
        allowed={o['value'] for o in described['options']}
        picked=[p.strip() for p in stored.split(',')] if described.get('multiple') else [stored]
        return bool(picked) and all(p in allowed for p in picked)
    return True

def replay(state,limit=40):
    """Unused. Re-applied stored answers after an edit; editing now rewinds
    instead, so later questions are asked again rather than silently refilled.
    """
    stored=state.get('application_values',{})
    for _ in range(limit):
        payload=fetch(state)
        pending=[e for e in payload['events'] if e.get('included') is True
                 and e.get('enabled') is True and e.get('pending') is True
                 and is_application_event(e)]
        if len(pending)!=1: return payload
        event=pending[0]
        if not replayable(event,stored.get(event['id'])): return payload
        described=describe(event)
        value=stored[event['id']]
        if not repo.execute_raw_event(state,event['id'],value):
            raise ApplicationError('DCR could not re-apply an earlier answer.')
        display=next((o['label'] for o in described.get('options',[]) if o['value']==value),value)
        if described.get('multiple'):
            names={o['value']:o['label'] for o in described.get('options',[])}
            display=', '.join(names.get(p.strip(),p.strip()) for p in value.split(','))
        state['application_answers'].append(record(described,display,value))
        log.info('Application replayed event=%s',event['id'])
    raise ApplicationError('The application did not settle after the change. Please start again.')

def edit(state,data):
    """Change an earlier answer, then let DCR decide what still applies."""
    target=data.get('field_id')
    payload=fetch(state)
    event=next((e for e in payload['events'] if e['id']==target),None)
    if not event or not is_application_event(event):
        raise ApplicationError('That is not an editable application question.')
    if event.get('included') is not True or event.get('enabled') is not True:
        raise ApplicationError('That question is no longer part of your application.')
    field=describe(event)
    if field['type']=='submit':raise ApplicationError('The send step cannot be edited.')
    value,display=validated(field,data.get('value'))
    answers=state.get('application_answers',[])
    keep=next((i for i,a in enumerate(answers) if a.get('id')==target),len(answers))
    previous=next((a for a in answers if a.get('id')==target),None)
    ilog.record(state,'edit',field=target,label=field['label'],
                from_value=(previous or {}).get('raw'),to_value=value,
                was_pending=((state.get('application_prompt') or {}).get('field') or {}).get('id'),
                answered_after=max(0,len(answers)-keep-1))
    prior_answers = answers[:keep]
    state.pop('application_prompt', None)
    state.setdefault('application_values', {})[target] = value

    # DCR simulations are append-only. To rewind to an earlier question and allow
    # DCR to compute new branching cleanly without stale downstream executions,
    # replay the trace up to the edited question in a fresh simulation.
    new_sim = repo.create_simulation(state)
    if new_sim:
        state['simulation_id'] = new_sim
        state['application_answers'] = []
        start(state)
        for a in prior_answers:
            raw_val = a.get('raw', a.get('value', ''))
            repo.execute_raw_event(state, a['id'], raw_val)
            state['application_answers'].append(a)
    else:
        state['application_answers'] = prior_answers

    if not repo.execute_raw_event(state, target, value):
        raise ApplicationError('DCR could not save the change. Please retry.')
    state['application_answers'].append(record(field, display, value))
    log.info('Application edited event=%s simulation=%s', target, state.get('simulation_id'))
    return view(state, fetch(state))

INTERPRETABLE={'int','integer','float','choice'}

def interpret(state,data):
    """Read free text as a value for a question.

    Targets the pending question by default, or an already-answered one when
    field_id is given, so an earlier answer can be rewritten in words.
    """
    target=data.get('field_id')
    if target:
        payload=fetch(state)
        event=next((e for e in payload['events'] if e['id']==target),None)
        if not event or not is_application_event(event):
            raise ApplicationError('That is not an editable application question.')
        field=describe(event)
    else:
        issued=state.get('application_prompt')
        if not issued or data.get('prompt_id')!=issued['ticket']:
            raise ApplicationError('This question has changed. Reload the application.')
        field=issued['field']
    if field['type'] not in INTERPRETABLE:
        raise ApplicationError('This question takes a direct answer.')
    message=data.get('message') or ''
    if not isinstance(message,str) or not message.strip() or len(message)>2000:
        raise ApplicationError('Please enter a reply of 1\u20132000 characters.')
    kind=('choices' if field.get('multiple') else 'choice') if field['type']=='choice' \
         else 'integer' if field['type'] in ('int','integer') else 'number'
    context=[dict(question=a['label'],answer=a['value'])
             for a in (state.get('application_answers') or []) if a.get('id')!=field['id']]
    attempt=ilog.counter(state,'attempts',field['id'])
    try:
        understood,value,explanation=openchat.interpret(
            message.strip(),field['label'],kind,field.get('options'),context=context)
    except (openchat.MatchError,ValueError) as error:
        log.warning('Application interpretation failed type=%s',type(error).__name__)
        raise ApplicationError('I could not read that as an answer. Please enter the value directly.')
    if not understood:
        ilog.record(state,'interpretation',field=field['id'],reply=message.strip(),value_kind=kind,
                    understood=False,explanation=explanation,attempt=attempt)
        result=dict(application=True,status='not_interpreted',
                    response=explanation or 'I could not work out a value from that. Please enter it directly.')
        fails=state.setdefault('interpret_fails',{})
        fails[field['id']]=fails.get(field['id'],0)+1
        if fails[field['id']]>=2:
            handover=escalate(state,2,f"answer to {field['id']} not readable twice",once=True)
            if handover:result['handover']=handover
        return result
    raw=(str(int(value)) if kind=='integer' else str(value) if kind=='number'
         else ','.join(value) if kind=='choices' else value)
    # Run the same validation the typed path uses, so an interpretation can
    # never bypass a bound such as the 0-168 hours range.
    try:
        raw,display=validated(field,raw)
    except ApplicationError as error:
        ilog.record(state,'interpretation',field=field['id'],reply=message.strip(),value_kind=kind,
                    understood=False,explanation=str(error),attempt=attempt)
        return dict(application=True,status='not_interpreted',response=str(error))
    ilog.record(state,'interpretation',field=field['id'],reply=message.strip(),value_kind=kind,
                understood=True,value=raw,display=display,explanation=explanation,attempt=attempt)
    return dict(application=True,status='interpreted',value=raw,display=display,
                explanation=explanation,prompt_id=data.get('prompt_id'),
                field_id=field['id'])

def context_for(state):
    """Application state as search context (to be sent as ctx via FAQ_SearchContext; not used yet).

    Both parts come from the graph: answered fields are executed application
    events, the current stage is the pending one. Nothing is stored in parallel.
    NOTE: once wired, this sends the user's application answers to the search API.
    """
    issued=state.get('application_prompt') or {}
    stage=(issued.get('field') or {}).get('label','')
    answered='; '.join(f"{a['label']}: {a['value']}" for a in (state.get('application_answers') or [])[-8:])
    parts=['The user is completing the SU disability supplement application.']
    if stage:parts.append('They are currently being asked: '+stage)
    if answered:parts.append('They have already answered: '+answered)
    return ' '.join(parts)

def _unchanged(state,before):
    """Every FAQ step must leave the application's own events exactly as they were."""
    payload=fetch(state)
    if application_marking(payload)!=before:
        # The graph has no FAQ-to-Form0 relation, so this should be unreachable.
        log.error('FAQ question changed application marking graph=%s simulation=%s',
                  state.get('graph_id'),state.get('simulation_id'))
        raise ApplicationError('The application state changed unexpectedly. Reload the application.')
    return payload

URGENT=ort.URGENT        # moved to outcome_runtime so the chat can use them; same names here
PERSON=ort.PERSON
MISSES_BEFORE_HANDOVER=oc.MISSES_BEFORE_HANDOVER
SAME_FAQ_COVERS='The answer above already covers this.'
SAME_FAQ_CLOSEST=('The answer above is the closest the FAQ has. It does not say more about this. For questions about '
                  'your own case, use the contact options published on SU.dk.')

def help_context(state,payload):
    """What the gated rewrite and the classifiers may use: the field on screen with its help text (DCR description),
    and the last answered FAQ (DCR). Earlier application answers are left out on purpose: on 2026-10-09 they pulled
    a rewrite towards an earlier question (time-limited award) instead of the question on screen."""
    field=((state.get('application_prompt') or {}).get('field') or {})
    answered=rr.event(payload,rr.ANSWERED)
    last=str(answered['value']) if answered and answered.get('executed') and answered.get('value') else None
    # The panel's own context lives in the Panel_Context event of the graph (spec 02, R26); the session fields are the
    # fallback for graphs without the event, an unreadable value, and PANEL_CONTEXT_IN_DCR=0.
    record=panel_context.current(state,payload)
    shown=panel_context.last_faq(record) if record is not None else (state.get('help_last_faq') or {})
    previous=panel_context.last_message(record) if record is not None else state.get('help_last_message')
    if shown.get('answer_start'):
        last=f"{shown['id']}: {shown['question']} (answer begins: {shown['answer_start']})"
    about=rr.plain((field.get('help') or {}).get('html') or '')[:1200] or None
    turn_trace.note(context=dict(faq_ids=[shown['id']] if shown.get('id') else [],field=field.get('id'),
                                 source='dcr' if record is not None else 'session'))
    return dict(current_question=field.get('label'),about_question=about,last_answered_faq=last,
                previous_question=previous)

def escalate(state,reason,signal,once=False):
    """Execute Help_Escalate (reason as value) and return the Help_Handover text DCR makes pending, or None.

    once=True: an automatic escalation is shown at most once per reason per session; the applicant's own request
    (reason 1) always goes through.
    """
    shown=state.setdefault('handover_shown',[])
    if once and reason in shown:
        return None
    payload=fetch(state)
    trigger=rr.event(payload,'Help_Escalate')
    if not trigger or trigger.get('enabled') is not True:
        return None   # older graph without the handover events
    before=application_marking(payload)
    handover=ort.handover(state,reason,signal)   # executes Help_Escalate, reads and acknowledges Help_Handover
    _unchanged(state,before)
    shown.append(reason)
    log.info('Help handover reason=%s',reason)
    ilog.record(state,'handover',reason=reason)
    return handover

def _miss(state,signal):
    """The applicant rejected a confirm or a list: count the miss (outcome counters) and hand over on the second."""
    c=rr.advance(state,signal)
    if c['misses']>=oc.MISSES_BEFORE_HANDOVER and not c['handover_shown']:
        handover=escalate(state,2,f"{c['misses']} questions in a row without a usable answer",once=True)
        rr.advance(state,'handover')
        return handover
    return None

def _show(state,found,how,message=None):
    """Show one FAQ answer verbatim and record it in DCR (FAQ_Answered) as context for later questions.

    With FOLLOWUP_SURFACE=panel (default) the answer may carry the follow-up determination of its FAQ
    (result['prompt'], kind 'determination'); the applicant's reply goes to determination() (spec 03, R10).
    """
    payload=fetch(state);before=application_marking(payload)
    answered=rr.event(payload,rr.ANSWERED)
    if answered and answered.get('enabled') is True:
        if not repo.execute_raw_event(state,rr.ANSWERED,f"{found['id']}: {found['question']}"):
            log.warning('Could not record the answered FAQ in DCR')
    payload=_unchanged(state,before)
    rr.advance(state,'answered')
    state['help_last_faq']=dict(id=found['id'],question=found['question'],
                                answer_start=' '.join(str(found.get('answer') or '').split())[:300])
    log.info('Application FAQ answered faq=%s via=%s',found['id'],how)
    ilog.record(state,'faq_answer',faq=found['id'],via=how,
                during=((state.get('application_prompt') or {}).get('field') or {}).get('id'))
    prompt=None
    if rr.followup_surface()=='panel':
        try:
            prompt=rr.open_followup(state,payload,found,message if message is not None else state.get('help_last_message') or '')
        except rr.StateError as error:
            log.warning('Follow-up unavailable: %s',error)
        if prompt:payload=_unchanged(state,before)
    result=view(state,payload)
    result.update(answered=True,faq_id=found['id'],faq_question=found['question'],
                  faq_response=rr.paragraphs(found['answer']),faq_citation=found.get('citation',''))
    if prompt:result.update(prompt=prompt,follow_up=rr.FOLLOW_UP_TEXT)
    return result

@turn_trace.turn('panel')
@panel_context.persist
def ask(state,data):
    """Search the FAQ for a question asked in the help panel. Never touches application state.

    A suggested question (related) and a field-scoped question are explicit, so the host executes FAQ_Triage = 1 itself.
    An unscoped typed message goes through the triage (PANEL_TRIAGE=1, default): the classifier chooses between 1
    (a question) and 5 (out of scope) only, and a 5 is answered with the FAQ_OutOfScope text without any search
    (status faq_out_of_scope). FAQ_Triage = 1 is what includes the panel's search input in the graph; the search
    runs through DCR (Robot + effect). The follow-up determination of an answered FAQ is asked here, in the panel,
    not in the chat (spec 03).

    What is searched, in order, stopping at the first usable result:
      related=<FAQ id>   a suggested question clicked on the field card: its canonical title. If that FAQ comes
                         back it is answered directly (no "is this what you mean").
      typed message      1. if a classifier says the message only makes sense with the context (DECISIONS_ENABLED,
                            DECISIONS_CONTEXT_MIN): a standalone rewrite first;
                         2. the message as typed;
                         3. scope='field' and none of the field's linked FAQs came back (or nothing came back):
                            "<field label> <message>" (composed-query eval 2026-10-08: 34/36 offered, 28/36 first).
                         A message the classifier did not call context dependent is never rewritten (eval
                         2026-10-09: a weather question was rewritten into a field question and answered). The old
                         last-resort rewrite runs only with PANEL_FALLBACK_REWRITE=1 (default 0).
    What is shown is decided by the outcome function (dcrai/chat/outcome.py, settled into DCR by outcome_runtime):
    a true single match that the relevance check says answers it is answered directly (row 4); a list pruned to one
    FAQ is confirmed first (row 6, faq_confirm); FAQs on the same topic only are offered as related (row 5,
    faq_related); several that answer it are offered as a choice (row 7, faq_clarify), and a second list after a
    clarify is offered as the best fit (row 8). Two misses in a row add the handover block. "Understood as"
    (searched_for) is shown only for a rewrite; the composed query is an internal search aid and is not shown. The
    original message goes in the DCR comment. A related-question click that brings its own FAQ back is answered
    without the table.
    """
    titles=faq_titles()
    related=data.get('related')
    if related is not None:
        if related not in titles:
            raise ApplicationError('That related question is not available.')
        message=titles[related]
        turn_trace.note(message=message)
    else:
        message=data.get('message')
        if not isinstance(message,str) or not message.strip() or len(message)>2000:
            raise ApplicationError('Please enter a question of 1\u20132000 characters.')
        message=message.strip()
    scope=data.get('scope')
    if scope not in (None,'field'):
        raise ApplicationError('Unknown question scope.')
    payload=fetch(state)
    if not rr.is_retrieval(payload):
        raise ApplicationError('Questions during the application need the retrieval graph (FAQ_UserQuestion).')
    state.pop('application_match',None)
    state['retrieval_prompt']=None   # an unanswered follow-up is dropped by a new question
    field=((state.get('application_prompt') or {}).get('field') or {})
    if scope=='field' and not field.get('label'):
        raise ApplicationError('There is no application question on screen to ask about.')
    handover=None
    if related is None:
        if PERSON.search(message):
            asked=ort.settle(state,payload,oc.decide('in_scope',None,[],asked_person=True),'panel')
            handover=escalate(state,1,'asked to talk to a person')
            if handover:
                rr.log_decision(state,'panel',asked,[],'typed')
                return dict(application=True,status='handover',response='',handover=handover)
        if URGENT.search(message):
            handover=escalate(state,3,'deadline or appeal mentioned',once=True)
    triage_value,triage_note='1','explicit question during the application'
    triage_event=rr.event(payload,rr.TRIAGE)
    if related is None and scope is None and triage_event is not None and triage_event.get('enabled') is True \
            and rr.flag('PANEL_TRIAGE','1'):
        triage_value,triage_note=panel_triage(message,payload,triage_event)
    context=help_context(state,payload)
    has_context=bool(context['current_question'] or context['last_answered_faq'])
    use_llm=related is None and llm.decisions_enabled()
    contextual=False
    if use_llm:
        try:
            signals=llm.panel_signals_decisions(message,context)
        except llm.LLMError as error:
            log.warning('Panel signals unavailable (%s); plain search',error)
            signals={}
        if signals.get('distress',0)>=llm._threshold('DECISIONS_DISTRESS_MIN','0.7') and not handover:
            handover=escalate(state,4,'distress p=%.2f'%signals['distress'],once=True)
        contextual=has_context and signals.get('contextual',0)>=llm._threshold('DECISIONS_CONTEXT_MIN','0.7')

    def rewrite():
        try:
            text=llm.rewrite(message,context,prompt=llm.PANEL_REWRITE_PROMPT)
        except llm.LLMError as error:
            log.warning('Rewrite unavailable (%s)',error)
            return None
        return text if text and text.strip().lower()!=message.lower() else None

    linked={r['id'] for r in ((field.get('help') or {}).get('related') or [])} if scope=='field' else set()
    if related is not None:
        steps=[('related',message)]
    else:
        steps=[]
        if contextual:
            # The message only makes sense with the context ("would the hours matter here?"), so the words alone
            # are not a question to search or to judge answers against: only the rewrite is searched. 2026-10-09:
            # searching the raw words found FAQ_16, which the relevance check passed out of context.
            steps.append(('rewritten',None))
        else:
            steps.append(('field-typed' if scope=='field' else 'typed',message))
            if scope=='field':steps.append(('field-composed',f"{field['label']} {message}"))
            if use_llm and has_context and rr.flag('PANEL_FALLBACK_REWRITE','0'):steps.append(('rewritten',None))

    before=application_marking(payload)
    best=None   # (status, found, text, query, how)
    tried=[]
    rewritten=None   # what the applicant means, when a rewrite was made
    try:
        triage=rr.event(payload,rr.TRIAGE)
        if triage is not None:
            if triage.get('enabled') is not True:
                raise ApplicationError('DCR is not accepting questions right now.')
            rr.execute(state,rr.TRIAGE,triage_value,triage_note)
        for how,query in (steps if triage_value!='5' else []):
            if how=='field-composed' and best and best[0]=='found' and any(c['id'] in linked for c in best[1]):
                break
            if how=='rewritten' and best and best[0]=='found':
                break
            if how=='rewritten':
                query=rewritten=rewrite()
                if not query:continue
            query=query[:1000]
            payload=fetch(state)
            search_input=rr.search_ids(state)[0]
            question=rr.event(payload,search_input)
            if (not question or question.get('enabled') is not True) and triage is not None:
                rr.execute(state,rr.TRIAGE,'1','explicit question during the application (next search)')
                payload=fetch(state);question=rr.event(payload,search_input)
            if not question or question.get('enabled') is not True:
                raise ApplicationError('DCR did not admit the question.')
            comment=f"application help ({how})"+(f": {message}" if query!=message else '')
            # Candidates are judged against what the applicant means: the rewrite, or their own words. Never
            # against the composed "<label> <message>" string, which is only a search aid.
            status,found,text=rr.search(state,query,comment[:500],judge=rewritten or message)
            decision=(state.get('last_search') or {}).get('decision')
            tried.append(how)
            if status=='unavailable':
                best=(status,found,text,query,how,decision);break
            if status=='found':
                best=(status,found,text,query,how,decision)
                if how in ('related','rewritten') or not linked or any(c['id'] in linked for c in found):
                    break
            elif best is None:
                best=(status,found,text,query,how,decision)
    except rr.StateError as error:
        log.warning('Application question failed: %s',error)
        raise ApplicationError('The FAQ search is unavailable. Please continue with the application.')
    payload=_unchanged(state,before)
    if triage_value=='5':
        return out_of_scope(state,payload,handover)
    if best is None:
        # contextual message and the rewrite was unavailable: nothing was searched
        best=('no_match',[],'',message,'rewritten',None)
    status,found,text,query,how,decision=best
    during=field.get('id')
    if related is None:
        state['help_last_message']=message[:500]
        state['help_last_rewrite']=rewritten
    # "Understood as" whenever a rewrite was made, also when it found nothing, so a wrong reading is visible.
    shown={'searched_for':rewritten} if rewritten else {}
    last_shown=panel_context.shown_id(state,payload)
    log.info('Application question how=%s tried=%s decision=%s',how,tried,status)
    if status=='unavailable':
        ilog.record(state,'faq_ask',decision=status,how=how,tried=tried,during=during)
        result=dict(application=True,status='faq_unavailable',
                    response=rr.plain(text) or 'I could not find an answer to that.',**shown)
        if handover:result['handover']=handover
        return result
    direct=[c for c in found if c['id']==related] if related is not None else []
    if direct:
        # The applicant clicked this FAQ's title and the search brought it back: answer it, no confirm and no table.
        ilog.record(state,'faq_ask',decision='found',how=how,tried=tried,candidates=[c['id'] for c in found],
                    during=during)
        rr.log_outcome(state,'panel','answer',None,direct,how)
        result=_show(state,direct[0],how,message)
        result.update(shown)
        if handover:result['handover']=handover
        return result
    # The outcome function (nine rows), written into DCR before anything is shown.
    settled=rr.settle_turn(state,payload,rr.decide_turn(state,decision or 'no_match',[c.get('tier') for c in found]),'panel')
    d=settled.decision
    outcome,row=d.outcome,d.row
    items=oc.shown_for(row,found)
    if outcome in ('answer','confirm','offer','clarify') and not items:
        log.error('Outcome %s (row %s) has nothing to show; treating as not covered',outcome,row)
        outcome='not_covered'
    if outcome=='confirm' and not rr.flag('CONFIRM_LONE_SURVIVOR','1'):
        outcome='answer'   # today's behaviour; the log keeps the table's row 6
    if related is not None and outcome=='answer':
        outcome,row='confirm',6   # the clicked title brought back a different FAQ: ask before showing it
    payload=_unchanged(state,before)
    if outcome in ('not_covered','handover'):
        ilog.record(state,'faq_ask',decision='no_match',how=how,tried=tried,during=during)
        rr.log_decision(state,'panel',settled,[],how,outcome=outcome)
        result=dict(application=True,status='faq_no_match',
                    response=rr.plain(text) or 'I could not find an answer to that.',**shown)
        if outcome=='handover':
            if handover:
                ort.acknowledge(state,'Help_Handover')   # a handover block was already shown this turn (deadline, distress)
            else:
                handover=escalate(state,2,'%d questions in a row without a usable answer'%(rr.counters(state)['misses']+1),once=True)
            rr.advance(state,'handover')
        else:
            rr.advance(state,'not_covered')
        if handover:result['handover']=handover
        return result
    ilog.record(state,'faq_ask',decision='found',how=how,tried=tried,candidates=[c['id'] for c in found],
                during=during)
    if outcome in ('answer','confirm','offer') and contextual and [c['id'] for c in items]==[last_shown]:
        # A follow-up whose only match is the FAQ just shown: the FAQ has nothing more on it. Say so instead of
        # showing the same answer again. The wording depends on what the relevance check said about the FAQ pointed
        # back to (WD1): it answers the follow-up, or it is only the closest the FAQ has.
        ilog.record(state,'faq_ask',decision='same_faq',how=how,tried=tried,during=during)
        rr.log_decision(state,'panel',settled,items,how,outcome=outcome,row=row,same_faq=True)
        rr.advance(state,{'answer':'answered','confirm':'confirm_shown','offer':'offer'}[outcome])
        covers=items[0].get('tier')=='answers'
        return dict(application=True,status='faq_no_match',same_faq=True,**shown,
                    response=SAME_FAQ_COVERS if covers else SAME_FAQ_CLOSEST)
    rr.log_decision(state,'panel',settled,items,how,outcome=outcome,row=row)
    if outcome=='answer':
        result=_show(state,items[0],how,message)
        result.update(shown)
        if handover:result['handover']=handover
        return result
    match_id=secrets.token_urlsafe(24)
    state['application_match']=dict(id=match_id,candidates=items,kind=outcome,turn=state.get('turn'))
    candidates=[dict(candidate_key=c['id'],question=c['question']) for c in items]
    if outcome=='confirm':
        rr.advance(state,'confirm_shown')
        result=dict(application=True,status='faq_confirm',response=rr.outcome_message(payload,6),match_id=match_id,
                    candidates=candidates[:1],**shown)
    elif outcome=='offer' and row==5:
        rr.advance(state,'offer')
        result=dict(application=True,status='faq_related',related=True,
                    response=rr.outcome_message(payload,5,len(items)),match_id=match_id,
                    candidates=candidates,**shown)
    else:
        # row 7 (several answer it) and row 8 (the best offer after a clarify) read the Clarify text
        rr.advance(state,'offer' if outcome=='offer' else 'clarify_candidates')
        result=dict(application=True,status='faq_clarify',response=rr.outcome_message(payload,row if row in (7,8) else 7),
                    match_id=match_id,candidates=candidates,**shown)
    if handover:result['handover']=handover
    return result

def panel_triage(message,payload,triage):
    """The triage for an unscoped typed message: the classifier chooses between 1 (a question) and 5 (out of scope).

    Returns (value, comment) for FAQ_Triage. 'unsure', a model that is down, a dictionary that is not the host
    contract, or any other value gives 1: the panel searches rather than refuses.
    """
    default=('1','explicit question during the application')
    try:
        values=[{'value':c['value'],'label':c['question']} for c in choices(triage) if c['value'] in ('1','5')]
    except rr.StateError as error:
        log.warning('Panel triage dictionary unreadable (%s); searching',error)
        return default
    if {v['value'] for v in values}!={'1','5'}:
        log.warning('FAQ_Triage has no values 1 and 5; the panel searches without a triage')
        return default
    try:
        decision=rr.classify('triage',message,rr.plain(triage.get('description')),values,None,rr.dcr_context(payload))
    except llm.LLMError as error:
        log.warning('Panel triage unavailable (%s); searching',error)
        return '1','triage unavailable; default search'
    if decision.get('unsure') or decision.get('value') not in ('1','5'):
        return '1','triage unsure; searching'
    return decision['value'],(str(decision.get('reason') or '')[:300] or default[1])

def out_of_scope(state,payload,handover=None):
    """Row 1 of the outcome table in the panel: FAQ_Triage = 5 made FAQ_OutOfScope pending. Nothing is searched."""
    settled=rr.settle_turn(state,payload,oc.decide('out_of_scope',None,[],rr.counters(state)['clarified']),'panel')
    rr.log_decision(state,'panel',settled,[],'typed')
    ilog.record(state,'faq_ask',decision='out_of_scope',during=((state.get('application_prompt') or {}).get('field') or {}).get('id'))
    text=rr.show_label(state,payload,'FAQOutOfScope','That is outside what I can help with.')   # acknowledges the event
    rr.advance(state,'out_of_scope')
    result=dict(application=True,status='faq_out_of_scope',response=rr.plain(text))
    if handover:result['handover']=handover
    return result

@turn_trace.turn('panel')
@panel_context.persist
def confirm(state,data):
    """Show the chosen FAQ answer verbatim from the retrieval result and record it in DCR as context."""
    issued=state.get('application_match')
    if not issued or data.get('match_id')!=issued['id']:
        raise ApplicationError('That question has expired. Please ask again.')
    kind=issued.get('kind') or 'clarify'
    if data.get('candidate_key')=='none':
        state.pop('application_match',None)
        rr.log_reaction(state,'panel',kind,'rejected' if kind=='confirm' else 'none_of_these',turn=issued.get('turn'))
        result=dict(application=True,status='faq_none',
                    response='Try asking in other words, for example with the situation you are in.')
        handover=_miss(state,'rejected' if kind=='confirm' else 'none_of_these')
        if handover:result['handover']=handover
        return result
    chosen=[c for c in issued['candidates'] if c['id']==data.get('candidate_key')]
    if len(chosen)!=1:raise ApplicationError('Choose one of the displayed questions.')
    state.pop('application_match',None)
    rr.log_reaction(state,'panel',kind,'accepted' if kind=='confirm' else 'chose',faq_id=chosen[0]['id'],
                    turn=issued.get('turn'))
    return _show(state,chosen[0],'chosen')

def determination(state,data):
    """The applicant answered the follow-up determination shown with an answer. Never touches application state."""
    prompt=rr.current(state)
    if not prompt or prompt.get('kind')!='determination' or data.get('retrieval_prompt_id')!=prompt['id']:
        raise ApplicationError('That follow-up question has expired. Please ask again.')
    value=str(data.get('value'))
    if value not in [str(c['value']) for c in prompt['choices']]:
        raise ApplicationError('Choose one of the displayed answers.')
    payload=fetch(state);before=application_marking(payload)
    try:
        result=rr.answer_determination(state,prompt,value)
    except rr.StateError as error:
        raise ApplicationError(str(error))
    _unchanged(state,before)
    result.update(application=True)
    return result

def install(app,session_store,credentials):
    from flask import request,jsonify
    lock=threading.Lock()
    @app.post('/application/init')
    def application_init():
        sid=request.headers.get('X-Session-ID');data=request.get_json(silent=True) or {}
        if not sid or not isinstance(data,dict) or data.get('demo_continue') is not True:return jsonify(error='Continue through the demonstration login first.'),400
        gid=str(data.get('graph_id',''))
        if not gid.isdigit():return jsonify(error='A valid DCR graph ID is required.'),400
        state=dict(credentials(),graph_id=gid)
        try:
            graph_elem = repo.get_graph(state)
            if graph_elem is not None:
                import xml.etree.ElementTree as ET
                state['graph_xml'] = ET.tostring(graph_elem, encoding='unicode')
            state['simulation_id']=repo.create_simulation(state)
            if not state['simulation_id']:raise ApplicationError('DCR could not create the application session.')
            ilog.start(state,gid,state['simulation_id'],interface='panel')
            result=start(state)
            with lock:session_store[sid]=state
            return jsonify(result)
        except ApplicationError as e:return jsonify(error=str(e)),400
        except Exception:return jsonify(error='DCR is unavailable. Please try again.'),502
    @app.post('/application/ask')
    def application_ask():
        sid=request.headers.get('X-Session-ID');data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(error='Invalid request.'),400
        with lock:
            state=session_store.get(sid)
            if not state or 'application_answers' not in state:return jsonify(error='Start the demo application first.'),400
            try:return jsonify(ask(state,data))
            except ApplicationError as e:return jsonify(error=str(e)),400
            except Exception:return jsonify(error='DCR is unavailable. Please reload to check the current state.'),502
    @app.post('/application/confirm')
    def application_confirm():
        sid=request.headers.get('X-Session-ID');data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(error='Invalid request.'),400
        with lock:
            state=session_store.get(sid)
            if not state or 'application_answers' not in state:return jsonify(error='Start the demo application first.'),400
            try:return jsonify(confirm(state,data))
            except ApplicationError as e:return jsonify(error=str(e)),400
            except Exception:return jsonify(error='DCR is unavailable. Please reload to check the current state.'),502
    @app.post('/application/determination')
    def application_determination():
        sid=request.headers.get('X-Session-ID');data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(error='Invalid request.'),400
        with lock:
            state=session_store.get(sid)
            if not state or 'application_answers' not in state:return jsonify(error='Start the demo application first.'),400
            try:return jsonify(determination(state,data))
            except ApplicationError as e:return jsonify(error=str(e)),400
            except Exception:return jsonify(error='DCR is unavailable. Please reload to check the current state.'),502
    @app.post('/application/handover')
    def application_handover():
        sid=request.headers.get('X-Session-ID')
        with lock:
            state=session_store.get(sid)
            if not state or 'application_answers' not in state:return jsonify(error='Start the demo application first.'),400
            try:
                handover=escalate(state,1,'Talk to a person button')
                if not handover:return jsonify(error='This graph has no handover message.'),400
                return jsonify(dict(application=True,status='handover',response='',handover=handover))
            except ApplicationError as e:return jsonify(error=str(e)),400
            except Exception:return jsonify(error='DCR is unavailable. Please reload to check the current state.'),502
    @app.post('/application/interpret')
    def application_interpret():
        sid=request.headers.get('X-Session-ID');data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(error='Invalid request.'),400
        with lock:
            state=session_store.get(sid)
            if not state or 'application_answers' not in state:return jsonify(error='Start the demo application first.'),400
            try:return jsonify(interpret(state,data))
            except ApplicationError as e:return jsonify(error=str(e)),400
            except Exception:return jsonify(error='DCR is unavailable. Please reload to check the current state.'),502
    @app.post('/application/edit')
    def application_edit():
        sid=request.headers.get('X-Session-ID');data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(error='Invalid request.'),400
        with lock:
            state=session_store.get(sid)
            if not state or 'application_answers' not in state:return jsonify(error='Start the demo application first.'),400
            try:return jsonify(edit(state,data))
            except ApplicationError as e:return jsonify(error=str(e)),400
            except Exception:return jsonify(error='DCR is unavailable. Please reload to check the current state.'),502
    @app.post('/application/answer')
    def application_answer():
        sid=request.headers.get('X-Session-ID');data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(error='Invalid request.'),400
        with lock:
            state=session_store.get(sid)
            if not state or 'application_answers' not in state:return jsonify(error='Start the demo application first.'),400
            try:return jsonify(answer(state,data,source=data.get('source') or 'typed'))
            except ApplicationError as e:return jsonify(error=str(e)),400
            except Exception:return jsonify(error='DCR is unavailable. Please reload to check the current state.'),502
