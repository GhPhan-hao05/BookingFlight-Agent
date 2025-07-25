from voice import GeminiLiveAudio  # change this import
import asyncio

_audio_chat = None
_audio_chat_lock = asyncio.Lock()

async def get_audio_chat():
    global _audio_chat
    async with _audio_chat_lock:
        if _audio_chat is None:
            _audio_chat = GeminiLiveAudio()
        return _audio_chat