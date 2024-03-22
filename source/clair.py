import requests
import json
import pandas as pd
import copy
import re

"""
Functions to interact with Clair API
"""

def activate_configuration(mode: str, language: str, keywords: list, host: str):
    # Define configuration
    agent_configuration = {
        "learning_space": "dev/clair-f2f",
        "is_active": True,
        "mode": mode,
        "language": language,
        "keywords": keywords
    }
    print(agent_configuration)
    # Activate agent under this configuration
    req = requests.post(f"{host}/configuration", 
                       data=json.dumps(agent_configuration), 
                       timeout=10)
    print(req, req.text, req.status_code, req.reason)
    return req

    
def parse_turn(transcription: str, dialogue: list, turn_threshold: int = 5):
    if len(dialogue) == 0:
        last_timestamp = pd.to_datetime("2000-01-01")
        last_user = ""
    else:
        last_timestamp = dialogue[-1]["timestamp"]
        last_user = dialogue[-1]["username"]
    # Check if transcription contains data
    if len(transcription)>0 and transcription!="Listening...":
        # Transcriptions can come in batches, so we need to split them
        transcripts = transcription.split("\n")
        # There could be a turn change within a batch, so lets monitor it
        is_new_turn = []
        # Let's go through the transcriptions of the batch
        for transcript in transcripts:
            # Initialize flag
            new_turn = True 
            # Take the current timestamp
            timestamp = pd.Timestamp.now()
            timedelta = (timestamp - last_timestamp).seconds
            # Each transcript has the following structure: "username: text" or "text" (which comes from same username as last_user)
            items = transcript.split(": ")
            # if there are two items ("username", "text") 
            if len(items) == 2:
                username = items[0]
                text = items[1]
                # if come within N seconds and is from the same username, it's not a new turn
                if last_user == username and 0 < timedelta < turn_threshold:
                    new_turn = False
            # if there is one part ("text") only, it's not a new turn
            elif len(items) == 1:
                username = last_user
                text = items[0]
                new_turn = False
            # Save new_turn information
            is_new_turn.append(new_turn)
            # if is a new turn, create a new one using the data
            if new_turn or len(dialogue)==0:
                turn = {
                    "username": username,
                    "text": text.strip(),
                    "timestamp": timestamp
                }
                dialogue.append(turn)
            else: # if its not, append it to the previous item stored in dialogue
                prev_msg = dialogue.pop()
                turn = {
                    "username": prev_msg["username"],
                    "text": prev_msg["text"] + " " + text.strip(),
                    "timestamp": prev_msg["timestamp"]
                }
                dialogue.append(turn)
            # Update last_timestamp and last_user
            last_timestamp = timestamp
            last_user = username
    # Else its an empty transcription
    else:
        turn = {}
        is_new_turn = {}
    return turn, dialogue, is_new_turn


def buffering_turn(transcription: str, dialogue: list, group: str, turn_threshold: int, verbose: bool = False):
    """
    Buffer the transcription and return the turn if there is a new one.

    Args:
    - transcription (str): The transcription to be buffered
    - dialogue (list): The dialogue to be updated
    - group (str): The group to which the dialogue belongs
    - turn_threshold (int): The time (seconds) threshold to consider a new turn
    - verbose (bool): Whether to print the transcription and the turn

    Returns:
    - turn (dict): The turn to be evaluated (keys: 'username', 'text', 'timestamp')
    """
    # In this function we delay the turn processing until we have a new turn
    # Pretty print the microphone input
    if verbose:
        print("\n\t🎙️ Microphone input received 🎙️ ")
        print('\n'.join([transcription[i:i+100] for i in range(0, len(transcription), 100)]))
    _, dialogue, is_new_turn = parse_turn(transcription, dialogue, turn_threshold)
    
    # If there is a new turn, return the previous turn (which now we know that has ended) to be evaluated
    if any(is_new_turn) and len(dialogue) > 1:
        # dialogue[-1] would be the new turn in progress, so dialogue[-2] is the turn before
        turn = dialogue[-2] 
    else: # If there is not a new turn, keep buffering
        turn = None # sentinel value

    # Pretty print turn
    if verbose and turn:
        turn['group'] = group
        print("\n\t💬 A turn was completed 💬")
        formatted_turn = copy.deepcopy(turn)
        # Check and modify the 'text' field of the copied dict only if it's too long
        if len(formatted_turn['text']) > 50:
            formatted_turn['text'] = [formatted_turn['text'][i:i+80] for i in range(0, len(formatted_turn['text']), 50)]
        # Get the JSON string
        json_str = json.dumps(formatted_turn, default=lambda obj: obj.strftime("%Y-%m-%d %H:%M:%S") if isinstance(obj, pd.Timestamp) else type(obj).__name__, indent=2)
        # Print the string
        print(json_str)
        print("\n\t🔄 Dialogue 🔄")
        print("\tNumber of turns:", len(dialogue))
        print("\tNumber of speakers:", len(set([item['username'] for item in dialogue])))
        print("\tTime duration:", dialogue[-1]['timestamp'] - dialogue[0]['timestamp']) 
        print("\t====================================\n")

    return turn 


def send_to_api_and_get_response(group: str, username: str, text: str, timestamp: int, host: str, verbose: bool = True):

    # Look for repeated sequences (BUG in Whisper)
    if re.search(r'(\b\w+(?:\s+\w+)*\.\s+)(\1{2,})', text):
        raise ValueError("ERROR: The transcription contained repetitive sentences. Please restart your audio source and try again.")
    message = {
        "learning_space": "dev/clair-f2f",
        "group": group,
        "username": username,
        "text": text,
        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S")
    }
    # Send the data to API with a POST request
    req = requests.post(f"{host}/message?retrieve_details=true&save=false",
                        data=json.dumps(message),
                        timeout=20)
    output = req.json()
    # Combine the original transcription with the API response
    combined_output = {
        "transcription": f"{username} ({str(timestamp)[:19]}): {text}",
        "response": output['agent_intervention'],
        'selected_move': output['selected_move']
    }

    # Play audio file with the response
    if verbose and output['agent_intervention']:
        print("\n\t⭐ Clair's response ⭐")
        print(json.dumps(combined_output, default=lambda obj: obj.strftime("%Y-%m-%d %H:%M:%S") if isinstance(obj, pd.Timestamp) else type(obj).__name__, indent=2))
        print("\t====================================\n")
    
    return json.dumps(combined_output, indent=2)

