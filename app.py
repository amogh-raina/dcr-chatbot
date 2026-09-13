from flask import Flask, request, render_template, jsonify, send_from_directory, session, abort
import logging
from typing import Optional, Any, Dict
import random
from dotenv import load_dotenv
import json
import time
import re
import dcr_repository as dcrrepo
import questions as quest
import utility as utility
import chatnlp as chatnlp
import faq_runtime
import threading
from datetime import datetime
import os

from waitress import serve
load_dotenv()
try:
    from external_scripts import graph_parser
except ModuleNotFoundError as error:
    if error.name not in ('external_scripts', 'external_scripts.graph_parser'):
        raise
    graph_parser = None


def parse_graph_for_review(graphxml, state):
    """Optional local tooling; shared chatbot does not depend on cached XML parsing."""
    if graph_parser is not None:
        graph_parser.parse_graph_async(graphxml, state)


app = Flask(__name__)

api_key = os.getenv("API_KEY")
token = os.getenv("TOKEN")
root_url = os.getenv("ROOT_URL")
TRACE_DIR = "runtime_traces"

# Store for tab-specific sessions
tab_sessions = {}

def get_session_id():
    """Get session ID from request header"""
    return request.headers.get('X-Session-ID')

def get_tab_session(session_id):
    """Get or create tab-specific session"""
    if session_id not in tab_sessions:
        tab_sessions[session_id] = {}
    return tab_sessions[session_id]

def set_tab_session(session_id, key, value):
    """Set value in tab-specific session"""
    if session_id not in tab_sessions:
        tab_sessions[session_id] = {}
    tab_sessions[session_id][key] = value


def _safe_fragment(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "unknown"))


def _persist_runtime_trace_file(
    session_id: str,
    graph_id: Any,
    simulation_id: Any,
    trace_kind: str,
    payload: Any
) -> Optional[str]:
    try:
        os.makedirs(TRACE_DIR, exist_ok=True)
        filename = (
            f"{_safe_fragment(trace_kind)}_{_safe_fragment(graph_id)}_{_safe_fragment(simulation_id)}_"
            f"{_safe_fragment(session_id)}.json"
        )
        filepath = os.path.join(TRACE_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)
        return filepath
    except Exception as e:
        logging.warning(f"Failed to persist runtime trace file ({trace_kind}): {str(e)}")
        return None


def _persist_raw_final_state_file(
    session_id: str,
    graph_id: Any,
    simulation_id: Any,
    final_state: Dict[str, Any]
) -> Optional[str]:
    """Backward-compatible wrapper for existing raw final state file naming."""
    return _persist_runtime_trace_file(
        session_id=session_id,
        graph_id=graph_id,
        simulation_id=simulation_id,
        trace_kind="raw_final_state",
        payload=final_state
    )


