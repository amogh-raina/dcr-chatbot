# utility.py
"""
Utility functions for date manipulation, validation, and more.
"""
from datetime import date
from typing import Union
import re
import xml.etree.ElementTree as ET
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.DEBUG)

def _get_day_with_suffix(day: int) -> str:
    """
    Get the ordinal suffix for a given day.
    
    Parameters:
        day (int): The day of the month.
    
    Returns:
        str: The day with its ordinal suffix.
    """
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]
    return f"{day}{suffix}"

def parse_date(date_str):
    formats = ["%Y-%m-%d", "%d-%m-%Y"]
    for date_format in formats:
        try:
            # Try to parse with each format
            return datetime.strptime(date_str, date_format)
        except ValueError:
            # If parsing fails, continue to try the next format
            continue
    # If neither format matches, return None or raise an error
    raise ValueError(f"Invalid date format: {date_str}. Expected 'YYYY-MM-DD' or 'DD-MM-YYYY'.")

def get_date_as_string(date_input: Union[str, date]) -> str:
    date_obj = None
    if isinstance(date_input, date):
        date_obj = date_input
    else:
        date_obj = parse_date(date_input)

    day_of_week = date_obj.strftime("%A")
    month = date_obj.strftime("%B")
    day_with_suffix = _get_day_with_suffix(date_obj.day)
    year = date_obj.year
    iso_format = date_obj.strftime("%d-%m-%Y")
    return f"{day_of_week} {month} {day_with_suffix}, {year}, or {iso_format}"

    
def get_today() -> str:
    """
    Get today's date formatted as a string.
    
    Returns:
        str: Today's date in the format "Today is {day_of_week} {month} {day_with_suffix}, {year}, or {iso_format}".
    """
    today = datetime.today()
    return 'Today is ' + get_date_as_string(today)
    

def _validate_date(date_str: str) -> bool:
    """
    Validate if a string is in the format DD-MM-YYYY.
    
    Parameters:
        date_str (str): The date string to validate.
    
    Returns:
        bool: True if the string is a valid date, False otherwise.
    """
    try:
        date_obj = datetime.strptime(date_str, "%d-%m-%Y")
        logging.debug(f'validate_date({date_str}) = {date_obj}')
        return True
    except ValueError:
        return False

def _extract_values(s: str) -> list:
    """
    Extract values enclosed in parentheses from a string.
    
    Parameters:
        s (str): The string containing values in parentheses.
    
    Returns:
        list: A list of values extracted from the string.
    """
    pattern = r'\((.*?)\)'
    return re.findall(pattern, s)


def validate_datatype(event: dict, reply: str) -> str:
    """
    Validate a reply against the expected data type specified in the event.
    
    Parameters:
        event (dict): The event containing the data type and other relevant information.
        reply (str): The reply to validate.
    
    Returns:
        str: The original reply if valid, 'GNYF' if datatype is invalid.
    """
    data_type = event['dataType']
    valid = False

    if data_type == 'date':
        valid = _validate_date(reply)

    elif data_type == 'int':
        valid = reply.isdigit()
    elif data_type == 'choice':
        choice_values = event['choiceValues']
        values = _extract_values(choice_values)
        valid = reply in values
    
    logging.debug(f"validate_datatype({event['id']}, {reply}) = {valid}")
    
    return reply if valid else 'GNYF'


def get_all_events(found_event: dict, simulation_state: dict) -> str:
    """
    Get a string of all enabled events except the found event.

    Parameters:
        found_event (dict): The found event to exclude.
        simulation_state (dict): The JSON data of events.

    Returns:
        str: A string of all enabled events except the found event.
    """
    all_events = ''
    for event in simulation_state['events']:
        if event.get('enabled') and event['id'] != found_event['id']:
            all_events += f"{event['id']}:{event['label']}\n"
    return all_events.strip()


