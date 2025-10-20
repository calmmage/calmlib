import asyncio
import pprint
from io import BytesIO
from typing import BinaryIO, TYPE_CHECKING

import loguru
import tqdm

if TYPE_CHECKING:
    from .whisper_utils import Audio
# region Whisper Bot

DEFAULT_PERIOD = 120 * 1000  # 2 minutes
DEFAULT_BUFFER = 5 * 1000  # 5 seconds


# todo: rework this function to split audio inplace to avoid huge memory usage
#  I did experiments somewhere.. /Users/petrlavrov/Downloads/macbook_migration/code-searcher/highlights/bot_lib_plugins/cut-audio-bot
def split_audio(
    audio: "Audio", period=DEFAULT_PERIOD, buffer=DEFAULT_BUFFER, logger=None
):
    from pydub import AudioSegment
    from .whisper_utils import WHISPER_RATE_LIMIT

    if isinstance(audio, (str, BytesIO, BinaryIO)):
        logger.debug(f"Loading audio from {audio}")
        audio = AudioSegment.from_file(audio)
    if logger is None:
        logger = loguru.logger
    chunks = []
    s = 0

    if len(audio) / period > WHISPER_RATE_LIMIT - 5:
        period = len(audio) // (WHISPER_RATE_LIMIT - 5)

    logger.debug("Splitting audio into chunks")
    while s + period < len(audio):
        chunks.append(audio[s : s + period])
        s += period - buffer
    chunks.append(audio[s:])
    logger.debug(f"Split into {len(chunks)} chunks")

    in_memory_audio_files = []

    logger.debug("Converting chunks to mp3")
    for i, chunk in enumerate(chunks):
        buffer = BytesIO()
        chunk.export(buffer, format="mp3")  # check which format it is and
        # use the same
        buffer.name = f"chunk_{i}.mp3"
        in_memory_audio_files.append(buffer)
    logger.debug("Converted chunks to mp3")

    return in_memory_audio_files


async def split_and_transcribe_audio(
    audio: "Audio",
    period: int = DEFAULT_PERIOD,
    buffer: int = DEFAULT_BUFFER,
    parallel: bool = None,
    logger=None,
):
    from pydub import AudioSegment
    from .whisper_utils import transcribe_audio, atranscribe_audio

    if logger is None:
        logger = loguru.logger

    if isinstance(audio, (str, BytesIO, BinaryIO)):
        logger.debug(f"Loading audio from {audio}")
        audio = AudioSegment.from_file(audio)

    audio_chunks = split_audio(audio, period=period, buffer=buffer, logger=logger)

    if parallel:
        logger.info("Processing chunks in parallel")
        tasks = map(atranscribe_audio, audio_chunks)
        text_chunks = await asyncio.gather(*tasks)
    else:
        logger.info("Processing chunks sequentially")
        text_chunks = []
        for chunk in tqdm.std.tqdm(audio_chunks):
            text_chunks.append(transcribe_audio(chunk))

    logger.debug("Parsed audio", data=pprint.pformat(text_chunks))
    return text_chunks


# endregion Whisper Bot

# region Cut Audio inplace
# todo: (failed?) /Users/petrlavrov/Downloads/macbook_migration/code-searcher/highlights/bot_lib_plugins/cut-audio-bot

# todo 2: /Users/petrlavrov/work/projects/examples/dev/unsorted/split_audio
# endregion Cut Audio inplace

# region Video to Audio
# todo:
# endregion Video to Audio
