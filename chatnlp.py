# chatnlp.py
"""
Module for accessing DCR Active Repository's chat functions.
"""

import requests
import json
import logging
from typing import Optional
import utility as utility
#from flask import state


logging.basicConfig(level=logging.DEBUG)

def create_chat(chat_type: int, user_input: str, user_input2: str, user_input3: str, graph_id: int, root_url: str, api_key: str, token: str) -> dict:
    """
    Create a chat in the DCR Active Repository.

    Parameters:
        chat_type (int): The type of chat.
        user_input (str): The first user input.
        user_input2 (str): The second user input.
        user_input3 (str): The third user input.
        graph_id (int): The ID of the graph.
        root_url (str): The root URL of the DCR repository.
        api_key (str): The API key for authentication.
        token (str): The authentication token.

    Returns:
        dict: A dictionary containing the chat ID and the result if successful, None otherwise.
    """
    headers = {
        'X-DCR-AuthToken': api_key,
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept-Language': 'en-US'
    }

    body = {
        'DCRGraphId': graph_id,
        'type': chat_type,
        'text': user_input,
        'text2': user_input2,
        'text3': user_input3,
        'objecttype': 'chat'
    }
    
    response = requests.post(f"{root_url}api/chat", headers=headers, json=body)
    
    if response.status_code == 201:
        #json_data = response.json()
        chat_id_str = response.headers.get('X-DCR-Chat-ID')
        chat_id = int(chat_id_str)
        #if chat_id_str else None
        #result = {'ChatID': chat_id}#, 'result': json_data['output']}
        return chat_id #result
    else:
        logging.error(f"Failed to create chat: {response.status_code}")
        return None

# not used
def validate_reply_to_question(event: dict, reply: str, question: str, root_url: str, api_key: str, token: str) -> Optional[str]:
    """
    Validate the user's reply to a question based on the event data type.

    Parameters:
        event (dict): The event data.
        reply (str): The user's reply.
        question (str): The question asked.
        root_url (str): The root URL of the DCR repository.
        api_key (str): The API key for authentication.
        token (str): The authentication token.

    Returns:
        Optional[str]: Validated reply if successful with the correct data value matching the event, 'GNYF' if question matches but no data can be found, or None otherwise.
    """
    data_type = event['dataType']
    extra_info = {
        'choice': '. Please enter one of these values: ' + event['choiceValues'],
        'date': f'Assume {utility.get_today()} to find a valid date given the users reply.',
        'int': ' Please return the response as an integer.'
    }.get(data_type, '')
    
    try:
        chat_result = create_chat(100, question, reply, extra_info, 1826984, root_url, api_key, token)
        if not chat_result:
            logging.error('Chat result is None')
            return None

        # Only try to convert to int if result is a digit
        result_str = str(chat_result['result']).replace(" ", "")
        if result_str.isdigit():
            rating = int(result_str)
        else:
            logging.error(f"Result is not an integer: {chat_result['result']}")
            return None

        if rating >= 5:
            if data_type == 'date':
                extra_info += 'Please return the response as a date in the format yyyy-mm-dd, where yyyy is the year, mm is the month, and dd is the day of the month.'
            chat_result = create_chat(37, question, reply, extra_info, 1826984, root_url, api_key, token)
            if not chat_result:
                return 'GNYF'
            else:
                result = chat_result["result"]
                logging.debug(f'Validation result: {result}')
                return utility.validate_datatype(event, result)
        else:
            logging.debug(f'Rating too low: {rating}')
            return None
    except Exception as e:
        logging.error(f'Failed to validate reply: {e}')
        return None

# not used
def any_matching_event(event: dict, query: str, simulation_state: dict, root_url: str, api_key: str, token: str) -> Optional[dict]:
    """
    Check if there is any matching event based on the user's query.

    Parameters:
        event (dict): The current event data.
        query (str): The user's query.
        simulation_state (dict): The JSON result containing events.
        root_url (str): The root URL of the DCR repository.
        api_key (str): The API key for authentication.
        token (str): The authentication token.

    Returns:
        Optional[dict]: The matching event if found, None otherwise.
    """
    all_events = utility.get_all_events(event, simulation_state)
    try:
        chat_result = create_chat(38, query, all_events, "", root_url, api_key, token)
        if not chat_result:
            logging.error('Chat result is None')
            return None
        
        event_id = chat_result['result']
        if event_id and event_id != 'Empty':
            return utility.get_event(event_id, simulation_state)
    except Exception as e:
        logging.error(f'Failed to find matching event: {e}')
    
    return None

