"""LLM utilities for enhanced AI interactions."""

import base64
import mimetypes
import random
from pathlib import Path
from textwrap import dedent
from typing import Any, Optional

from pydantic import BaseModel

# from src.utils import get_resources_dir

# todo: create (find and use?) more sophisticated default model picker
# check which models are available for each provider, pick the latest one
# do a cheap / middle / expensive options
DEFAULT_MODEL = "claude-4.5-sonnet"


def query_llm_with_file(
    prompt: str,
    file_path: str | Path | bytes,
    *,
    model: str = DEFAULT_MODEL,
    system_message: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Query LLM with attached file (image/PDF).

    Args:
        prompt: Text prompt to send with the file
        file_path: Path to file, or raw bytes
        model: Model to use for the query
        system_message: Optional system message
        **kwargs: Additional arguments passed to query_llm_raw

    Returns:
        LLM response as string

    Example:
        response = query_llm_with_file(
            "What's in this image?",
            "screenshot.png",
            model="claude-3.5-sonnet"
        )
    """
    from calmlib.llm import query_llm_text
    
    # Handle file input
    if isinstance(file_path, bytes):
        file_bytes = file_path
        file_type = "image/jpeg"  # Default assumption for bytes
    else:
        file_path = Path(file_path)
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        # Detect MIME type from file extension
        mime_type, _ = mimetypes.guess_type(str(file_path))
        file_type = mime_type or "image/jpeg"

    # Base64 encode the file
    encoded_file = base64.b64encode(file_bytes).decode("utf-8")

    # Prepare messages with file attachment
    messages = []

    if system_message:
        messages.append({"role": "system", "content": system_message})

    # Add user message with file
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": f"data:{file_type};base64,{encoded_file}"},
    ]

    messages.append({"role": "user", "content": content})

    # Use the raw query function with prepared messages
    return query_llm_text(messages=messages, model=model, **kwargs)


class ValidationResponse(BaseModel):
    """Response from is_this_a_good_that validation."""

    reason: str | None = None
    is_good: bool
    suggestion: str | None = None



def is_this_a_good_that(
    source: str,
    target: str = "title",
    candidate: str | None = None,
    # todo: idea of a criteria
    # criteria: Optional[str] = None,
    model: str = DEFAULT_MODEL,
) -> ValidationResponse:
    """
    Evaluate if a candidate is a good target for a source.
    Propose a better alternative if not good.
    """

    from calmlib.llm import (
        query_llm_structured,
    )
    prompt = f'I need a good {target} for the following text:\n"""\n{source}\n""".\n\n'
    if candidate:
        prompt += f"Candidate: {candidate}."

    system_message = dedent("""
        Tell if "this" is a good "that". Or propose a better alternative if not good.

        Provide:
        1. reason: brief explanation of your decision
        2. is_good: true/false
        3. suggestion: if not good, suggest a better alternative (optional)
        
        Be concise and helpful.""")

    return query_llm_structured(
        prompt=prompt,
        output_schema=ValidationResponse,
        model=model,
        system_message=system_message,
    )


# todo: generate a title for (something)
class TitleResponse(BaseModel):
    title: str


title_system_message = """
Generate a short and descriptive title for the provided content.
Maximum {n} words, no punctuation.
Capitalize only first letter of recognized names or acronyms.
{extra}
"""


def generate_title(
    prompt: str,
    model: str = DEFAULT_MODEL,
    max_length=None,
    extra_instructions: str | None = None,
):
    from calmlib.llm import (
        query_llm_structured,
    )
    if max_length is None:
        max_length = random.randint(2, 6)
    extra = extra_instructions if extra_instructions else ""
    return query_llm_structured(
        prompt=prompt,
        output_schema=TitleResponse,
        model=model,
        system_message=title_system_message.format(n=max_length, extra=extra),
    )


async def agenerate_title(
    prompt: str,
    model: str = DEFAULT_MODEL,
    max_length=3,
    extra_instructions: Optional[str] = None,
):

    from calmlib.llm import (
        aquery_llm_structured,
    )
    extra = extra_instructions if extra_instructions else ""
    return await aquery_llm_structured(
        prompt=prompt,
        output_schema=TitleResponse,
        model=model,
        system_message=title_system_message.format(n=max_length, extra=extra),
    )


# secretary_prompt_path = (
#     get_resources_dir() / "ai_character_launcher/characters/Secretary.md"
# )
# secretary_prompt = secretary_prompt_path.read_text()
#
#
# def format_text(text: str, model: str = DEFAULT_MODEL) -> str:
#     from calmlib.llm import (
#         query_llm_text,
#     )
#     return query_llm_text(text, system_message=secretary_prompt, model=model)
#
#
# async def aformat_text(text: str, model: str = DEFAULT_MODEL) -> str:
#     from calmlib.llm import (
#         aquery_llm_text,
#     )
#     return await aquery_llm_text(text, system_message=secretary_prompt, model=model)