def _collect_and_persist_runtime_traces(tab_session: Dict[str, Any], session_id: str) -> Dict[str, Optional[str]]:
    """Collect simulation payloads and persist them under runtime_traces/."""
    graph_id = tab_session.get("graph_id")
    simulation_id = tab_session.get("simulation_id")
    traces: Dict[str, Any] = {
        "sim": None,
        "log": None,
        "events": None,
    }

    try:
        sim_payload = dcrrepo.get_simulation_payload(tab_session)
        if sim_payload is not None:
            traces["sim"] = _persist_runtime_trace_file(
                session_id=session_id,
                graph_id=graph_id,
                simulation_id=simulation_id,
                trace_kind="sim_payload",
                payload=sim_payload
            )
        else:
            traces["sim"] = _persist_runtime_trace_file(
                session_id=session_id,
                graph_id=graph_id,
                simulation_id=simulation_id,
                trace_kind="sim_payload_error",
                payload={
                    "error": "Simulation payload endpoint returned no data",
                    "attempted_endpoints": [
                        f"/api/graphs/{graph_id}/sims/{simulation_id}",
                        f"/api/graphs/{graph_id}/simulation/{simulation_id}"
                    ]
                }
            )
    except Exception as e:
        logging.warning(f"Failed to collect simulation payload: {str(e)}")
        traces["sim"] = _persist_runtime_trace_file(
            session_id=session_id,
            graph_id=graph_id,
            simulation_id=simulation_id,
            trace_kind="sim_payload_error",
            payload={
                "error": f"Exception while collecting simulation payload: {str(e)}",
                "attempted_endpoints": [
                    f"/api/graphs/{graph_id}/sims/{simulation_id}",
                    f"/api/graphs/{graph_id}/simulation/{simulation_id}"
                ]
            }
        )

    try:
        sim_log = dcrrepo.get_simulation_log(tab_session)
        if sim_log is not None:
            traces["log"] = _persist_runtime_trace_file(
                session_id=session_id,
                graph_id=graph_id,
                simulation_id=simulation_id,
                trace_kind="sim_log",
                payload=sim_log
            )
    except Exception as e:
        logging.warning(f"Failed to collect simulation log: {str(e)}")

    try:
        sim_events = dcrrepo.get_simulation_events(tab_session)
        if sim_events is not None:
            traces["events"] = _persist_runtime_trace_file(
                session_id=session_id,
                graph_id=graph_id,
                simulation_id=simulation_id,
                trace_kind="sim_events",
                payload=sim_events
            )
            # Keep the events payload in session for any downstream use.
            set_tab_session(session_id, "simulation_state", sim_events)
        else:
            traces["events"] = _persist_runtime_trace_file(
                session_id=session_id,
                graph_id=graph_id,
                simulation_id=simulation_id,
                trace_kind="sim_events_error",
                payload={
                    "error": "Simulation events endpoint returned no data",
                    "attempted_endpoints": [
                        f"/api/graphs/{graph_id}/sims/{simulation_id}/events",
                        f"/api/graphs/{graph_id}/simulation/{simulation_id}/event"
                    ]
                }
            )
    except Exception as e:
        logging.warning(f"Failed to collect simulation events: {str(e)}")
        traces["events"] = _persist_runtime_trace_file(
            session_id=session_id,
            graph_id=graph_id,
            simulation_id=simulation_id,
            trace_kind="sim_events_error",
            payload={
                "error": f"Exception while collecting simulation events: {str(e)}",
                "attempted_endpoints": [
                    f"/api/graphs/{graph_id}/sims/{simulation_id}/events",
                    f"/api/graphs/{graph_id}/simulation/{simulation_id}/event"
                ]
            }
        )

    return traces

# Error Handlers
@app.errorhandler(400)
def bad_request(error):
    logging.error(f'400 Error: {error}')
    return jsonify({'error': 'Bad Request', 'message': str(error)}), 400

@app.errorhandler(404)
def not_found(error):
    logging.error(f'404 Error: {error}')
    return jsonify({'error': 'Resource Not Found', 'message': 'The requested resource could not be found'}), 404

@app.errorhandler(500)
def internal_server_error(error):
    logging.error(f'500 Error: {error}')
    return jsonify({'error': 'Internal Server Error', 'message': 'An internal error occurred. Please try again later.'}), 500

@app.errorhandler(Exception)
def handle_exception(error):
    logging.error(f'Unhandled Exception: {error}')
    return jsonify({'error': 'Server Error', 'message': str(error)}), 500

def faq_response(state, data):
    # Serialize matching/confirmation/execution within each browser session.
    with state.setdefault('faq_lock', threading.RLock()):
        try:
            return jsonify(faq_runtime.handle(state, data))
        except faq_runtime.StateError as error:
            logging.warning('FAQ state validation failed: %s marking=%s', error, state.get('simulation_state'))
            return jsonify({'faq': True, 'status': 'graph_state_error',
                            'error': str(error)}), 409
        except Exception as error:
            logging.error('FAQ operation failed type=%s', type(error).__name__)
            return jsonify({'faq': True, 'status': 'graph_state_error',
                            'error': 'The FAQ service is unavailable. Please try again.'}), 502


