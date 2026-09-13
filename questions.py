import logging
import re
from html.parser import HTMLParser
import utility as utility


class _InformationTextParser(HTMLParser):
    """Turn graph-authored HTML into safe, readable chat text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "div", "br"}:
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n- ")

    def handle_endtag(self, tag):
        if tag in {"p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)

    def get_text(self):
        text = "".join(self.parts).replace("\u00a0", " ")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def graph_html_to_text(html: str) -> str:
    """Return graph description HTML as safe plain text for the chat UI."""
    parser = _InformationTextParser()
    parser.feed(html or "")
    parser.close()
    return parser.get_text()


def is_information_event(event: dict) -> bool:
    """Whether a live DCR event should be displayed, not answered."""
    data_type = str(event.get("dataType") or "").lower()
    has_description = bool(str(event.get("description") or "").strip())
    return data_type == "label" or (not data_type and has_description)


def get_information_text(event: dict) -> str:
    """Get static text directly from the live DCR event payload."""
    for field in ("value", "displayValue", "description", "label"):
        value = event.get(field)
        if value not in (None, "") and str(value).strip().lower() != "undefined":
            return graph_html_to_text(str(value))
    return ""

def get_inferred_value(event, inferred_value) -> str:
    """
    Generate a question based on the event data type.

    Parameters:
        event (dict): The event data.

    Returns:
        str: The question string based on the event data type.
    """
    enum = event.get('choiceValues', '')
    data_type = event.get('dataType')
    qvalue = ""  # Initialize qvalue to an empty string
    if enum != "":
        try:
            qvalue = utility.get_label_from_enum(enum, inferred_value)
            # Optionally append the value:
            # qvalue = qvalue + " (" + str(inferred_value) + ")"
        except ValueError as e:
            logging.error(f"Invalid enum format: {qvalue}. Error: {str(e)}")
            raise ValueError(f"Problem while interpreting inferred replies.")
    elif data_type == 'date':
        try: 
            qvalue = utility.get_date_as_string(inferred_value)
        except ValueError as e:
            logging.error(f"Invalid date format: {qvalue}. Error: {str(e)}")
            raise ValueError(f"Problem while interpreting inferred replies.")
    else:
        qvalue = str(inferred_value)  # Fallback for other types

    return qvalue

def get_question(event: dict) -> str:
    """
    Generate a question based on the event data type.
 
    Parameters:
        event (dict): The event data.
 
    Returns:
        str: The question string based on the event data type.
    """
    question = event['label']
    # Remove all datatype instructions - just return the label from the graph
    logging.debug(f'Generated question: {question}')
   
    return question

def get_question_inferred(event, inferred_value):
    question = get_question(event)
    logging.debug(f'********this is the choice:{event.get("choiceValues", "")}, this is the date {event.get("dataType")}')
    qvalue = get_inferred_value(event, inferred_value)
    return question, qvalue


def get_conclusion(simulation_state: dict):
    # retrieve all events that are enabled and have datatype='label' and return that value
    result = ""
    for event in simulation_state['events']:
        tags = event.get('tags')
        if event.get('enabled') and (event.get('dataType') == 'label' or tags and 'ShowInChatSOP' in tags):
            if result != "":
                result += "<br>"
            if event.get('dataType') == 'label':
                desc = event.get('value')
                if desc == "":
                    desc = event.get('description')
                if desc == "":
                    desc = event.get('label')
            else: # tag
                desc = event.get('label') + ': ' + event.get('displayValue')

            result += desc

    logging.debug(f'Conclusion: {result}')
    return result
