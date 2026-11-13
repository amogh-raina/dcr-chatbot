# dcr_repository.py
"""
Module for interacting with the DCR Active Repository.
"""

import requests
import xml.etree.ElementTree as ET
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dcrai import paths
from dcrai.observability.redaction import redact
import dcrai.observability.turn_trace as turn_trace

# The entry point configures logging; importing this adapter must not enable DEBUG globally.

# Reused across requests so repeated calls to the same DCR host (several per
# user interaction: refresh, execute, refresh again, ...) keep the TCP/TLS
# connection alive instead of renegotiating it every time.
_session = requests.Session()


def _auth_headers(state: Dict[str, Any], content_type: Optional[str] = None) -> Dict[str, str]:
    """Build auth headers used by repository requests."""
    headers = {
        'X-DCR-AuthToken': state["api_key"],
    }
    if state.get("token"):
        headers['Authorization'] = f'Bearer {state["token"]}'
    if content_type:
        headers['Content-Type'] = content_type
    return headers

def get_graph(state) -> ET.Element:
    """
    Retrieve a graph from the DCR Active Repository.

    Parameters:
        id (int): The ID of the graph.
        root_url (str): The root URL of the DCR repository.
        api_key (str): The API key for authentication.
        token (str): The authentication token.

    Returns:
        ET.Element: The parsed XML content of the graph if successful, None otherwise.
    """
    headers = _auth_headers(state, content_type='application/xml')

    response = _session.get(f"{state['root_url']}api/graphs/{state['graph_id']}", headers=headers)

    if response.status_code == 200:
        return ET.fromstring(response.content)
    else:
        logging.error(f"Failed to get graph: {response.status_code}")
        return None

def _sim_url(state, suffix: str = '') -> str:
    """Base of the new simulation engine: /api/graphs/{id}/simulation[...].

    The old /sims/ engine is not used: it never runs Robots or their effects.
    """
    return f"{state['root_url']}api/graphs/{state['graph_id']}/simulation{suffix}"


def create_simulation(state) -> int:
    """Create a simulation: POST /api/graphs/{id}/simulation.

    Returns the simulation ID from the X-DCR-simulation-ID header, 0 on failure.
    """
    headers = {**_auth_headers(state), 'Content-Length': '0'}
    response = _session.post(_sim_url(state), headers=headers, timeout=30)
    if response.status_code == 201:
        simulation_id_str = response.headers.get('X-DCR-simulation-ID')
        state.pop('event_roles', None)
        return int(simulation_id_str) if simulation_id_str else 0
    logging.error(f"Failed to create simulation: {response.status_code}")
    logging.error(f"Response body: {response.text[:500]}")
    logging.error(f"Request URL: {_sim_url(state)}")
    logging.error(f"Auth headers: X-DCR-AuthToken present: {bool(state.get('api_key'))}, Bearer token present: {bool(state.get('token'))}")
    return 0


def _remember_roles(state, payload):
    """Cache each event's first role from the live event list.

    The /simulation/ engine needs a role in the execute body for any event
    whose execution runs a Robot with an effect; without it DCR answers 500
    "Value cannot be null. (Parameter 'input')". Events without a role are
    executed without one.
    """
    if isinstance(payload, dict) and isinstance(payload.get('events'), list):
        roles = state.setdefault('event_roles', {})
        for event in payload['events']:
            first = next((r.strip() for r in str(event.get('roles') or '').split(',') if r.strip()), '')
            roles[event.get('id')] = first
    return payload