@app.route('/chat', methods=['POST'])
def chat_reply():
    session_id = get_session_id()
    tab_session = get_tab_session(session_id)
    
    if tab_session.get('faq_mode'):
        return faq_response(tab_session, request.get_json(silent=True) or {})

    # Debug: Check what's in the session
    logging.debug(f"Session ID: {session_id}")
    logging.debug("Tab session initialized: %s", bool(tab_session))
    
    # Check if required keys exist
    if not tab_session.get("api_key"):
        logging.error(f"Missing api_key in session {session_id}")
        return jsonify({'error': 'Session expired or invalid'}), 400
    
    #the user replied and we interpret the message
    retry = False

    # now we start chatting, i.e. we receive a response from the user
    datatype = None
    enum = None
    conclusion = None
    event_id = tab_session.get("event_id")
    question = tab_session.get("question")
    lang = tab_session.get("graph_language") or "da"
    simulation_state = tab_session.get("simulation_state")
    
    try:
        simulation_id = request.json.get('simulation_id')  # Retrieve simulation_id from the request
    except Exception as e:
        logging.error(f'Failed to retrieve simulation_id. Error: {str(e)}')
        abort(500, f'Failed to retrieve simulation_id: {str(e)}')

    # the message is the text input by the user, value is the predefined answer given as options
    # if the user replies with a value, the value of the button is returned in msg_text
    # e.g. if the user replies with "Yes" button, the label of the button is returned in message (Yes), and value in value (1)
    # if the user replies with a message, value is None
    msg_text = request.json.get('message') # txt input from the user
    msg_value = request.json.get('value') # predefined answer given as options
    
    # Track if the user used free-text (not a choice button)
    user_used_freetext = msg_value is None
    
    chat_result = {}
    comment = ""
    replyvalue = None
    logging.info(f'CHAT message={msg_text}, value={msg_value}, simulation_id={simulation_id}, event_id={event_id}')
    interpreted_event = utility.get_event(event_id, simulation_state)
    # A request to see the menu is not a selection and must not execute it.
    menu_request = re.sub(r"[^a-z ]", "", (msg_text or "").lower()).strip()
    if (msg_value is None and interpreted_event.get("dataType") == "choice"
            and menu_request in {"what are the other topics", "what are my options",
                                 "show options", "show topics", "what topics are available"}):
        return jsonify(ask_question(session_id))
    
    # Use elifs and only interpret integer/int replies
    if interpreted_event.get('dataType') == 'longtext':
        msg_value = msg_text
    elif interpreted_event.get('dataType') == 'text':
        msg_value = msg_text
    elif interpreted_event.get('dataType') == 'integer' or interpreted_event.get('dataType') == 'int' or msg_value is None:
        msg_value, chat_result, retry, comment = chatnlp.convert_msg_to_value(event_id, simulation_state, msg_text, tab_session)

        # Free text can match a different enabled question than the one
        # currently displayed (for example FAQ_GlobalQuestion while FAQ_Home
        # is pending).  Keep the event selected by the interpreter so the
        # confirmation label and the eventual DCR execution use the same
        # choice dictionary.  A button reply has an explicit value for the
        # current event and must not be redirected.
        matched_event_id = chat_result.get('questionid') if isinstance(chat_result, dict) else None
        if user_used_freetext and msg_value is not None and matched_event_id:
            matched_event = utility.get_event(matched_event_id, simulation_state)
            if (
                matched_event is not None
                and matched_event.get('enabled')
                and matched_event.get('dataType') not in (None, '', 'label')
            ):
                event_id = matched_event_id
                interpreted_event = matched_event
                question = quest.get_question(matched_event)
                set_tab_session(session_id, "event_id", event_id)
                set_tab_session(session_id, "question", question)
                logging.info(
                    "Free-text interpretation redirected to event_id=%s, value=%s",
                    event_id,
                    msg_value,
                )
        
        # Only allow integer values for integer/int events
        def safe_int(val):
            try:
                return int(val)
            except (ValueError, TypeError):
                return None
        
        if msg_value is not None and (interpreted_event.get('dataType') == 'integer' or interpreted_event.get('dataType') == 'int'):
            int_value = safe_int(msg_value)
            if int_value is None:
                if lang.lower().startswith("en"):
                    comment = f"The answer '{msg_value}' is not a valid integer. Please enter a number."
                elif lang.lower().startswith("es"):
                    comment = f"La respuesta '{msg_value}' no es un entero válido. Por favor ingresa un número."
                else:
                    comment = f"Svaret '{msg_value}' er ikke et gyldigt heltal. Indtast venligst et tal."
                return jsonify({'response': question, "enum": interpreted_event.get("choiceValues", ""), "datatype": interpreted_event.get('dataType'),
                                 "comment":comment, 'confirm': False, 'event_id': event_id})
            msg_value = int_value
        
        # case 1: the interpretation didn't succeed, and we ask to retry
        if(retry and tab_session.get("tentative", 0) > 0):
            set_tab_session(session_id, "tentative", tab_session.get("tentative") - 1)
            found_event = utility.get_event(event_id, simulation_state)
            return jsonify({'response': question, "enum":found_event.get("choiceValues",""), "datatype":datatype,
                             "comment":comment, 'confirm': False, 'event_id': event_id})
        
        # case 2: the interpretation didn't succeed, the tentatives expired, and we try ask another question
        if(retry and tab_session.get("tentative", 0) == 0):
            found_event = utility.get_next_pending_event(simulation_state, event_id=event_id)
            if(found_event): #there are other pending events
                set_tab_session(session_id, "tentative", 1)
                if lang.lower().startswith("en"):
                    comment = "I did not understand the answer. Let's try another question."
                elif lang.lower().startswith("es"):
                    comment = "No entendí la respuesta. Intentemos con otra pregunta."
                else:
                    comment = "Jeg forstod ikke svaret. Lad os prøve med et andet spørgsmål."
                question = quest.get_question(found_event)
                set_tab_session(session_id, "question", question)
                event_id = found_event['id']
                set_tab_session(session_id, "event_id", event_id)
                datatype = found_event['dataType']
                enum = found_event.get('choiceValues', '')
                logging.info(f'event_id={event_id}, question={question}, datatype={datatype}, enum={enum}')
                return jsonify({'response': question, "comment":comment ,'confirm': False, 
                                'enum': enum, 'datatype': datatype, 'event_id': event_id})
            else:  # there are no other pending events, so we ask again the same
                new_question = ask_question(session_id)
                if lang.lower().startswith("es"):
                    comment = "Es muy importante que respondas a esta pregunta."
                elif lang.lower().startswith("en"):
                    comment = "It is very important that you answer this question. "
                else:
                    comment = "Det er virkelig vigtigt, at du svarer på dette spørgsmål. "
                new_question["comment"] = comment
                return jsonify(new_question)

        # A free-text reply to a choice is an interpretation, not an explicit
        # button selection. Reuse the generic confirmation UI before changing
        # the DCR marking. The confirmed request carries a concrete value and
        # therefore passes through this block on the next call.
        if user_used_freetext and msg_value is not None and interpreted_event.get('dataType') == 'choice':
            interpreted_choice = utility.get_label_from_enum(
                interpreted_event.get('choiceValues', ''), msg_value
            )
            return jsonify({
                'response': question,
                'confirm': True,
                'qvalue': interpreted_choice,
                'value': msg_value,
                'enum': interpreted_event.get('choiceValues', ''),
                'datatype': interpreted_event.get('dataType'),
                'event_id': event_id,
            })

    interpreted_reply = msg_value
    if(interpreted_event.get('dataType') == 'date'):
        try:
            # Try parsing with yyyy-mm-dd format
            date = datetime.strptime(msg_value, "%Y-%m-%d")
        except ValueError:
            try:
                # Try parsing with dd-mm-yyyy format
                date = datetime.strptime(msg_value, "%d-%m-%Y")
            except ValueError:
                interpreted_reply = msg_value
        
        # Format the date as dd-mm-yyyy
        interpreted_reply = date.strftime("%d-%m-%Y")
    elif(interpreted_event.get('choiceValues') != ""):
        interpreted_reply = utility.get_label_from_enum(interpreted_event.get('choiceValues', ''), msg_value)
    elif interpreted_event.get('dataType') == 'integer' or interpreted_event.get('dataType') == 'int':
        # Always use NLP/mapping to get the correct value
        msg_value, chat_result, retry, comment = chatnlp.convert_msg_to_value(event_id, simulation_state, msg_text, tab_session)
    
    # we can execute the event:
    set_tab_session(session_id, "tentative", 1)
    try: 
        if not dcrrepo.execute_event(tab_session, event_id, msg_value, comment):
            raise ValueError("DCR did not accept this answer")
    except Exception as e:
        logging.error(f'### Failed to execute event: {event_id}={msg_value}')
        abort(400, f'Failed to execute event: {event_id}={msg_value}, error: {str(e)}.')

    # Keep runtime state fresh after each execution.
    try:
        latest_state = dcrrepo.get_events(tab_session)
        if latest_state:
            set_tab_session(session_id, "simulation_state", latest_state)
    except Exception as e:
        logging.warning(f'Failed to refresh simulation state after execute_event: {str(e)}')
    
    set_tab_session(session_id, "last_event", {event_id: msg_value})
    
    # Track execution history for this session
    event_timestamp = time.time()
    execution_history = get_tab_session(session_id).get('execution_history', [])
    execution_history.append({
        'event_id': event_id,
        'event_label': interpreted_event.get('label', event_id) if interpreted_event else event_id,
        'value': msg_value,
        'type': 'user',
        'timestamp': event_timestamp
    })
    set_tab_session(session_id, 'execution_history', execution_history)

    # Step-based transition tracing is intentionally disabled in this mode.

    #and I update the inferred replies
    if 'inferred_replies' in chat_result and chat_result['inferred_replies']:
        inferred_replies = tab_session.get('inferred_replies', [])
        inferred_replies.extend(chat_result['inferred_replies'])
        set_tab_session(session_id, 'inferred_replies', inferred_replies)

    # we need to ask the next question
    new_question = ask_question(session_id)
    # Only add interpreted_reply if the user used free-text (not a choice button)
    if user_used_freetext:
        new_question["interpreted_reply"] = interpreted_reply
    return jsonify(new_question)

