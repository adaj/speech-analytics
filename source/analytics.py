import json
import copy
import pandas as pd
import re
from termcolor import colored


def parse_turn(transcription: str, turns_list: list):
    if len(turns_list) == 0:
        last_timestamp = pd.to_datetime("2000-01-01")
        last_user = ""
    else:
        last_timestamp = turns_list[-1]["timestamp"]
        last_user = turns_list[-1]["username"]
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
                # if come within 10 seconds and is from the same username, it's not a new turn
                if last_user == username and 0 < timedelta < 10:
                    new_turn = False
            # if there is one part ("text") only, it's not a new turn
            elif len(items) == 1:
                username = last_user
                text = items[0]
                new_turn = False
            # Save new_turn information
            is_new_turn.append(new_turn)
            # if is a new turn, create a new one using the data
            if new_turn or len(turns_list)==0:
                turn = {
                    "username": username,
                    "text": text.strip(),
                    "timestamp": timestamp
                }
                turns_list.append(turn)
            else: # if its not, append it to the previous item stored in turns_list
                prev_msg = turns_list.pop()
                turn = {
                    "username": prev_msg["username"],
                    "text": prev_msg["text"] + " " + text.strip(),
                    "timestamp": prev_msg["timestamp"]
                }
                turns_list.append(turn)
            # Update last_timestamp and last_user
            last_timestamp = timestamp
            last_user = username
    # Else its an empty transcription
    else:
        turn = {}
        is_new_turn = {}
    return turn, turns_list, is_new_turn


def color_speaker(json_str):
    color_mapping = {
        '0': 'magenta',
        '1': 'blue',
        '2': 'green',
        '3': 'yellow',
        '4': 'red',
    }
    def replace_func(match):
        speaker_num = match.group(1)
        color = color_mapping.get(speaker_num, 'white')  # Default to 'white' if speaker number is out of range
        return colored(f'Speaker{speaker_num}', color)
    return re.sub(r'Speaker(\d)', replace_func, json_str)


def buffering_turn(transcription: str, turns_list: list, verbose: bool = False):
    """
    Buffer the transcription and return the turn if there is a new one.

    Args:
    - transcription (str): The transcription to be buffered
    - turns_list (list): The turns_list to be updated
    - verbose (bool): Whether to print the transcription and the turn

    Returns:
    - turn (dict): The turn to be evaluated (keys: 'username', 'text', 'timestamp')
    """
    # In this function we delay the turn processing until we have a new turn
    # Pretty print the microphone input
    if verbose:
        print(colored("\n🎙️ Microphone input received 🎙️ ", 'white', 'on_green'))
        print(color_speaker('\n'.join([transcription[i:i+100] for i in range(0, len(transcription), 100)])))
    _, turns_list, is_new_turn = parse_turn(transcription, turns_list)
    # If there is a new turn, return the previous turn (which now we know that has ended) to be evaluated
    if any(is_new_turn) and len(turns_list) > 1:
        # turns_list[-1] would be the new turn in progress, so turns_list[-2] is the turn before
        turn = turns_list[-2] 
    else: # If there is not a new turn, keep buffering
        turn = None # sentinel value
    # Pretty print turn
    if verbose and turn:
        # def print_str_in_chunks(s: str, n: int):
        #     for i in range(0, len(s), n):
        #         print(s[i:i+n])
        print(colored("\n💬 A turn was completed 💬", 'black', 'on_light_red'))
        formatted_turn = copy.deepcopy(turn)
        # Check and modify the 'text' field of the copied dict only if it's too long
        if len(formatted_turn['text']) > 50:
            formatted_turn['text'] = [formatted_turn['text'][i:i+50] for i in range(0, len(formatted_turn['text']), 50)]
        # Get the JSON string
        json_str = json.dumps(formatted_turn, default=lambda obj: obj.strftime("%Y-%m-%d %H:%M:%S") if isinstance(obj, pd.Timestamp) else type(obj).__name__, indent=2)
        # Print the string
        print(color_speaker(json_str))
        print(colored("\n🔄 Dialogue 🔄", 'black', 'on_light_yellow'))
        print("Number of turns:", len(turns_list))
        print("Number of speakers:", len(set([item['username'] for item in turns_list])))
        print("Time duration:", turns_list[-1]['timestamp'] - turns_list[0]['timestamp']) 
        print("====================================\n")
    return turn 


class DialogueState:

    def __init__(self):
        # One turn element is a dict{'username': str, 'text': str, 'timestamp': pd.Timestamp}
        self.turns_list = [] 
        # More attributes you want to compute...
        self.speakers = []
        self.number_of_speakers = 0
        self.starting_time = None
        self.time_duration = None
        self.number_of_turns = 0

    def update(self, turn):
        # Update turns
        self.turns_list.append(turn)
        self.number_of_turns = len(self.turns_list)
        # Compute more attributes...
        # a - number of speakers
        if turn['username'] not in self.speakers:
            self.speakers.append(turn['username'])
            self.number_of_speakers += 1
        # b - time duration
        if self.starting_time is None:
            self.starting_time = turn['timestamp']
        self.time_duration = turn['timestamp'] - self.starting_time
        # c - ...

    def to_log_file(self, file_path):
        # Save the dialogue state to a log file
        with open(file_path, 'w') as file:
            file.write(json.dumps(self.__dict__, default=lambda obj: obj.strftime("%Y-%m-%d %H:%M:%S") if isinstance(obj, pd.Timestamp) else type(obj).__name__, indent=2))
        return None

    def to_dashboard(self):
        # ...
        return None


def compute_turn(username, text, timestamp, dialogue_state, verbose=False):
    # Preprocess the inputs
    if re.search(r'(\b\w+(?:\s+\w+)*\.\s+)(\1{2,})', text):
        raise ValueError("ERROR: The transcription contained repetitive sentences. Please restart your audio source and try again.")
    # Compute your analytics
    dialogue_state.update({'username': username, 'text': text, 'timestamp': timestamp})
    # Send dialogue_state to the dashboard
    dialogue_state.to_dashboard()
    # Log the data into a file
    dialogue_state.to_log_file('dialogue_state.json')
    # The output of this function is only printed, so we don't need to return anything
    if verbose:
        print("Computing turn executed.")
    return None