def get_all_events_not_executed(found_event: dict, simulation_state: dict) -> str:
    """
    Get a string of all enabled events except the found event.

    Parameters:
        found_event (dict): The found event to exclude.
        simulation_state (dict): The JSON data of events.

    Returns:
        str: A string of all enabled and not executed events except the found event.
    """
    all_events = ''
    for event in simulation_state['events']:
        if event.get('enabled') and event['id'] != found_event['id'] and event.get('executed') == None:
            all_events += f"{event['id']}:{event['label']}\n"
    return all_events.strip()

def get_event(eventid: str, simulation_state: dict) -> dict:
    """
    Get a specific event by ID from the JSON data.

    Parameters:
        eventid (str): The ID of the event to retrieve.
        simulation_state (dict): The JSON data of events.

    Returns:
        dict: The event if found, None otherwise.
    """
    for event in simulation_state['events']:
        if event.get('id') == eventid:
            return event
    return None

def is_pending_event(event: dict) -> bool:
    """Return whether an event is currently actionable in the DCR simulation."""
    return bool(
        event and (
            (event.get('enabled') and event.get('pending')) or
            (event.get('enabled') and event.get('IsProductive') and not event.get('executed'))
        )
    )

def is_container_event(event: dict) -> bool:
    """Return whether an API event represents structure rather than a chat turn."""
    event_type = str((event or {}).get('type') or '').strip().lower()
    return event_type in {'subprocess', 'nesting', 'form'}

def get_pending_event(simulation_state: dict) -> dict:
    """
    Get the first pending event from the JSON data.

    Parameters:
        simulation_state (dict): The JSON data of events.

    Returns:
        dict: The first pending event if found, None otherwise.
    """
    for event in simulation_state['events']:
        if not is_container_event(event) and is_pending_event(event):
            return event
    return None

def get_next_pending_event(simulation_state: dict, event_id:str) -> dict:
    """
    Get another pending event from the JSON data.

    Parameters:
        simulation_state (dict): The JSON data of events.

    Returns:
        dict: The first pending event if found, None otherwise.
    """
    for event in simulation_state['events']:
        if(event.get('id') == event_id):
            continue
        if not is_container_event(event) and is_pending_event(event):
            return event
    return None

def get_events_enabled_not_executed(simulation_state: dict) -> dict:
    """
    Get all enabled but not executed events from the JSON data that have a datatype and is not label.

    Parameters:
        simulation_state (dict): The JSON data of events.

    Returns:
        dict: All the enabled and not executed events that have a datatype excluding labels, or None
    """
    result = None
    for event in simulation_state['events']:
        if event.get('enabled') and not event.get('executed'):
            if event.get('dataType') != "" and event.get('dataType') != "label":
                if result == None:
                    result = []
                result.append(event);
    return result

def get_enabled_interpretable_events(simulation_state: dict) -> list:
    """Return reusable input events exposed by the current DCR API state.

    Execution history is deliberately ignored here. An enabled choice can be
    used again by an FAQ conversation even when the repository reports that
    it was executed earlier in the same simulation.
    """
    return [
        event
        for event in simulation_state.get('events', [])
        if event.get('enabled')
        and not is_container_event(event)
        and event.get('dataType') not in (None, '', 'label')
    ]

def get_label_from_enum(enum: str, reply: int) -> str:
    logging.info(f'### get_label_from_enum({enum}, {reply}), typeof(reply)={type(reply)}')
    # Split the enum string into individual label-value pairs
    pairs = enum.split(')')
    for pair in pairs:
        pair = pair.strip()  # Remove any leading/trailing whitespace
        if pair == "":
            continue  # Skip empty items
        # Split the item by "(" to get the label and value
        parts = pair.split("(")
        # Extract and clean the label
        label = parts[0].strip()
        if label.startswith(", "):
            label = label[2:].strip()

        # Extract the value if it exists, otherwise return None
        if len(parts) > 1:
            value = parts[1].strip()
            # Compare as int only if both are digits, else as string
            if value.isdigit() and str(reply).isdigit():
                if int(value) == int(reply):
                    return label
            if value == str(reply):
                return label
        else:
            return None
    # Return None if no match is found
    return None