def ask_question(session_id):
    tab_session = get_tab_session(session_id)
    simulation_state = dcrrepo.get_events(tab_session)
    set_tab_session(session_id, "simulation_state", simulation_state)
    
    # Check for inferred replies in the session
    inferred_replies = tab_session.get('inferred_replies', [])
    logging.debug(f'### inferred replies in session: {inferred_replies}')
    
    for next_inferred_reply in inferred_replies:
        event_id = next_inferred_reply['questionid']
        set_tab_session(session_id, "event_id", event_id)
        found_event = utility.get_event(event_id, simulation_state)
        # check if the event of the inferred reply is still valid, if it's not I skip it and go to the next inferred reply
        if(found_event is not None) and (found_event.get('pending') or found_event.get('IsProductive')):
            # we generate the question for the given event, and we interpret the inferred reply
            inferred_value = next_inferred_reply['value']
            try: 
                question, inferred_reply = quest.get_question_inferred(found_event, inferred_value)
            except Exception as e: 
                logging.error(f'Failed to get inferred question: {str(e)}')
                abort(500, f'Failed to get inferred question: {str(e)}')
            if inferred_reply is not None:
                inferred_replies.pop(0)
                set_tab_session(session_id, 'inferred_replies', inferred_replies)
                logging.info(f'*** Inferred reply: event_id={event_id}, reply={inferred_reply}, value={inferred_value}, question={question}')
                logging.info(f'*** Event of the inferred? {found_event}')
                return ({'response': question, 'confirm': True, 'qvalue': inferred_reply, 'value': inferred_value,
                                'enum': f"Yes ({inferred_value})", 'event_id': event_id, 'datatype': found_event['dataType'], 'enum': found_event.get('choiceValues', '')})
    
    # If we reach this point, we have no inferred replies, and we have to ask the user the next pending question
    found_event = utility.get_pending_event(simulation_state)
    if(found_event):
        if quest.is_information_event(found_event):
            event_id = found_event['id']
            information_text = quest.get_information_text(found_event)
            set_tab_session(session_id, "question", information_text)
            set_tab_session(session_id, "event_id", event_id)
            logging.info(f'Information event_id={event_id}')
            return ({
                'response': information_text,
                'information': True,
                'continue': True,
                'event_id': event_id,
                'datatype': found_event.get('dataType', ''),
            })
        question = quest.get_question(found_event)
        set_tab_session(session_id, "question", question)
        event_id = found_event['id']
        set_tab_session(session_id, "event_id", event_id)
        datatype = found_event.get('dataType', '')
        enum = found_event.get('choiceValues', '')
        logging.info(f'event_id={event_id}, question={question}, datatype={datatype}, enum={enum}')
        return ({'response': question, 'confirm': False, 'enum': enum, 'datatype': datatype, 'event_id': event_id})
    else: # No pending event found
        conclusion = quest.get_conclusion(simulation_state)
        set_tab_session(session_id, "name", None)
        set_tab_session(session_id, "question", None)
        logging.info(f"### No pending event found: {conclusion}")

        trace_files = _collect_and_persist_runtime_traces(tab_session, session_id)
        raw_final_state_file = trace_files.get("events")
        if not raw_final_state_file:
            raw_final_state_file = _persist_raw_final_state_file(
                session_id=session_id,
                graph_id=tab_session.get('graph_id'),
                simulation_id=tab_session.get('simulation_id'),
                final_state=simulation_state
            )

        return ({
            'conclusion': conclusion,
            'raw_final_state_file': raw_final_state_file,
            'simulation_payload_file': trace_files.get("sim"),
            'simulation_log_file': trace_files.get("log"),
            'simulation_events_file': trace_files.get("events"),
        })


