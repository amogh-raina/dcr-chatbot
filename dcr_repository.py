# dcr_repository.py
"""
Module for interacting with the DCR Active Repository.
"""

import requests
import xml.etree.ElementTree as ET
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, Optional

logging.basicConfig(level=logging.DEBUG)

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

def create_simulation(state) -> int:
    """
    Create a simulation for a graph in the DCR Active Repository.

    Parameters:
        id (int): The ID of the graph.
        root_url (str): The root URL of the DCR repository.
        api_key (str): The API key for authentication.
        token (str): The authentication token.

    Returns:
        int: The simulation ID if successful, 0 otherwise.
    """
    headers = _auth_headers(state, content_type='application/xml')
    
    response = _session.post(f"{state['root_url']}api/graphs/{state['graph_id']}/sims", headers=headers)
    
    if response.status_code == 201:
        simulation_id_str = response.headers.get('X-DCR-simulation-ID')
        return int(simulation_id_str) if simulation_id_str else 0
    else:
        logging.error(f"Failed to create simulation: {response.status_code}")
        logging.error(f"Response body: {response.text}")
        logging.error(f"Request URL: {state['root_url']}api/graphs/{state['graph_id']}/sims")
        logging.error(f"Auth headers: X-DCR-AuthToken present: {bool(state.get('api_key'))}, Bearer token present: {bool(state.get('token'))}")
        return 0

