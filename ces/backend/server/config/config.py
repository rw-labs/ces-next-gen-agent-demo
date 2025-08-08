"""
Configuration for Vertex AI Gemini Multimodal Live Proxy Server
"""

import os
import warnings
from typing import Optional

from dotenv import load_dotenv
from google.adk.agents import RunConfig
from google.api_core.client_options import ClientOptions
from google.cloud import secretmanager
from google.cloud import texttospeech_v1beta1 as tts
from google.genai import types

warnings.filterwarnings("ignore", category=UserWarning)

from core.logger import logger

# Load environment variables
load_dotenv()

PROJECT_ID = os.environ.get("PROJECT_ID", "cx-demo-312101")
LOCATION = os.environ.get("VERTEX_LOCATION", "us-central1")
DEMO_TYPE = os.environ.get("DEMO_TYPE", "optus_modem_setup")
FIRST_NAME = os.environ.get("FIRST_NAME", "Rod")
LAST_NAME = os.environ.get("LAST_NAME", "Williams")
MODEL_NAME = os.environ.get("MODEL", "gemini-live-2.5-flash-preview-native-audio")

logger.info(f"FIRST_NAME: {FIRST_NAME}")
logger.info(f"LAST_NAME: {LAST_NAME}")
logger.info(f"DEMO_TYPE: {DEMO_TYPE}")
logger.info(f"PROJECT_ID: {PROJECT_ID}")
logger.info(f"LOCATION: {LOCATION}")
logger.info(f"MODEL_NAME: {MODEL_NAME}")

# Model and Voice Globals
MODEL = os.getenv("MODEL", "gemini-live-2.5-flash-preview-native-audio")
VOICE = os.getenv("VOICE", "Aoede")
MODEL_LANGUAGE = os.getenv("MODEL_LANGUAGE", "en-AU")
PROMPT_LANGUAGE = os.getenv("PROMPT_LANGUAGE", None)
ACCENT_LANGUAGE = os.getenv("ACCENT_LANGUAGE", None)

USE_TTS = True if os.environ.get("USE_TTS", False) == "true" else False
TTS_LOCATION = os.environ.get("TTS_LOCATION", "global")
TTS_ENDPOINT = (
    f"{TTS_LOCATION}-texttospeech.googleapis.com"
    if TTS_LOCATION != "global"
    else "texttospeech.googleapis.com"
)
logger.info(f"USE_TTS: {USE_TTS}")


class ConfigurationError(Exception):
    """Custom exception for configuration errors."""

    pass


def get_secret(secret_id: str) -> str:
    """Get secret from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    project_id = PROJECT_ID

    if not project_id:
        raise ConfigurationError("PROJECT_ID environment variable is not set")

    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"

    try:
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception:
        raise


class ApiConfig:
    """API configuration handler."""

    def __init__(self):
        use_vertex_env = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "1")
        if use_vertex_env.lower() == "true":
            self.use_vertex = 1
        elif use_vertex_env.lower() == "false":
            self.use_vertex = 0
        else:
            self.use_vertex = int(use_vertex_env)

        self.api_key: Optional[str] = None
        self.tts_client: tts.TextToSpeechClient = self.init_tts_client()

        logger.info(f"Initialized API configuration with Vertex AI: {self.use_vertex}")

    async def initialize(self):
        """Initialize API credentials."""
        if not self.use_vertex:
            try:
                self.api_key = get_secret("GOOGLE_API_KEY")
            except Exception as e:
                logger.warning(f"Failed to get API key from Secret Manager: {e}")
                self.api_key = os.getenv("GOOGLE_API_KEY")
                if not self.api_key:
                    raise ConfigurationError(
                        "No API key available from Secret Manager or environment"
                    )

    def init_tts_client(self):
        """Initialize TTS client."""
        try:
            tts_client = tts.TextToSpeechClient(
                client_options=ClientOptions(api_endpoint=TTS_ENDPOINT)
            )
            logger.info(f"TTS Client initialized for endpoint: {TTS_ENDPOINT}")
        except Exception as e:
            logger.exception(f"Failed to initialize TTS client: {e}")
            tts_client = None  # Handle cases where TTS might not be available

        return tts_client

    def get_tts_streaming_config(self):
        """Return the TTS streaming config."""
        if not self.tts_client:
            logger.warning("TTS client not available, cannot get streaming config.")
            return None

        TTS_VOICE = f"{MODEL_LANGUAGE}-Chirp3-HD-{VOICE}"

        try:
            streaming_config = tts.StreamingSynthesizeConfig(
                voice=tts.VoiceSelectionParams(
                    name=TTS_VOICE, language_code=MODEL_LANGUAGE
                )
            )
        except Exception as e:
            logger.exception(f"Failed to initialize TTS Config: {e}")

        return streaming_config


# Initialize API configuration
api_config = ApiConfig()

if USE_TTS:
    # Temp: 2 newest voices are not supported across all langauges yet
    # As of 4/23/25 the 2 newest voices are only supported in en-US
    if VOICE in ["Achernar", "Sulafat"] and MODEL_LANGUAGE != "en-US":
        raise ConfigurationError(
            f"Voice `{VOICE}` only supported in `en-US` for TTS at this time."
        )

    # RUN_CONFIG = RunConfig(
    #     response_modalities=["TEXT"],
    #     realtime_input_config=types.RealtimeInputConfig(
    #         automatic_activity_detection=types.AutomaticActivityDetection(
    #             disabled=False,  # default
    #             start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
    #             end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
    #             prefix_padding_ms=500, # The required duration of detected speech before start-of-speech is committed. The lower this value the more sensitive the start-of-speech detection is and the shorter speech can be recognized. However, this also increases the probability of false positives.
    #             silence_duration_ms=100,
    #         )
    #     ),
    # )

    logger.info(f"TTS VERSION: {tts.__version__}")
    logger.info(
        f"Using Cloud TTS for Audio Out and voice `{VOICE}`. language_code=`{MODEL_LANGUAGE}`"
    )

else:
    # Temp: Raise if voice selection is in non-supported Live API Audio Out
    # As of 4/23/25 there are still 2 voices that are not supported
    if VOICE in ["Achernar", "Sulafat"]:
        raise ConfigurationError(
            f"Voice `{VOICE}` is currently not supported in Live API. Set USE_TTS=true if you want to use this voice."
        )

    RUN_CONFIG = RunConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfigDict(
                {"prebuilt_voice_config": {"voice_name": VOICE}}
            ),
            language_code=MODEL_LANGUAGE,
        ),
        enable_affective_dialog=True, # understands tone of voice
        proactivity=types.ProactivityConfig(proactive_audio=True), # ignores non-relevant conversations
        #input_audio_transcription={},
        output_audio_transcription={},
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=False,  # default
                start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                prefix_padding_ms=1000,
                silence_duration_ms=100,
            )
        ),
    )

    logger.info(
        f"Using Live API for Audio Out and voice `{VOICE}`. language_code=`{MODEL_LANGUAGE}`"
    )

TTS_CLIENT = api_config.tts_client
TTS_CONFIG = api_config.get_tts_streaming_config()
