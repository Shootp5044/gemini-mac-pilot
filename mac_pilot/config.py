"""Configuration — API clients, model names, and audio constants.

All tuneable knobs live here so nothing is scattered across modules.
"""

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

if "GCP_PROJECT" not in os.environ:
    raise EnvironmentError(
        "GCP_PROJECT environment variable is required. Set it in your .env file."
    )
GCP_PROJECT = os.environ["GCP_PROJECT"]

# ── Model names (single source of truth) ─────────────────────────
BRAIN_MODEL = "gemini-3-flash-preview"
VOICE_MODEL = "gemini-live-2.5-flash-native-audio"

# ── API clients ───────────────────────────────────────────────────
client = genai.Client(
    vertexai=True,
    project=GCP_PROJECT,
    location="global",
)

voice_client = genai.Client(
    vertexai=True,
    project=GCP_PROJECT,
    location="us-central1",
)

# ── Audio constants ───────────────────────────────────────────────
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024