def reply_to_chat(questionId: str, reply: str, graph_json: str, state: dict) -> dict:
    """
    Reply to an existing chat in the DCR Active Repository.

    Parameters:
        DCRGraphId (int): The ID of the DCR graph.
        chat_id (int): The Chat ID from the create_chat call.
        questionId (str): The ID of the question.
        reply (str): The reply from the user.
        graph_json (str): The graph as a JSON string with the enabled events.

    Returns:
        dict: The response JSON containing the question, reply, value, explanation, and inferred replies.
    """
    graph_json = graph_json.replace("\"id\"", "\"questionid\"")
    headers = {
        'X-DCR-AuthToken': state['api_key'],
        'Authorization': f'Bearer {state["token"]}',
        'Content-Type': 'application/json',
        'Accept-Language': 'en-US'
    }

    body = {
        'DCRGraphId': state["graph_id"],
        'type': 100,
        'text': questionId,
        'text2': reply,
        'text3': graph_json
    }
    #logging.debug(f"chat - json={body}")
    response = requests.post(f"{state['root_url']}api/chat/{state['chat_id']}", headers=headers, json=body)
    
    if response.status_code == 200:
        json_data = response.json()
        logging.debug(f"Reply to chat successful: {json_data}")
        return json_data
    else:
        logging.error(f"Failed to reply to chat: {response.status_code}")
        return None

def convert_msg_to_value(event_id: int, simulation_state: dict, message: str, state: dict) -> str:
    value = None
    retry = False
    comment = ""

    # Get language from state, default to Danish
    lang = state.get("graph_language") or "da"

    # Send every input event currently enabled by the DCR API to the
    # interpretation service. FAQ selectors are reusable, so their execution
    # history must not remove them from later free-text matching.
    candidates = utility.get_enabled_interpretable_events(simulation_state)
    current_event = utility.get_event(event_id, simulation_state)
    if (
        current_event
        and current_event.get("enabled")
        and current_event.get("dataType") not in (None, "", "label")
        and all(event.get("id") != current_event.get("id") for event in candidates)
    ):
        candidates.insert(0, current_event)
    graph_json = json.dumps(candidates)
    # So I send the list of all the possible events and the message to the chatnlp to find the best match
    chat_result = reply_to_chat(event_id, message, graph_json, state)

    # If the chat_result is None, it means that the AI could not find a match for the user's reply
    if chat_result != None:  # otherwise the AI found a match, and we have to check if the provided reply replied to the question or not
        logging.info(f"*** reply_to_chat({event_id}, {message}) = {chat_result}")
        if chat_result == 'GNYF':  # date format not valid
            retry = True
        if chat_result.get("reply") == True:  # the user replied to the question
            # if the user is vague, it's still considered as a valid reply, but we ask the user to retry
            if chat_result.get("value") == "" or chat_result.get("value") is None:
                if lang.lower().startswith("es"):
                    comment = "Lo siento, necesito una respuesta más específica. Por favor, inténtalo de nuevo."
                elif lang.lower().startswith("en"):
                    comment = "Sorry, I need a more specific answer. Please try again."
                else:
                    comment = "Beklager, jeg har brug for et mere specifikt svar. Prøv venligst igen."
                retry = True
            else:
                value = chat_result["value"]
            logging.info(f"### reply_to_chat = {value},  ({event_id}, {message})")
        else:  # the user did NOT reply to the question, but value could be used to infer another event
            logging.info(f"### reply_to_chat({event_id}, {message}) = {chat_result}")

            inferred_event_id = chat_result.get("questionid")
            inferred_value = chat_result.get("value")
            inferred_replies = state.get("inferred_replies", [])

            # Store any inferred replies from chat_result["inferred_replies"]
            for inferred in chat_result.get("inferred_replies", []):
                qid = inferred.get("questionid")
                val = inferred.get("value")
                if qid and val not in (None, ""):
                    inferred_replies.append({
                        "questionid": qid,
                        "value": val
                    })
                    logging.info(f"*** inferred reply added from inferred_replies: {qid}={val}")

            state["inferred_replies"] = inferred_replies

            # but we still need to ask the user to reply to the question
            if lang.lower().startswith("es"):
                comment = "Lo siento, no pude entender tu respuesta. Por favor, inténtalo de nuevo."
            elif lang.lower().startswith("en"):
                comment = "Sorry, I could not understand your answer. Please try again."
            else:
                comment = "Beklager, jeg kunne ikke forstå dit svar. Prøv venligst igen."
            retry = True
    else:
        retry = True
        if lang.lower().startswith("es"):
            comment = "Lo siento, no pude entender tu respuesta. Por favor, inténtalo de nuevo."
        elif lang.lower().startswith("en"):
            comment = "Sorry, I could not understand your answer. Please try again."
        else:
            comment = "Beklager, jeg kunne ikke forstå dit svar. Prøv venligst igen."
    return value, chat_result, retry, comment
