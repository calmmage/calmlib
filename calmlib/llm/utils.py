"""LLM utilities for enhanced AI interactions."""

import base64
import mimetypes
from pathlib import Path
from typing import Union, Optional

from pydantic import BaseModel
from .litellm_wrapper import query_llm_raw, query_llm_structured


class ValidationResponse(BaseModel):
    """Response from is_this_a_good_that validation."""
    is_good: bool
    reason: Optional[str] = None
    suggestion: Optional[str] = None


def query_llm_with_file(
    prompt: str,
    file_path: Union[str, Path, bytes],
    model: str = "claude-3.5-sonnet",
    system_message: Optional[str] = None,
    **kwargs
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
        {"type": "image_url", "image_url": f"data:{file_type};base64,{encoded_file}"}
    ]
    
    messages.append({"role": "user", "content": content})
    
    # Use the raw query function with prepared messages
    return query_llm_raw(
        messages=messages,
        model=model,
        **kwargs
    )


def is_this_a_good_that(
    input_str: str,
    desired_thing: str,
    criteria: Optional[str] = None,
    model: str = "claude-3.5-sonnet"
) -> ValidationResponse:
    """
    Validate if something meets criteria with structured feedback.
    
    Args:
        input_str: The thing to validate (e.g., "My Blog Post")
        desired_thing: What it should be (e.g., "title for a post")  
        criteria: Optional criteria/guidelines (e.g., "should be engaging and clear")
        model: Model to use for validation
        
    Returns:
        ValidationResponse with is_good flag, reason, and suggestion
        
    Example:
        result = is_this_a_good_that(
            "My Blog Post", 
            "title for a post",
            "should be engaging and clear"
        )
        print(f"Good: {result.is_good}, Reason: {result.reason}")
    """
    # Build the prompt
    prompt = f"Evaluate if '{input_str}' is a good {desired_thing}."
    
    if criteria:
        prompt += f" Criteria: {criteria}."
    
    prompt += """
    
Provide:
1. is_good: true/false
2. reason: brief explanation of your decision
3. suggestion: if not good, suggest a better alternative (optional)

Be concise and helpful."""
    
    return query_llm_structured(
        prompt=prompt,
        response_model=ValidationResponse,
        model=model
    )