@app.route('/continue', methods=['POST'])
def continue_information_event():
    """Execute the currently displayed static-information event and continue."""
    session_id = get_session_id()
    if not session_id:
        return jsonify({'error': 'Missing session ID'}), 400

    tab_session = get_tab_session(session_id)
    if tab_session.get('faq_mode'):
        return jsonify({'error': 'Use the current FAQ controls'}), 409
    if not tab_session.get('api_key'):
        return jsonify({'error': 'Session expired or invalid'}), 400

    data = request.get_json(silent=True) or {}
    event_id = data.get('event_id')
    if not event_id:
        return jsonify({'error': 'Event ID is required'}), 400
    if event_id != tab_session.get('event_id'):
        return jsonify({'error': 'This information item is no longer current'}), 409

    simulation_state = dcrrepo.get_events(tab_session)
    if not simulation_state:
        return jsonify({'error': 'Could not retrieve the current simulation state'}), 502
    set_tab_session(session_id, 'simulation_state', simulation_state)

    event = utility.get_event(event_id, simulation_state)
    if not quest.is_information_event(event):
        return jsonify({'error': 'This event is not an information item'}), 400
    if not utility.is_pending_event(event):
        return jsonify({'error': 'This information item is no longer available'}), 409

    if not dcrrepo.execute_event(tab_session, event_id, '', ''):
        return jsonify({'error': 'DCR could not advance this information item'}), 502

    latest_state = dcrrepo.get_events(tab_session)
    if not latest_state:
        return jsonify({'error': 'DCR did not return an updated simulation state'}), 502
    set_tab_session(session_id, 'simulation_state', latest_state)
    set_tab_session(session_id, 'last_event', {event_id: ''})

    execution_history = tab_session.get('execution_history', [])
    execution_history.append({
        'event_id': event_id,
        'event_label': event.get('label', event_id),
        'value': '',
        'type': 'system',
        'is_system': True,
        'timestamp': time.time(),
    })
    set_tab_session(session_id, 'execution_history', execution_history)

    return jsonify(ask_question(session_id))


