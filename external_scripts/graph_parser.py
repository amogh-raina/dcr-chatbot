# graph_parser.py
"""
Graph Parser Module.
Converts DCR Graph XML to canonical JSON deterministically.
Includes caching mechanism.
"""

import os
import json
import logging
import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Dict, Any, Iterable, Optional
from datetime import datetime
import threading

logging.basicConfig(level=logging.DEBUG)

# In-memory cache for parsed graphs
# Key: f"{graph_id}_{graph_hash}"
# Value: {"parsed_at": timestamp, "canonical_json": {...}}
_graph_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()

# Directory for saving parsed graphs
PARSED_GRAPHS_DIR = "parsed_graphs"
PARSER_MODE = "deterministic-v2"


def get_graph_hash(graph_xml: ET.Element) -> str:
    """Extract or compute hash for graph version tracking"""
    # Try to get hash from meta
    meta = graph_xml.find('.//meta/graph')
    if meta is not None:
        existing_hash = meta.get('hash')
        if existing_hash:
            return existing_hash
    
    # Compute hash from XML content
    xml_str = ET.tostring(graph_xml, encoding='unicode')
    return hashlib.md5(xml_str.encode()).hexdigest()


def get_graph_id_from_xml(graph_xml: ET.Element) -> Optional[str]:
    """Extract graph ID from XML"""
    meta = graph_xml.find('.//meta/graph')
    if meta is not None:
        return meta.get('id')
    return None


def get_cache_key(graph_id: str, graph_hash: str) -> str:
    """Generate cache key from graph ID and hash"""
    return f"{graph_id}_{graph_hash}"


