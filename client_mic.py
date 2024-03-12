import os
import numpy as np
import rx.operators as ops
from websocket import WebSocket
from diart.sources import MicrophoneAudioSource
from diart.utils import encode_audio
import dotenv

# Load environment variables
dotenv.load_dotenv()
HOST = os.environ.get("HOST")
PORT = int(os.environ.get("PORT"))
PIPELINE_STEP = float(os.environ.get("PIPELINE_STEP"))
PIPELINE_SAMPLE_RATE = int(os.environ.get("PIPELINE_SAMPLE_RATE"))

# Run websocket client
ws = WebSocket()
ws.connect(f"ws://{HOST}:{PORT}")

# Create audio source
block_size = int(np.rint(PIPELINE_STEP * PIPELINE_SAMPLE_RATE))
audio_source = MicrophoneAudioSource(PIPELINE_SAMPLE_RATE, block_size)

# Encode audio, then send through websocket
audio_source.stream.pipe(
    ops.map(encode_audio)
).subscribe_(ws.send)
print("Connected to server")

# Start reading audio
print("Listening to local microphone...")
audio_source.read()