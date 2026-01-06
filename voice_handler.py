import os
import base64
import asyncio
from typing import Optional
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class VoiceHandler:
    def __init__(self):
        self.voice_provider = os.getenv("VOICE_PROVIDER", "webspeech")
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
        
        if self.voice_provider == "deepgram" and not self.deepgram_api_key:
            logger.warning("Deepgram API key not found, falling back to Web Speech API")
            self.voice_provider = "webspeech"
            
    async def transcribe_audio(self, audio_data: str) -> Optional[str]:
        """
        Transcribe audio to text.
        For Web Speech API, this is handled client-side.
        For Deepgram, we process server-side.
        """
        if self.voice_provider == "webspeech":
            # Web Speech API transcription happens client-side
            return None
            
        elif self.voice_provider == "deepgram":
            try:
                # Import only if using Deepgram
                from deepgram import Deepgram
                
                dg_client = Deepgram(self.deepgram_api_key)
                
                # Decode base64 audio
                audio_bytes = base64.b64decode(audio_data)
                
                # Transcribe
                response = await dg_client.transcription.prerecorded(
                    {'buffer': audio_bytes, 'mimetype': 'audio/webm'},
                    {'punctuate': True, 'language': 'en-US'}
                )
                
                transcript = response['results']['channels'][0]['alternatives'][0]['transcript']
                return transcript
                
            except Exception as e:
                logger.error(f"Deepgram transcription error: {e}")
                return None
                
    def get_tts_config(self) -> dict:
        """
        Get TTS configuration based on provider.
        For Web Speech API, we use browser's built-in TTS.
        """
        if self.voice_provider == "webspeech":
            return {
                "provider": "webspeech",
                "voice": "Google US English",
                "rate": 1.0,
                "pitch": 1.0
            }
        else:
            # Could add other TTS providers here
            return {
                "provider": "webspeech",
                "voice": "default",
                "rate": 1.0,
                "pitch": 1.0
            }
            
    def estimate_speech_duration(self, text: str) -> int:
        """
        Estimate speech duration in seconds.
        Assumes average speaking rate of 150 words per minute.
        """
        words = len(text.split())
        minutes = words / 150
        seconds = int(minutes * 60)
        return max(seconds, 1)  # At least 1 second