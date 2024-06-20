import os
import json
import random
import numpy as np
import rx.operators as ops
from websocket import WebSocket, create_connection
from diart.sources import MicrophoneAudioSource
from diart.utils import encode_audio
import dotenv
import threading 
import pyttsx3
from pydub import AudioSegment
from pydub.playback import play


# Load environment variables
dotenv.load_dotenv()
HOST = os.environ.get("HOST")
PORT = int(os.environ.get("PORT"))
PIPELINE_STEP = float(os.environ.get("PIPELINE_STEP"))
PIPELINE_SAMPLE_RATE = int(os.environ.get("PIPELINE_SAMPLE_RATE"))

# Load audio folder path
AUDIO_FOLDER_PATH = os.environ.get("AUDIO_FOLDER_PATH")
AUDIO_FOLDER_PATH = AUDIO_FOLDER_PATH.replace("\\", "/")
if AUDIO_FOLDER_PATH[-1] == "/":
    AUDIO_FOLDER_PATH = AUDIO_FOLDER_PATH[:-1]


class ClairManager:

    def __init__(self):

        # Define talk_moves available
        self.talk_moves = {
            'negative_valence_monitoring_cognition': [
                "feel_stuck", "better_understanding", "reflecting", "current_approach"
            ],
            'issue_conceptual_understanding': [
                "confusion", "key_concepts", "tools"
            ],
            'lack_shared_perspective': [
                "progress_group", "joint_plan", "accomplish_group"
            ],
        }

        # Organize paths of audio files
        self.audio_files = {}
        for talk_move in self.talk_moves:
            self.audio_files[talk_move] = {}
            for variation in self.talk_moves[talk_move]:
                self.audio_files[talk_move][variation] = f"{AUDIO_FOLDER_PATH}/{variation}.mp3"
        
        # Initialize Text-to-Speech (tts) engine
        self.tts = pyttsx3.init()

        # Set properties before adding anything to speak
        self.tts.setProperty('rate', 130)    # Speed percent (can go over 100)
        self.tts.setProperty('volume', 0.9)  # Volume 0-1
        self.tts.setProperty('voice', 'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_ZIRA_11.0')

    def play_audio(self, talk_move):
        try:
            variation = random.choice(self.talk_moves[talk_move])
            file_path = self.audio_files[talk_move][variation]
            play(AudioSegment.from_mp3(file_path))
        except:
            print(f"ERROR: Audio file not found for the talk_move {talk_move}")
            pass

    def say(self, text):
        self.tts.say(text)

    def runAndWait(self):
        self.tts.runAndWait()


def listen_server(ws, manager, should_continue):
    try:
        while should_continue.is_set():
            # Receive message from websocket server
            output = ws.recv()
            # Transform output to dictionary
            output = json.loads(output)
            print(output)

            # Check if there is a response
            if output['response']:
                # Play the output response as audio
                try:
                    # Play the audio file
                    manager.play_audio(output['selected_move'])  
                except:
                    print(f"WARNING: Audio file not found: {output['response']}")
                    # If the audio file is not found, use TTS
                    # manager.say(output['response'])
                    # manager.runAndWait()
                    pass # Dont play any audio for now
            elif 'test test' in output['transcription'].lower().replace(",", ""):
                manager.play_audio('issue_conceptual_understanding')  

    except Exception as e:
        print(f"Error while receiving message: {e}")


if __name__ == "__main__":
    try:
        # Initialize ClairManager
        manager = ClairManager()

        # Run websocket client
        print("Connecting to server...")
        ws = WebSocket()
        ws.connect(f"ws://{HOST}:{PORT}")

        # Start the listening thread
        should_continue = threading.Event()
        should_continue.set()
        listener_thread = threading.Thread(target=listen_server, args=(ws,manager,should_continue,))
        listener_thread.start()

        # Create audio source
        block_size = int(np.rint(PIPELINE_STEP * PIPELINE_SAMPLE_RATE))
        audio_source = MicrophoneAudioSource(PIPELINE_SAMPLE_RATE, block_size)

        # Encode audio, then send through websocket
        audio_source.stream.pipe(
            ops.map(encode_audio)
        ).subscribe_(ws.send)
        print("Microphone audio source is now streaming")

        # Start reading audio
        print("Listening to local microphone...")
        audio_source.read()
    
    except KeyboardInterrupt:
        print("Exiting...")
        should_continue.clear()
        ws.close()
        listener_thread.join()
        audio_source.close()
        exit(0)

