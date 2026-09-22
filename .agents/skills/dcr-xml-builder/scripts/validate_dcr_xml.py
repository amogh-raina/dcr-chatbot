#!/usr/bin/env python3
"""Validate structural invariants in a full-format DCR XML graph."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


REQUIRED_RESOURCE_COLLECTIONS = (
    "events",
    "labels",
    "labelMappings",
    "expressions",
    "variables",
    "variableAccesses",
    "custom",
)
REQUIRED_CONSTRAINT_COLLECTIONS = (
    "conditions",
    "responses",
    "coresponses",
    "includes",
    "excludes",
    "milestones",
    "updates",
    "spawns",
    "templateSpawns",
)
RELATION_TAGS = {
    "condition",
    "response",
    "coresponse",
    "include",
    "exclude",
    "milestone",
    "update",
    "spawn",
    "templateSpawn",
}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def values_with_duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def validate(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as exc:
        return [f"Cannot parse XML: {exc}"], warnings

    root = tree.getroot()
    if local_name(root.tag) != "dcrgraph":
        return [
            f"Expected full-format <dcrgraph> root, found <{local_name(root.tag)}>"
        ], warnings

    specification = root.find("specification")
    resources = specification.find("resources") if specification is not None else None
    constraints = specification.find("constraints") if specification is not None else None
    if specification is None:
        errors.append("Missing /dcrgraph/specification")
    if resources is None:
        errors.append("Missing /dcrgraph/specification/resources")
    if constraints is None:
        errors.append("Missing /dcrgraph/specification/constraints")
    if resources is None or constraints is None:
        return errors, warnings

    for name in REQUIRED_RESOURCE_COLLECTIONS:
        if resources.find(name) is None:
            warnings.append(f"Missing resource collection <{name}>")
    for name in REQUIRED_CONSTRAINT_COLLECTIONS:
        if constraints.find(name) is None:
            warnings.append(f"Missing constraint collection <{name}>")

    events_node = resources.find("events")
    resource_events = list(events_node.iter("event")) if events_node is not None else []
    event_ids = [event.get("id", "") for event in resource_events]
    for index, event_id in enumerate(event_ids, start=1):
        if not event_id:
            errors.append(f"Resource event #{index} has no id")
    duplicates = values_with_duplicates([event_id for event_id in event_ids if event_id])
    if duplicates:
        errors.append(f"Duplicate resource event IDs: {', '.join(duplicates)}")
    event_id_set = set(event_ids) - {""}

    expression_nodes = list(resources.findall("./expressions/expression"))
    expression_ids = [node.get("id", "") for node in expression_nodes]
    missing_expression_ids = sum(not value for value in expression_ids)
    if missing_expression_ids:
        errors.append(f"{missing_expression_ids} expression(s) have no id")
    expression_duplicates = values_with_duplicates(
        [value for value in expression_ids if value]
    )
    if expression_duplicates:
        errors.append(f"Duplicate expression IDs: {', '.join(expression_duplicates)}")
    expression_id_set = set(expression_ids) - {""}

    label_nodes = list(resources.findall("./labels/label"))
    label_ids = [node.get("id", "") for node in label_nodes]
    label_id_set = set(label_ids) - {""}
    label_duplicates = values_with_duplicates([value for value in label_ids if value])
    if label_duplicates:
        warnings.append(f"Duplicate label IDs: {', '.join(label_duplicates)}")

    for mapping in resources.findall("./labelMappings/labelMapping"):
        event_id = mapping.get("eventId", "")
        label_id = mapping.get("labelId", "")
        if event_id not in event_id_set:
            errors.append(f"Label mapping references missing event: {event_id or '<empty>'}")
        if label_id not in label_id_set:
            errors.append(f"Label mapping references missing label: {label_id or '<empty>'}")

    for event in resource_events:
        event_id = event.get("id", "<unknown>")
        computation = event.get("computation")
        if computation and computation not in expression_id_set:
            errors.append(f"Event {event_id} references missing computation: {computation}")
        for data_type in event.findall("./custom/eventData/dataType"):
            dataset = data_type.get("dataSetActivity")
            if dataset and dataset not in event_id_set:
                errors.append(f"Event {event_id} references missing dataset event: {dataset}")
        if computation:
            roles = {
                (role.text or "").strip()
                for role in event.findall("./custom/roles/role")
            }
            if not (roles & {"Robot", "LocalRobot"}) and event.get("type") != "subprocess":
                warnings.append(
                    f"Computed event {event_id} is not a Robot/LocalRobot or computed subprocess"
                )

    for collection in list(constraints):
        for relation in list(collection):
            tag = local_name(relation.tag)
            if tag not in RELATION_TAGS:
                warnings.append(f"Unknown relation element <{tag}>")
            source_id = relation.get("sourceId", "")
            target_id = relation.get("targetId", "")
            if source_id not in event_id_set:
                errors.append(f"{tag} references missing source event: {source_id or '<empty>'}")
            if target_id not in event_id_set:
                errors.append(f"{tag} references missing target event: {target_id or '<empty>'}")
            guard_id = relation.get("expressionId")
            if guard_id and guard_id not in expression_id_set:
                errors.append(f"{tag} references missing guard expression: {guard_id}")
            value_id = relation.get("valueExpressionId")
            if value_id and value_id not in expression_id_set:
                errors.append(f"{tag} references missing value expression: {value_id}")

    runtime = root.find("runtime")
    marking = runtime.find("marking") if runtime is not None else None
    if runtime is None:
        warnings.append("Missing /dcrgraph/runtime")
    elif marking is None:
        warnings.append("Missing /dcrgraph/runtime/marking")
    else:
        for state_name in ("executed", "included", "pendingResponses"):
            state = marking.find(state_name)
            if state is None:
                warnings.append(f"Missing marking collection <{state_name}>")
                continue
            seen: list[str] = []
            for event in state.findall("event"):
                event_id = event.get("id", "")
                seen.append(event_id)
                if event_id not in event_id_set:
                    errors.append(
                        f"Initial {state_name} references missing event: {event_id or '<empty>'}"
                    )
            state_duplicates = values_with_duplicates([value for value in seen if value])
            if state_duplicates:
                errors.append(
                    f"Duplicate IDs in initial {state_name}: {', '.join(state_duplicates)}"
                )

    if root.find("meta") is not None:
        warnings.append(
            "Graph contains <meta>; ensure repository IDs, GUID, hash, owner, and revision are intentional"
        )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate references and structural invariants in full-format DCR XML."
    )
    parser.add_argument("xml_file", type=Path)
    args = parser.parse_args()

    errors, warnings = validate(args.xml_file)
    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARNING: {message}")
    if errors:
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"OK: 0 errors, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