def _prepare_event_payload(state, payload):
    """Bridge XML activity-backed choices when the events API omits their enum."""
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        return payload
    from faq_runtime import is_faq
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
            folder = Path(__file__).resolve().parent / "runtime_traces"
            folder.mkdir(exist_ok=True)
            ids = [re.sub(r"[^A-Za-z0-9_-]", "_", str(state.get(k, "unknown")))
                   for k in ("graph_id", "simulation_id")]
            (folder / ("choice_diagnostics_" + "_".join(ids) + ".json")).write_text(
                json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
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


def get_raw_events(state):
    """FAQ boundary: raw simulation JSON, never XML choice hydration."""
    response = _session.get(
        f"{state['root_url']}api/graphs/{state['graph_id']}/simulation/{state['simulation_id']}/event",
        headers=_auth_headers(state), timeout=30)
    response.raise_for_status()
    return _enrich_events_from_xml(state, response.json())


def execute_raw_event(state, event_id, value, comment=''):
    """Execute through the simulation API without consulting graph XML."""
    response = _session.post(
        f"{state['root_url']}api/graphs/{state['graph_id']}/simulation/{state['simulation_id']}/event",
        headers=_auth_headers(state, content_type='application/json'),
        json={'eventId': event_id, 'eventValue': value, 'comment': comment, 'isNull': False},
        timeout=30)
    return response.status_code == 204


def get_events(state) -> dict:
    """
    Retrieve events for a simulation from the DCR Active Repository.

    Parameters:
        id (int): The ID of the graph.
        simulation_id (int): The ID of the simulation.
        root_url (str): The root URL of the DCR repository.
        api_key (str): The API key for authentication.
        token (str): The authentication token.

    Returns:
        dict: The JSON data of events if successful, None otherwise.
    """
    headers = _auth_headers(state)

    response = _session.get(
        f"{state['root_url']}api/graphs/{state['graph_id']}/simulation/{state['simulation_id']}/event",
        headers=headers
    )

    if response.status_code == 200:
        return _prepare_event_payload(state, response.json())

    logging.warning(f"Legacy events endpoint failed: {response.status_code}, trying /sims endpoint")
    return get_simulation_events(state)


def get_simulation_payload(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Retrieve full simulation payload: GET /api/graphs/{id}/sims/{simid}."""
    headers = _auth_headers(state)
    # Prefer /sims endpoint, fallback to legacy /simulation endpoint.
    response = _session.get(
        f"{state['root_url']}api/graphs/{state['graph_id']}/sims/{state['simulation_id']}",
        headers=headers
    )
    if response.status_code == 200:
        return response.json()

    logging.warning(
        f"/sims payload endpoint failed ({response.status_code}), trying /simulation fallback"
    )
    fallback_response = _session.get(
        f"{state['root_url']}api/graphs/{state['graph_id']}/simulation/{state['simulation_id']}",
        headers=headers
    )
    if fallback_response.status_code == 200:
        return fallback_response.json()

    logging.error(
        "Failed to get simulation payload from both endpoints: "
        f"/sims ({response.status_code}), /simulation ({fallback_response.status_code})"
    )
    return None


def get_simulation_log(state: Dict[str, Any]) -> Optional[Any]:
    """Retrieve simulation log: GET /api/graphs/{id}/sims/{simid}/log."""
    headers = _auth_headers(state)
    response = _session.get(
        f"{state['root_url']}api/graphs/{state['graph_id']}/sims/{state['simulation_id']}/log",
        headers=headers
    )

    if response.status_code == 200:
        return response.json()

    logging.error(f"Failed to get simulation log: {response.status_code}")
    return None


def get_simulation_events(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Retrieve all simulation events: GET /api/graphs/{id}/sims/{simid}/events."""
    headers = _auth_headers(state)
    response = _session.get(
        f"{state['root_url']}api/graphs/{state['graph_id']}/sims/{state['simulation_id']}/events",
        headers=headers
    )

    if response.status_code == 200:
        return _prepare_event_payload(state, response.json())

    logging.warning(
        f"/sims events endpoint failed ({response.status_code}), trying legacy /simulation endpoint"
    )
    fallback_response = _session.get(
        f"{state['root_url']}api/graphs/{state['graph_id']}/simulation/{state['simulation_id']}/event",
        headers=headers
    )
    if fallback_response.status_code == 200:
        return _prepare_event_payload(state, fallback_response.json())

    logging.error(
        "Failed to get simulation events from both endpoints: "
        f"/sims/events ({response.status_code}), /simulation/event ({fallback_response.status_code})"
    )
    return None


def execute_event(state, event_id: str, value: str, comment: str) -> bool:
    """
    Execute an event in the DCR Active Repository.

    Parameters:
        id (int): The ID of the graph.
        simulation_id (int): The ID of the simulation.
        event (str): The event to execute.
        data (str): The data to include in the execution.
		comment {str}: Optional comment.
        root_url (str): The root URL of the DCR repository.
        api_key (str): The API key for authentication.
        token (str): The authentication token.

    Returns:
        bool: True if the event was executed successfully, False otherwise.
    """
    headers = _auth_headers(state, content_type='application/json')
    
    if state.get('faq_mode'):
        return execute_raw_event(state, event_id, value, comment)

    # The legacy endpoint drops values for activity-backed choices with no
    # static dictionary. Send typed data to the repository execution endpoint.
    try:
        root = ET.fromstring(state.get("graph_xml") or "<dcrgraph/>")
        event_xml = next((e for e in root.findall("./specification/resources/events//event")
                          if e.get("id") == event_id), None)
        dtype = event_xml.find("./custom/eventData/dataType") if event_xml is not None else None
    except ET.ParseError:
        dtype = None
    if dtype is not None and dtype.text == "choice" and dtype.get("dataSetActivity"):
        value_type = dtype.get("format") or "int"
        if value_type == "int":
            try:
                value = str(int(value))
            except (ValueError, TypeError):
                return False
        store = ET.Element("globalStore")
        ET.SubElement(store, "variable", id=event_id, type=value_type,
                      value=str(value), isNull="false")
        from urllib.parse import quote
        response = _session.post(
            f"{state['root_url']}api/graphs/{state['graph_id']}/sims/"
            f"{state['simulation_id']}/events/{quote(event_id, safe='')}",
            headers=headers, json={"DataXML": ET.tostring(store, encoding="unicode")},
            timeout=30,
        )
        return response.status_code in (200, 204)

    body = {
        'eventId':event_id,
        'eventValue':value,
        'comment':comment,
        'isNull':False
    }
    response = _session.post(f"{state['root_url']}api/graphs/{state['graph_id']}/simulation/{state['simulation_id']}/event", headers=headers, json=body)
    if response.status_code == 204:
        logging.info(f"******Event executed: {event_id}={value}")
        return True
    else:
        logging.error(f"Failed to execute event: {response.status_code}")
        return False
