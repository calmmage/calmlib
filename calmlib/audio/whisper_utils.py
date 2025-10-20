from __future__ import annotations  # Allows forward references in type hints

from io import BytesIO
from typing import TYPE_CHECKING, BinaryIO, Union

if TYPE_CHECKING:
    import pydub

    assert pydub

    Audio = Union[
        "pydub.AudioSegment", BytesIO, BinaryIO, str
    ]  # Use string annotations


WHISPER_RATE_LIMIT = 50  # 50 requests per minute


def transcribe_audio(audio: Audio, model="whisper-1"):
    import openai

    if isinstance(audio, str):
        audio = open(audio, "rb")
    return openai.Audio.transcribe(model, audio).text


async def atranscribe_audio(audio: Audio, model="whisper-1"):
    import openai

    global whisper_limiter
    from aiolimiter import AsyncLimiter

    whisper_limiter = AsyncLimiter(WHISPER_RATE_LIMIT, 60)

    if isinstance(audio, str):
        audio = open(audio, "rb")
    async with whisper_limiter:
        result = await openai.Audio.atranscribe(model, audio)
    return result.text