def load_parsed_graph_from_file(graph_id: str, graph_hash: str) -> Optional[Dict[str, Any]]:
    """Load parsed graph from file if it exists"""
    try:
        filename = f"graph_{graph_id}_{graph_hash[:8]}.json"
        filepath = os.path.join(PARSED_GRAPHS_DIR, filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("parser_mode") != PARSER_MODE:
                    logging.info(f"Ignoring cached graph with parser_mode={data.get('parser_mode')} at {filepath}")
                    return None
                canonical_json = data.get("canonical_json", {})
                logging.info(f"Loaded parsed graph from file: {filepath}")
                return canonical_json
    except Exception as e:
        logging.error(f"Failed to load parsed graph from file: {e}")
    
    return None


def get_cached_graph(graph_id: str, graph_hash: str) -> Optional[Dict[str, Any]]:
    """Get parsed graph from cache (memory or file) if available"""
    cache_key = get_cache_key(graph_id, graph_hash)
    
    # Try memory cache first
    with _cache_lock:
        if cache_key in _graph_cache:
            logging.info(f"Memory cache hit for graph {graph_id}")
            return _graph_cache[cache_key]["canonical_json"]
    
    # Try loading from file
    cached_from_file = load_parsed_graph_from_file(graph_id, graph_hash)
    if cached_from_file:
        # Store in memory cache for faster access
        with _cache_lock:
            _graph_cache[cache_key] = {
                "parsed_at": datetime.now().isoformat(),
                "canonical_json": cached_from_file
            }
        logging.info(f"File cache hit for graph {graph_id}, loaded into memory")
        return cached_from_file
    
    return None


def cache_parsed_graph(graph_id: str, graph_hash: str, canonical_json: Dict[str, Any]):
    """Store parsed graph in cache and save to file"""
    cache_key = get_cache_key(graph_id, graph_hash)
    timestamp = datetime.now().isoformat()
    
    # Store in memory cache
    with _cache_lock:
        _graph_cache[cache_key] = {
            "parsed_at": timestamp,
            "canonical_json": canonical_json
        }
    logging.info(f"Cached parsed graph {graph_id}")
    
    # Save to file
    try:
        # Create directory if it doesn't exist
        os.makedirs(PARSED_GRAPHS_DIR, exist_ok=True)
        
        # Save to file with timestamp and hash in filename
        filename = f"graph_{graph_id}_{graph_hash[:8]}.json"
        filepath = os.path.join(PARSED_GRAPHS_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "parsed_at": timestamp,
                "graph_id": graph_id,
                "graph_hash": graph_hash,
                "parser_mode": PARSER_MODE,
                "canonical_json": canonical_json
            }, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Saved parsed graph to {filepath}")
    except Exception as e:
        logging.error(f"Failed to save parsed graph to file: {e}")


def _get_label_mapping(graph_xml: ET.Element) -> Dict[str, str]:
    label_map: Dict[str, str] = {}
    for mapping in graph_xml.findall('.//specification/resources/labelMappings/labelMapping'):
        event_id = mapping.get('eventId')
        label = mapping.get('labelId')
        if event_id:
            label_map[event_id] = (label or event_id).strip()
    return label_map


def _extract_event_data(event_elem: ET.Element) -> Dict[str, Any]:
    custom = event_elem.find('./custom')
    role = None
    data_type = None
    choice_values = None
    tags = []

    if custom is not None:
        role_elem = custom.find('./roles/role')
        if role_elem is not None and role_elem.text:
            role = role_elem.text.strip()

        data_type_elem = custom.find('./eventData/dataType')
        if data_type_elem is not None and data_type_elem.text:
            data_type = data_type_elem.text.strip()

        dictionary_items = custom.findall('./eventData/dictionary/item')
        if dictionary_items:
            choice_values = []
            for item in dictionary_items:
                label = item.get('label')
                value = item.get('value')
                choice_values.append((label or value or '').strip())

        # Support both explicit tags and DCR group markers (e.g., ShowInChatSOP).
        for tag_elem in custom.findall('./tags/tag'):
            if tag_elem.text:
                tags.append(tag_elem.text.strip())
        for group_elem in custom.findall('./groups/group'):
            if group_elem.text and group_elem.text.strip():
                tags.append(group_elem.text.strip())

    return {
        "data_type": data_type,
        "choice_values": choice_values,
        "role": role,
        "tags": sorted(set(tags))
    }


def _iter_events_recursive(events_root: ET.Element) -> Iterable[ET.Element]:
    """Yield all event nodes in declaration order, including nested child events."""
    stack = list(events_root.findall('./event'))
    while stack:
        current = stack.pop(0)
        yield current
        for child in current.findall('./event'):
            stack.append(child)


def _constraint_meaning(constraint_type: str, source: str, target: str) -> str:
    templates = {
        "condition": f"{source} must be executed before {target} can be executed.",
        "response": f"Executing {source} makes {target} required (pending).",
        "milestone": f"{target} is blocked while {source} is pending.",
        "include": f"Executing {source} includes {target} in the process.",
        "exclude": f"Executing {source} excludes {target} from the process."
    }
    return templates.get(constraint_type, f"{constraint_type} relation from {source} to {target}.")


def _parse_constraints(graph_xml: ET.Element) -> list:
    constraints = []
    constraints_root = graph_xml.find('.//specification/constraints')
    if constraints_root is None:
        return constraints

    section_to_type = {
        "conditions": "condition",
        "responses": "response",
        "milestones": "milestone",
        "includes": "include",
        "excludes": "exclude"
    }

    for section_name, ctype in section_to_type.items():
        section = constraints_root.find(section_name)
        if section is None:
            continue
        for item in list(section):
            source = item.get('sourceId')
            target = item.get('targetId')
            if not source or not target:
                continue
            constraints.append({
                "type": ctype,
                "source": source,
                "target": target,
                "meaning": _constraint_meaning(ctype, source, target)
            })

    # Updates are value assignments and should be explicit in canonical metadata.
    updates_section = constraints_root.find("updates")
    if updates_section is not None:
        for item in list(updates_section):
            source = item.get('sourceId')
            target = item.get('targetId')
            expression_id = item.get('valueExpressionId')
            if not source or not target:
                continue
            meaning = f"Executing {source} updates {target} value"
            if expression_id:
                meaning += f" using expression {expression_id}"
            meaning += "."
            constraints.append({
                "type": "update",
                "source": source,
                "target": target,
                "expression_id": expression_id,
                "meaning": meaning
            })
    return constraints


def _extract_dmn_description(expression_elem: ET.Element) -> str:
    # DMN definitions are nested with namespaces; use local-name wildcard.
    decision_table = expression_elem.find('.//{*}decisionTable')
    if decision_table is None:
        return "DMN decision logic."

    input_labels = []
    for input_elem in decision_table.findall('./{*}input'):
        label = input_elem.get('label')
        if label:
            input_labels.append(label.strip())
    output_elem = decision_table.find('./{*}output')
    output_label = output_elem.get('label').strip() if output_elem is not None and output_elem.get('label') else "output"
    rules_count = len(decision_table.findall('./{*}rule'))

    if input_labels:
        return f"DMN decision table maps {', '.join(input_labels)} to {output_label} ({rules_count} rules)."
    return f"DMN decision table with {rules_count} rules."


def _extract_expression_references(value: str, event_ids: set) -> list:
    if not value:
        return []
    candidates = set(re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', value))
    return sorted(candidates.intersection(event_ids))


def _parse_expressions(graph_xml: ET.Element, event_ids: set) -> list:
    expressions = []
    for expr in graph_xml.findall('.//specification/resources/expressions/expression'):
        expr_id = expr.get('id')
        if not expr_id:
            continue
        expr_type = (expr.get('type') or "formula").strip()
        expr_value = expr.get('value') or ""
        if expr_type.lower() == "dmn":
            description = _extract_dmn_description(expr)
        else:
            description = f"{expr_type} expression."
        references = _extract_expression_references(expr_value, event_ids)

        expressions.append({
            "id": expr_id,
            "type": expr_type,
            "value": expr_value,
            "description": description,
            "references": references
        })
    return expressions


def _parse_initial_state(graph_xml: ET.Element) -> Dict[str, Any]:
    included = []
    pending = []

    for event_elem in graph_xml.findall('.//runtime/marking/included/event'):
        event_id = event_elem.get('id')
        if event_id:
            included.append(event_id)

    for event_elem in graph_xml.findall('.//runtime/marking/pendingResponses/event'):
        event_id = event_elem.get('id')
        if event_id:
            pending.append(event_id)

    return {
        "pending": sorted(set(pending)),
        "included": sorted(set(included))
    }


def parse_graph_deterministic(graph_xml: ET.Element, graph_id: str, graph_hash: str) -> Dict[str, Any]:
    label_map = _get_label_mapping(graph_xml)
    events = []
    event_ids = set()

    events_root = graph_xml.find('.//specification/resources/events')
    if events_root is None:
        events_root = ET.Element("events")

    for event_elem in _iter_events_recursive(events_root):
        event_id = event_elem.get('id')
        if not event_id:
            continue
        event_ids.add(event_id)
        parsed_event = _extract_event_data(event_elem)
        events.append({
            "id": event_id,
            "label": label_map.get(event_id, event_id),
            "dataType": parsed_event["data_type"],
            "choiceValues": parsed_event["choice_values"],
            "tags": parsed_event["tags"],
            "computation": event_elem.get("computation"),
            "role": parsed_event["role"]
        })

    return {
        "graph_id": graph_id,
        "graph_hash": graph_hash,
        "title": graph_xml.get("title", ""),
        "events": events,
        "constraints": _parse_constraints(graph_xml),
        "expressions": _parse_expressions(graph_xml, event_ids),
        "initial_state": _parse_initial_state(graph_xml)
    }


def parse_graph_to_canonical(
    graph_xml: ET.Element, 
    state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Parse DCR graph XML to canonical JSON deterministically.
    
    Args:
        graph_xml: Parsed XML element of the DCR graph
        state: Session state with API credentials
    
    Returns:
        Canonical JSON representation of the graph
    """
    graph_id = get_graph_id_from_xml(graph_xml) or state.get("graph_id", "unknown")
    graph_hash = get_graph_hash(graph_xml)
    
    # Check cache first
    cached = get_cached_graph(str(graph_id), graph_hash)
    if cached:
        return cached

    try:
        canonical_json = parse_graph_deterministic(graph_xml, str(graph_id), graph_hash)

        # Only cache successful parses
        if not canonical_json.get("error"):
            cache_parsed_graph(str(graph_id), graph_hash, canonical_json)
        else:
            logging.warning("Skipping cache due to parse error")
        
        logging.info(f"Successfully parsed graph {graph_id}")
        return canonical_json
        
    except Exception as e:
        logging.error(f"Failed to parse graph: {e}")
        # Return minimal structure on failure
        return {
            "graph_id": graph_id,
            "graph_hash": graph_hash,
            "error": str(e),
            "events": [],
            "constraints": [],
            "expressions": []
        }


def parse_graph_async(
    graph_xml: ET.Element, 
    state: Dict[str, Any],
    callback: Optional[callable] = None
):
    """
    Parse graph asynchronously in background thread.
    
    Args:
        graph_xml: Parsed XML element of the DCR graph
        state: Session state with API credentials
        callback: Optional callback function to call with result
    """
    def _parse():
        try:
            result = parse_graph_to_canonical(graph_xml, state)
            if callback:
                callback(result)
        except Exception as e:
            logging.error(f"Async graph parsing failed: {e}")
            if callback:
                callback({"error": str(e)})
    
    thread = threading.Thread(target=_parse, daemon=True)
    thread.start()
    logging.info("Started async graph parsing")
    return thread


def get_cached_or_wait(graph_id: str, graph_hash: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
    """
    Get cached graph, waiting if parsing is in progress.
    
    Args:
        graph_id: Graph ID
        graph_hash: Graph hash
        timeout: Maximum seconds to wait
    
    Returns:
        Cached canonical JSON or None if timeout
    """
    import time
    start = time.time()
    
    while time.time() - start < timeout:
        cached = get_cached_graph(str(graph_id), graph_hash)
        if cached:
            return cached
        time.sleep(0.5)
    
    logging.warning(f"Timeout waiting for graph {graph_id} to be parsed")
    return None
