from io import BytesIO
from typing import Union, BinaryIO

import openai
import pydub
from aiolimiter import AsyncLimiter

WHISPER_RATE_LIMIT = 50  # 50 requests per minute
whisper_limiter = AsyncLimiter(WHISPER_RATE_LIMIT, 60)  # 50 requests per minute
Audio = Union[pydub.AudioSegment, BytesIO, BinaryIO, str]


def transcribe_audio(audio: Audio, model="whisper-1"):
    if isinstance(audio, str):
        audio = open(audio)
    return openai.Audio.transcribe(model, audio).text


async def atranscribe_audio(audio: Audio, model="whisper-1"):
    if isinstance(audio, str):
        audio = open(audio)
    async with whisper_limiter:
        result = await openai.Audio.atranscribe(model, audio)
    return result.text
