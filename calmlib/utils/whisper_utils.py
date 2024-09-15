from __future__ import annotations  # Allows forward references in type hints

from io import BytesIO
from typing import Union, BinaryIO

from loguru import logger

try:
    import openai
    import pydub
    from aiolimiter import AsyncLimiter

    modules_installed = True
except ImportError as e:
    modules_installed = False
    missing_module = e.name  # The name of the missing module
    logger.warning(f"{missing_module} is required to use whisper_utils")

if modules_installed:
    WHISPER_RATE_LIMIT = 50  # 50 requests per minute
    whisper_limiter = AsyncLimiter(WHISPER_RATE_LIMIT, 60)
else:
    whisper_limiter = None

Audio = Union["pydub.AudioSegment", BytesIO, BinaryIO, str]  # Use string annotations


def transcribe_audio(audio: Audio, model="whisper-1"):
    try:
        openai
    except:
        raise ImportError("openai is required to use this function")
    if isinstance(audio, str):
        audio = open(audio, "rb")
    return openai.Audio.transcribe(model, audio).text


async def atranscribe_audio(audio: Audio, model="whisper-1"):
    try:
        openai, AsyncLimiter
    except:
        raise ImportError("openai and aiolimiter are required to use this function")
    if isinstance(audio, str):
        audio = open(audio, "rb")
    async with whisper_limiter:
        result = await openai.Audio.atranscribe(model, audio)
    return result.text