@app.route('/edit', methods=['POST'])
def edit_event():
    session_id = get_session_id()
    if not session_id:
        return jsonify({'error': 'Missing session ID'}), 400
    
    tab_session = get_tab_session(session_id)
    if tab_session.get('faq_mode'):
        return jsonify({'error': 'Use the current FAQ controls'}), 409
    confirm = False
    
    try: 
        event_toedit = request.json.get('event_id')
    except Exception as e:
        logging.error(f'No event_id in the request. Error: {str(e)}')
        abort(400, f'Failed to retrieve event_id: {str(e)}')

    if(request.json.get('confirm')):
        confirm = True
        value = event_toedit
    else:
        last_event = tab_session.get("last_event", {})
        if(event_toedit not in last_event.keys()): 
            abort(400, f'No previous reply found') 
        value = last_event[event_toedit]
    
    simulation_state = tab_session.get("simulation_state")
    found_event = utility.get_event(event_toedit, simulation_state)
    lang = tab_session.get("graph_language") or "da"

    if(found_event.get("enabled") is True):
        question = quest.get_question(found_event)
        set_tab_session(session_id, "question", question)
        set_tab_session(session_id, 'inferred_replies', [])
        event_id = found_event['id']
        set_tab_session(session_id, "event_id", event_id)
        datatype = found_event['dataType']
        enum = found_event.get('choiceValues', "")
        
        if(confirm is False): #if this is the edit, I want to return the previous answer, therefore I construct it  
            qvalue = ""
            if enum != "": # If choice value is not empty, we interpret the values 
                try:
                    qvalue = utility.get_label_from_enum(enum, value)
                except ValueError as e:
                    logging.error(f"Invalid enum format: {qvalue}. Error: {str(e)}")
                    qvalue = ""
                    abort(500, f"Problem with parsing the new question. ")
            if datatype == 'date':
                try: 
                    qvalue = utility.get_date_as_string(value)
                except ValueError as e:  # Explicitly catching date parsing errors
                    logging.error(f"Invalid date format: {qvalue}. Error: {str(e)}")
                    qvalue = ""
                    abort(400, f"Invalid date format: {qvalue}. Please use 'YYYY-MM-DD' or 'DD-MM-YYYY'.")
            
            if lang.lower().startswith("en"):
                comment = f"You previously replied '{qvalue}'. You can change your reply."
            elif lang.lower().startswith("es"):
                comment = f"Anteriormente respondiste '{qvalue}'. Puedes cambiar tu respuesta."
            else:
                comment = f"Du svarede tidligere '{qvalue}'. Du kan ændre dit svar."
        else:
            if lang.lower().startswith("en"):
                comment = "You can change the answer of the inferred reply."
            elif lang.lower().startswith("es"):
                comment = "Puedes cambiar la respuesta de la respuesta inferida."
            else:
                comment = "Du kan ændre svaret på det afledte svar."

        return jsonify({'response': question, 'comment':comment, 'confirm': False, 'enum': enum, 'conclusion': None, 'datatype': datatype, 'event_id': event_id})
    else : 
        return jsonify({'error': f'Event {event_id} is not enabled, therefore you cannot modify the reply'}), 304