def _prepare_event_payload(state, payload):
    """Bridge XML activity-backed choices when the events API omits their enum."""
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        return payload
    from dcrai.chat.faq_runtime import is_faq
    if state.get('faq_mode') or is_faq(payload):
        state['faq_mode'] = True
        return payload
    try:
        root = ET.fromstring(state.get("graph_xml") or "<dcrgraph/>")
    except ET.ParseError:
        return payload
    bindings = {
        event.get("id"): dtype.get("dataSetActivity")
        for event in root.findall("./specification/resources/events//event")
        for dtype in event.findall("./custom/eventData/dataType")
        if dtype.text == "choice" and dtype.get("dataSetActivity")
    }
    events = {event.get("id"): event for event in payload["events"]}
    watched = set(bindings) | set(bindings.values())
    # Capture before hydration so a missing repository enum remains visible.
    watched.update(e.get("id") for e in payload["events"]
                   if e.get("pending") and e.get("dataType") == "label")
    snapshot = [{key: event.get(key) for key in
                 ("id", "dataType", "value", "displayValue", "description",
                  "choiceValues", "executed", "pending", "enabled")}
                for id, event in events.items() if id in watched]
    for menu_id, source_id in bindings.items():
        menu, source = events.get(menu_id), events.get(source_id)
        if not menu or not source or not source.get("executed"):
            continue
        raw = source.get("value")
        try:
            pairs = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(pairs, list) or not pairs:
                continue
            if any(not isinstance(pair, list) or len(pair) != 2
                   or not isinstance(pair[0], (str, int)) or isinstance(pair[0], bool)
                   or not isinstance(pair[1], str) for pair in pairs):
                continue
            # Existing UI enum parser requires labels without parentheses.
            if any(any(char in str(part) for char in "()") for pair in pairs for part in pair):
                continue
            menu["choiceValues"] = ", ".join(f"{label} ({key})" for key, label in pairs)
        except (ValueError, TypeError):
            continue
    if bindings:
        diagnostic = {"bindings": bindings, "raw_events": snapshot,
                      "resolved_choices": {id: events[id].get("choiceValues", "")
                                           for id in bindings if id in events}}
        history = state.setdefault("choice_diagnostics", [])
        history.append(diagnostic)
        del history[:-20]
        try:
            folder = paths.RUNTIME_TRACES
            folder.mkdir(parents=True, exist_ok=True)
            ids = [re.sub(r"[^A-Za-z0-9_-]", "_", str(state.get(k, "unknown")))
                   for k in ("graph_id", "simulation_id")]
            (folder / ("choice_diagnostics_" + "_".join(ids) + ".json")).write_text(
                json.dumps(redact(history), indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as error:
            logging.warning("Could not save choice diagnostics: %s", error)
    return payload


def _enrich_events_from_xml(state, payload):
    """Enrich live simulation events with XML-defined metadata if available."""
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        return payload
    raw_xml = state.get("graph_xml")
    if not raw_xml:
        return payload
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return payload

    xml_events = {e.get("id"): e for e in root.findall(".//events//event")}
    for event in payload["events"]:
        eid = event.get("id")
        if eid in xml_events:
            x_ev = xml_events[eid]
            dtype = x_ev.find("./custom/eventData/dataType")
            if dtype is not None and dtype.get("multiple") == "true":
                event["multiple"] = "true"
    return payload


def _get_event_list(state):
    """GET /api/graphs/{id}/simulation/{simid}/event (raw JSON) or None."""
    response = _session.get(_sim_url(state, f"/{state['simulation_id']}/event"),
                            headers=_auth_headers(state), timeout=30)
    if response.status_code != 200:
        logging.error(f"Failed to get simulation events: {response.status_code}")
        return None
    return _remember_roles(state, response.json())


def get_raw_events(state):
    """FAQ boundary: raw simulation JSON, never XML choice hydration."""
    response = _session.get(_sim_url(state, f"/{state['simulation_id']}/event"),
                            headers=_auth_headers(state), timeout=30)
    response.raise_for_status()
    return _enrich_events_from_xml(state, _remember_roles(state, response.json()))


def execute_raw_event(state, event_id, value, comment='', role=None):
    """Execute through POST /api/graphs/{id}/simulation/{simid}/event.

    Sends the event's own role (from the last event list read) unless one is
    given. Never consults graph XML.
    """
    body = {'eventId': event_id, 'eventValue': value, 'comment': comment, 'isNull': False}
    role = role if role is not None else state.get('event_roles', {}).get(event_id, '')
    if role:
        body['role'] = role
    started, at = time.monotonic(), datetime.now(timezone.utc).astimezone().isoformat(timespec='milliseconds')
    try:
        response = _session.post(
            _sim_url(state, f"/{state['simulation_id']}/event"),
            headers=_auth_headers(state, content_type='application/json'),
            json=body, timeout=60)
    except Exception:
        _trace_event(event_id, value, comment, False, at, started)
        raise
    if response.status_code != 204:
        logging.error(f"Failed to execute {event_id}: {response.status_code} {response.text[:300]}")
    _trace_event(event_id, value, comment, response.status_code == 204, at, started)
    return response.status_code == 204


def _trace_event(event_id, value, comment, ok, at, started):
    """Add this execution to the open turn record (spec 02, R15). Never raises, never changes the result."""
    try:
        turn_trace.add_dcr_event(dict(id=event_id, value=value, comment=comment, ok=ok, at=at,
                                      latency_s=round(time.monotonic() - started, 3)))
    except Exception:
        logging.warning('DCR event not traced', exc_info=False)


def get_events(state) -> Optional[dict]:
    """Event list for the chatbot, with choice hydration for activity-backed menus."""
    payload = _get_event_list(state)
    return None if payload is None else _prepare_event_payload(state, payload)


def get_simulation_events(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Event list for runtime traces (same /simulation/ route as get_events)."""
    return get_events(state)


def execute_event(state, event_id: str, value: str, comment: str) -> bool:
    """Execute an event on the /simulation/ engine.

    Activity-backed choice menus used to go through the old /sims/ engine with
    DataXML; everything now uses the same /simulation/ call as execute_raw_event.
    """
    ok = execute_raw_event(state, event_id, value, comment)
    if ok:
        logging.info(f"******Event executed: {event_id}")
    return ok
