"""Demo application fields driven only by the live DCR event API.
No LLM, local XML, real authentication, file contents, or external submission.
"""
from datetime import date
import math
import logging
import os
import re
import secrets
import threading
import dcr_repository as repo
import faq_runtime as faq
import interaction_log as ilog
import openchat
from faq_runtime import groups, choices

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

# Shown when the matcher finds nothing. Kept here (not in DCR) by decision;
# move it to a DCR label event when the out-of-scope activity is modelled.
OUT_OF_SCOPE=("I couldn\u2019t find an answer to that in this chatbot\u2019s SU disability supplement FAQs. "
              "You can ask about eligibility, documentation, applying, or payments, "
              "or continue with the question above.")

# Diagnostic escape hatch. With APPLICATION_ENABLED_FALLBACK=1 the handler
# falls back to a single included+enabled step when nothing is pending, which
# is how the demo behaved before. It exists to walk past the entry defect and
# observe whether responses *inside* Form0 set pending. Leave it off normally:
# running on the fallback hides exactly the bug we are chasing.
ENABLED_FALLBACK=os.getenv('APPLICATION_ENABLED_FALLBACK')=='1'

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

def describe(e):
    tags=groups(e); dtype=e.get('dataType','').lower()
    if 'ApplicationDemoFile' in tags: dtype='demo_file'
    if 'ApplicationSubmit' in tags or dtype == 'button' or str(e.get('id', '')).endswith(':A10'): dtype='submit'
    supported={'date','text','longtext','textbox','email','int','integer','float','choice','boolean','bool','file','demo_file','submit','button'}
    if dtype == 'button': dtype = 'submit'
    if dtype not in supported: raise ApplicationError('This field type is not supported by the demo: '+dtype)
    is_hours = 'ApplicationHours' in tags or 'hour' in e.get('label', '').lower() or 'timer' in e.get('label', '').lower()
    result=dict(id=e['id'],label=e.get('label',''),type=dtype,hours=is_hours)
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
    if not eid or not value:
        raise ApplicationError('The application entry is not available.')
    home=next((e for e in payload['events'] if e['id']==eid),None)
    if not home or home.get('enabled') is not True:
        raise ApplicationError('The application entry is not available.')
    if not repo.execute_raw_event(state,eid,value):raise ApplicationError('DCR could not start the application.')
    log.info('Application entry executed graph=%s simulation=%s event=%s',
             state.get('graph_id'), state.get('simulation_id'), eid)
    if state.get('interaction'):
        state['interaction']['shown'] = {}
    state['application_answers']=[]
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
        return dict(application=True,status='not_interpreted',
                    response=explanation or 'I could not work out a value from that. Please enter it directly.')
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
    """Application state as matcher context.

    Both parts come from the graph: answered fields are executed application
    events, the current stage is the pending one. Nothing is stored in parallel.
    NOTE: this sends the user's application answers to the matcher provider.
    """
    issued=state.get('application_prompt') or {}
    stage=(issued.get('field') or {}).get('label','')
    answered='; '.join(f"{a['label']}: {a['value']}" for a in (state.get('application_answers') or [])[-8:])
    parts=['The user is completing the SU disability supplement application.']
    if stage:parts.append('They are currently being asked: '+stage)
    if answered:parts.append('They have already answered: '+answered)
    return ' '.join(parts)

def ask(state,data):
    """Answer an FAQ question mid-application. Never touches application state."""
    message=data.get('message')
    if not isinstance(message,str) or not message.strip() or len(message)>8000:
        raise ApplicationError('Please enter a question of 1\u20138000 characters.')
    payload=fetch(state)
    try:
        candidates=faq.catalogue(payload)
    except faq.StateError:
        raise ApplicationError('Question matching is not configured for this graph.')
    try:
        decision,rows=openchat.rank(message,context_for(state),candidates)
    except (openchat.MatchError,ValueError) as error:
        log.warning('Application question matching failed type=%s',type(error).__name__)
        raise ApplicationError('Question matching is temporarily unavailable. Please continue with the question above.')
    if decision=='no_match':
        log.info('Application question out_of_scope')
        ilog.record(state,'faq_ask',message=message.strip(),decision='no_match')
        return dict(application=True,status='faq_no_match',response=OUT_OF_SCOPE)
    by_key={c['candidate_key']:c for c in candidates}
    selected=[by_key[r['candidate_key']] for r in rows]
    ilog.record(state,'faq_ask',message=message.strip(),decision=decision,
                candidates=[c['question'] for c in selected])
    match_id=secrets.token_urlsafe(24)
    state['application_match']=dict(id=match_id,candidates=selected)
    return dict(application=True,
                status='faq_confirm' if decision=='single_match' else 'faq_clarify',
                response='Is this the question you mean?' if decision=='single_match'
                         else 'I\u2019m not entirely sure. Did you mean one of these?',
                match_id=match_id,
                candidates=[dict(candidate_key=c['candidate_key'],question=c['question']) for c in selected])

def confirm(state,data):
    """Execute the confirmed canonical question and return its DCR answer verbatim."""
    issued=state.get('application_match')
    if not issued or data.get('match_id')!=issued['id']:
        raise ApplicationError('That question has expired. Please ask again.')
    chosen=[c for c in issued['candidates'] if c['candidate_key']==data.get('candidate_key')]
    if len(chosen)!=1:raise ApplicationError('Choose one of the displayed questions.')
    candidate=chosen[0];state.pop('application_match',None)
    payload=fetch(state);before=application_marking(payload)
    selector=next((e for e in payload['events'] if e['id']==candidate['event_id']),None)
    if not selector or selector.get('enabled') is not True:
        raise ApplicationError('The question selector is not available.')
    if not repo.execute_raw_event(state,candidate['event_id'],candidate['value']):
        raise ApplicationError('DCR could not look up that question.')
    payload=fetch(state)
    answers=[e for e in payload['events'] if 'FAQAnswer' in groups(e) and e.get('pending') is True
             and e.get('included') is True]
    if len(answers)!=1:
        raise ApplicationError('DCR did not return a single answer for that question.')
    answer_event=answers[0]
    # The body is the description. The label is only the question title, which
    # is why the answer appeared as a repeated heading with no content.
    text=answer_event.get('description')
    if not isinstance(text,str) or not text:
        raise ApplicationError('DCR did not return the answer text.')
    # Acknowledge so the answer does not stay pending.
    if not repo.execute_raw_event(state,answer_event['id'],''):
        raise ApplicationError('DCR could not acknowledge the answer.')
    payload=fetch(state)
    if application_marking(payload)!=before:
        # The graph has no FAQ-to-Form0 relation, so this should be unreachable.
        log.error('FAQ interjection changed application marking graph=%s simulation=%s',
                  state.get('graph_id'),state.get('simulation_id'))
        raise ApplicationError('The application state changed unexpectedly. Reload the application.')
    log.info('Application FAQ interjection answered event=%s',answer_event['id'])
    ilog.record(state,'faq_answer',question=candidate['question'],
                answer_event=answer_event['id'],
                during=((state.get('application_prompt') or {}).get('field') or {}).get('id'))
    result=view(state,payload)
    result['faq_response']=text
    result['faq_question']=candidate['question']
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
            ilog.start(state,gid,state['simulation_id'])
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