'''The init function is responsible for initializing a simulation and setting up a chat session. It performs the following key tasks:
    - Retrieves a graph from a repository.
    - Creates a simulation based on the given graph.
    - Retrieve events for a simulation from the DCR Active Repository, i.e. simulation_state
    - Checks for pending events in the simulation.
    - Creates a chat session if a pending event is found.'''
@app.route('/init', methods=['POST'])
def init():
    session_id = get_session_id()
    if not session_id:
        return jsonify({'error': 'Missing session ID'}), 400
    
    # Clear any existing session data for this tab
    tab_sessions[session_id] = {}
    tab_session = get_tab_session(session_id)
    
    # 0. create a new chat session
    data = request.get_json()
    graph_id = data.get('graph_id')
    if not graph_id:
        return jsonify({'error': 'Graph ID is required'}), 400
    
    set_tab_session(session_id, "api_key", api_key)
    set_tab_session(session_id, "token", token)
    set_tab_session(session_id, "root_url", root_url)
    set_tab_session(session_id, "graph_id", graph_id)
    set_tab_session(session_id, "user", "user_" + str(random.randint(1000, 9999)))
    set_tab_session(session_id, "event_id", None)

    # 1. Retrieve graph from repository
    try:
        graphxml = dcrrepo.get_graph(tab_session)
        if graphxml is None:
            logging.error("Graph not found")
            return jsonify({"error": "Graph not found"}), 404
    except Exception as e:
        logging.error(f'Failed to retrieve graph: {str(e)}')
        return jsonify({"error": "Graph not found"}), 404
    
    import xml.etree.ElementTree as ET
    set_tab_session(session_id, 'graph_xml', ET.tostring(graphxml, encoding='unicode'))

    welcome = graphxml.get('title')
   
    graph_language_element = graphxml.find('./specification/resources/custom/graphLanguage')
    if graph_language_element is not None and graph_language_element.text:
        graphLanguage = graph_language_element.text.lower()
        if graphLanguage.startswith("es"):
            graphLanguage = "es"
        elif graphLanguage.startswith("da"):
            graphLanguage = "da"
        else:
            graphLanguage = "en"
    else:
        graphLanguage = "en"
    
    set_tab_session(session_id, "graph_language", graphLanguage)

    # 2. Create simulation
    simulation_id = dcrrepo.create_simulation(tab_session)
    if simulation_id == 0:
        logging.error("Could not create simulation")
        return jsonify({
            "error": "Could not create simulation",
            "graph_language": graphLanguage,
            "welcome": welcome
        }), 500
    
    logging.info(f'simulation_id={simulation_id}, welcome={welcome}')
    set_tab_session(session_id, "simulation_id", simulation_id)

    # 3. Retrieve the DCR simulation state and let the graph's initial marking
    # determine the first question or information event.
    simulation_state = dcrrepo.get_events(tab_session)
    set_tab_session(session_id, "simulation_state", simulation_state)
    if faq_runtime.is_faq(simulation_state):
        # Background parsing remains review-only; FAQ runtime never consumes it.
        parse_graph_for_review(graphxml, tab_session)
        response = faq_runtime.initialize(tab_session, simulation_state)
        response.update(welcome=welcome, simulation_id=simulation_id, graph_language=graphLanguage)
        return jsonify(response)

    found_event = utility.get_pending_event(simulation_state)

    # 4. A graph-driven chatbot must expose an initial pending/productive event.
    if not found_event:
        logging.error("No pending event found during initialization")
        return jsonify({
            "error": "No questions found in the graph.",
            "graph_language": graphLanguage,
            "welcome": welcome
        }), 400
    # otherwise you get the question
    else:
        chat_id = chatnlp.create_chat(100, "x", "", "", tab_session["graph_id"], root_url, api_key, token)
        logging.info(f'ZZZ chat_id={chat_id}')
        if chat_id == None:
            logging.error("Could not create chat")
            abort(500, 'Could not create chat')
        
        set_tab_session(session_id, 'chat_id', chat_id)
        # Format the first pending event as either static information or a question.
        event_id = found_event['id']
        set_tab_session(session_id, "event_id", event_id)
        datatype = found_event.get('dataType', '')
        enum = found_event.get('choiceValues', '') 
        logging.info(f'ZZZ chat_id={chat_id} event_id={event_id}, datatype={datatype}')

        information = quest.is_information_event(found_event)
        question = (
            quest.get_information_text(found_event)
            if information else quest.get_question(found_event)
        )
        set_tab_session(session_id, "question", question)
        
        # Initialize session data
        set_tab_session(session_id, 'inferred_replies', [])  # Empty list to start with
        set_tab_session(session_id, "tentative", 1)
        set_tab_session(session_id, "last_event", {event_id: None})
        
        # Initialize execution history for this session
        set_tab_session(session_id, 'execution_history', [])
        # Step-based transition fields disabled in final-snapshot test mode.
        # set_tab_session(session_id, 'state_transitions', [])
        # set_tab_session(session_id, 'transition_trace_files', [])
        set_tab_session(session_id, 'parsed_graph', None)

        # Start async parsing of graph for canonical JSON in the background
        import xml.etree.ElementTree as ET
        graph_xml_str = ET.tostring(graphxml, encoding='unicode')
        set_tab_session(session_id, 'graph_xml', graph_xml_str)
        # Pass the Element object, not the string.
        parse_graph_for_review(graphxml, tab_session)
        logging.info("Started async graph parsing")

        response = {
            'welcome': welcome,
            'response': question,
            'datatype': datatype,
            'enum': enum,
            'simulation_id': simulation_id,
            'event_id': event_id,
            'graph_language': graphLanguage,
        }
        if information:
            response.update({'information': True, 'continue': True})
        return jsonify(response)

