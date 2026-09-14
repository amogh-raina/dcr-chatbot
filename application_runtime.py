"""Demo application fields driven only by the live DCR event API.
No LLM, local XML, real authentication, file contents, or external submission.
"""
from datetime import date
import math
import re
import secrets
import threading
import dcr_repository as repo
from faq_runtime import groups, choices, marking

class ApplicationError(ValueError):
    pass

def fetch(state):
    payload=repo.get_raw_events(state)
    if not isinstance(payload,dict) or not isinstance(payload.get('events'),list) or not all(isinstance(e,dict) for e in payload['events']):
        raise ApplicationError('DCR did not return application fields.')
    return payload

def active(e):
    return e.get('included') is True and e.get('enabled') is True and e.get('pending') is True

def describe(e):
    tags=groups(e); dtype=e.get('dataType','').lower()
    if 'ApplicationDemoFile' in tags: dtype='demo_file'
    if 'ApplicationSubmit' in tags: dtype='submit'
    supported={'date','text','longtext','textbox','email','int','integer','float','choice','boolean','bool','demo_file','submit'}
    if dtype not in supported: raise ApplicationError('This field type is not supported by the demo: '+dtype)
    result=dict(id=e['id'],label=e.get('label',''),type=dtype,hours='ApplicationHours' in tags)
    if dtype=='choice':result['options']=[dict(label=c['question'],value=c['value']) for c in choices(e)]
    return result

def view(state,payload):
    if state.get('application_result'):
        return state['application_result']
    terminal=[e for e in payload['events'] if active(e) and groups(e)&{'ApplicationComplete','ApplicationDeclined'}]
    if len(terminal)==1:
        state.pop('application_prompt',None)
        if not repo.execute_raw_event(state,terminal[0]['id'],''):
            raise ApplicationError('DCR could not acknowledge the final demo message.')
        state['application_result'] = dict(application=True,status='complete' if 'ApplicationComplete' in groups(terminal[0]) else 'declined',response=terminal[0]['label'],demo_notice='Demonstration only. Nothing was submitted and no e-Boks message will be sent.')
        return state['application_result']
    fields=[e for e in payload['events'] if active(e) and 'ApplicationField' in groups(e)]
    if len(fields)!=1:raise ApplicationError('DCR must provide exactly one next application field. Please check the imported demo graph.')
    field=describe(fields[0]);ticket=secrets.token_urlsafe(24)
    state['application_prompt']=dict(ticket=ticket,marking=marking(payload),field=field)
    return dict(application=True,status='review' if field['type']=='submit' else 'question',field=field,prompt_id=ticket,answers=state.get('application_answers',[]))

def start(state):
    payload=fetch(state)
    forms=[e for e in payload['events'] if 'ApplicationForm' in groups(e)]
    if len(forms)!=1:raise ApplicationError('Import SU_handicaptillaeg_FAQ_Application_Demo.xml and use its graph ID. This graph has no configured demo application.')
    links=[g for g in groups(forms[0]) if g.startswith('ApplicationStart:')]
    if len(links)!=1:raise ApplicationError('Missing application entry link in DCR.')
    _,eid,value=links[0].split(':',2)
    home=next((e for e in payload['events'] if e['id']==eid),None)
    if not home or home.get('enabled') is not True or not any(c['value']==value for c in choices(home)):
        raise ApplicationError('The application entry is not available.')
    if not repo.execute_raw_event(state,eid,value):raise ApplicationError('DCR could not start the application.')
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
        found=[o for o in field['options'] if o['value']==value]
        if len(found)!=1:raise ApplicationError('Choose one of the displayed options.')
        display=found[0]['label']
    elif dtype in ('bool','boolean'):
        if value not in ('true','false'):raise ApplicationError('Choose Yes or No.')
    elif dtype=='date':
        try:date.fromisoformat(value)
        except ValueError:raise ApplicationError('Enter a valid date.')
    elif dtype in ('int','integer','float'):
        try:number=float(value)
        except ValueError:raise ApplicationError('Enter a number.')
        if not math.isfinite(number) or (dtype in ('int','integer') and not number.is_integer()):raise ApplicationError('Enter a valid number.')
        if field['hours'] and not 0<=number<=168:raise ApplicationError('Hours per week must be between 0 and 168.')
    elif dtype=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ApplicationError('Enter a valid email address.')
    elif dtype=='demo_file':
        if len(value)>200 or '/' in value or '\\' in value:raise ApplicationError('Use a filename only, up to 200 characters.')
    elif dtype=='text' and len(value)>50:raise ApplicationError('Use up to 50 characters for this field.')
    return value,display

def answer(state,data):
    issued=state.get('application_prompt')
    if not issued or data.get('prompt_id')!=issued['ticket']:raise ApplicationError('This question has changed. Reload the application.')
    payload=fetch(state)
    if marking(payload)!=issued['marking']:raise ApplicationError('DCR state changed. Reload the application.')
    field=issued['field'];value,display=validated(field,data.get('value'))
    if not repo.execute_raw_event(state,field['id'],value):raise ApplicationError('DCR could not save this answer. Please retry.')
    state.pop('application_prompt',None)
    if field['type']!='submit':state['application_answers'].append(dict(label=field['label'],value=display))
    return view(state,fetch(state))

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
            state['simulation_id']=repo.create_simulation(state)
            if not state['simulation_id']:raise ApplicationError('DCR could not create the application session.')
            result=start(state)
            with lock:session_store[sid]=state
            return jsonify(result)
        except ApplicationError as e:return jsonify(error=str(e)),400
        except Exception:return jsonify(error='DCR is unavailable. Please try again.'),502
    @app.post('/application/answer')
    def application_answer():
        sid=request.headers.get('X-Session-ID');data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(error='Invalid request.'),400
        with lock:
            state=session_store.get(sid)
            if not state or 'application_answers' not in state:return jsonify(error='Start the demo application first.'),400
            try:return jsonify(answer(state,data))
            except ApplicationError as e:return jsonify(error=str(e)),400
            except Exception:return jsonify(error='DCR is unavailable. Please reload to check the current state.'),502
