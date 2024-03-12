import os
import json
import numpy as np
import rx.operators as ops
from websocket import WebSocket, create_connection
from diart.sources import MicrophoneAudioSource
from diart.utils import encode_audio
import dotenv
import threading 
import pyttsx3

# Load environment variables
dotenv.load_dotenv()
HOST = os.environ.get("HOST")
PORT = int(os.environ.get("PORT"))
PIPELINE_STEP = float(os.environ.get("PIPELINE_STEP"))
PIPELINE_SAMPLE_RATE = int(os.environ.get("PIPELINE_SAMPLE_RATE"))


# Initialize Text-to-Speech (tts) engine
TTS = pyttsx3.init()

# Set properties before adding anything to speak
TTS.setProperty('rate', 130)    # Speed percent (can go over 100)
TTS.setProperty('volume', 0.9)  # Volume 0-1
TTS.setProperty('voice', 'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_ZIRA_11.0')


def listen_server(ws):
    try:
        while True:
            output = ws.recv()
            # Transform output to dictionary
            output = json.loads(output)

            # # Parse the output for logging
            # text = output['transcription'].split(":")
            # username = text[0].split("(")[0].strip()
            # timestamp = text[0].split("(")[1][1:-1]
            # transcription = text[1]
            if output['response']:
                # Play the speech
                TTS.say(output['response'])
                TTS.runAndWait()          

    except Exception as e:
        print(f"Error while receiving message: {e}")

print("Connecting to server...")
# Run websocket client
ws = WebSocket()
ws.connect(f"ws://{HOST}:{PORT}")

# Start the listening thread
listener_thread = threading.Thread(target=listen_server, args=(ws,))
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