@app.route('/')
def index():
    return render_template(
        "index.html"
    )

@app.route('/demo')
def demo():
    return send_from_directory(
        os.path.join(app.static_folder, "demo"),
        "index.html",
    )

@app.route('/api/validate-graph/<int:graph_id>')
def validate_graph(graph_id):
    try:
        temp_state = {
            "graph_id": graph_id,
            "api_key": api_key,
            "token": token,
            "root_url": root_url
        }
        graphxml = dcrrepo.get_graph(temp_state)
        graph_title = graphxml.get('title', f'Graph {graph_id}')
        return jsonify({
            'valid': True,
            'graph_id': graph_id,
            'title': graph_title
        })
    except Exception as e:
        logging.error(f'Graph {graph_id} not found or invalid: {str(e)}')
        return jsonify({
            'valid': False,
            'error': f'Graph {graph_id} not found or inaccessible'
        }), 404

@app.route('/api/parsed-graph/<int:graph_id>')
def get_parsed_graph(graph_id):
    """Get the cached parsed graph JSON for debugging/viewing"""
    if graph_parser is None:
        return jsonify({'success': False, 'message': 'Optional local graph-review tools are not installed.'}), 404
    try:
        # Get graph XML to compute hash
        temp_state = {
            "graph_id": graph_id,
            "api_key": api_key,
            "token": token,
            "root_url": root_url
        }
        graphxml = dcrrepo.get_graph(temp_state)
        graph_hash = graph_parser.get_graph_hash(graphxml)
        
        # Try to get cached parsed graph
        parsed_graph = graph_parser.get_cached_graph(str(graph_id), graph_hash)
        
        if parsed_graph:
            return jsonify({
                'success': True,
                'graph_id': graph_id,
                'graph_hash': graph_hash,
                'parsed_graph': parsed_graph
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Graph not yet parsed or not found in cache',
                'graph_id': graph_id,
                'graph_hash': graph_hash
            }), 404
            
    except Exception as e:
        logging.error(f'Failed to retrieve parsed graph {graph_id}: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=8080)
