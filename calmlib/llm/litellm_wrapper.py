import json
import os
from collections import defaultdict
from dataclasses import dataclass

from functools import lru_cache
from typing import TYPE_CHECKING, Any, AsyncGenerator, Generator, Optional, Type
from loguru import logger
from pydantic import BaseModel
from pydantic_settings import BaseSettings

if TYPE_CHECKING:
    from litellm.types.utils import ModelResponse
    from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper


# ---------------------------------------------
# region Settings and Configuration
# ---------------------------------------------


class LLMProviderSettings(BaseSettings):
    """Settings for the LLM Provider component."""

    # enabled: bool = False
    default_model: str = "claude-4-sonnet"  # Default model to use
    default_temperature: float = 0.7
    default_max_tokens: int = 1000
    default_timeout: int = 30
    # If False, only friends and admins can use LLM features
    allow_everyone: bool = False

    skip_import_check: bool = False  # Skip import check for dependencies

    class Config:
        env_prefix = "CALMLIB_LLM_PROVIDER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Model name mapping for shortcuts
# This maps simple names to the provider-specific model names
MODEL_NAME_SHORTCUTS = {
    # Anthropic (Claude models)
    "claude-3.5": "anthropic/claude-3-5-sonnet-20241022",
    "claude-3.7-max": "anthropic/claude-3-7-sonnet-max",
    "claude-4-opus": "anthropic/claude-opus-4-20250514",
    "claude-4-sonnet": "anthropic/claude-sonnet-4-20250514",
    "claude-4.1-opus": "anthropic/claude-opus-4-1-20250805",
    # OpenAI models
    "gpt-4o": "openai/gpt-4o",
    "gpt-5": "openai/gpt-5",
    "gpt-5-mini": "openai/gpt-5-mini",
    "gpt-5-nano": "openai/gpt-5-nano",
    "gpt-5-chat": "openai/gpt-5-chat",
    "o1": "openai/o1",
    # Google models
    "gemini-2.5": "google/gemini-2.5-pro-max",
    "gemini-2.5-max": "google/gemini-2.5-pro-max",
    "gemini-2.0-pro": "google/gemini-2.0-pro-exp",
    "gemini-2.0": "google/gemini-2.0-pro-exp",
    # xAI models
    "grok-2": "xai/grok-2-1212",
    "grok-3": "xai/grok-3-beta",
    "grok-3-fast": "xai/grok-3-fast-beta",
    "grok-3-mini": "xai/grok-3-mini-beta",
    "grok-4": "xai/grok-4",
    "gpt-4.5": "openai/gpt-4.5-preview",
    # Remaining models
    # Claude models (continued)
    "claude-3-opus": "anthropic/claude-3-opus",
    "claude-3.5-haiku": "anthropic/claude-3-5-haiku",
    "claude-3.5-sonnet": "anthropic/claude-3-5-sonnet",
    "claude-3.7": "anthropic/claude-3-7-sonnet",
    # OpenAI models (continued)
    "gpt-3.5": "openai/gpt-3.5-turbo",
    "gpt-4": "openai/gpt-4",
    "gpt-4-turbo": "openai/gpt-4-turbo-2024-04-09",
    "gpt-4.5-preview": "openai/gpt-4.5-preview",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "o1-mini": "openai/o1-mini",
    "o1-preview": "openai/o1-preview",
    "o3-mini": "openai/o3-mini",
    # Google models (continued)
    "gemini-2.0-flash": "google/gemini-2.0-flash",
    "gemini-2.0-flash-exp": "google/gemini-2.0-flash-thinking-exp",
    "gemini-2.5-exp": "google/gemini-2.5-pro-exp-03-25",
    "gemini-exp-1206": "google/gemini-exp-1206",
    # Cursor models
    "cursor-fast": "cursor/cursor-fast",
    "cursor-small": "cursor/cursor-small",
    # Deepseek models
    "deepseek-r1": "deepseek/deepseek-r1",
    "deepseek-v3": "deepseek/deepseek-v3",
    # Meta models
    "llama": "meta/llama",
}


@dataclass
class LLMModelParams:
    """Parameters for configuring the LLM model"""

    model: str = "claude-4-sonnet"
    temperature: float = 0.7
    max_tokens: int = 1000
    timeout: Optional[float] = None
    max_retries: int = 2
    streaming: bool = False


@dataclass
class LLMQueryParams:
    """Parameters for the query itself"""

    system_message: Optional[str] = None
    use_structured_output: bool = False
    structured_output_schema: Optional[Any] = None


# ---------------------------------------------
# endregion Settings and Configuration
# ---------------------------------------------


# ---------------------------------------------
# region LLM Provider Implementation
# ---------------------------------------------


class LLMProvider:
    """Main LLM Provider class for Botspot"""

    def __init__(self, settings: LLMProviderSettings):
        """Initialize the LLM Provider with the given settings."""
        self.settings = settings
        # In-memory storage for usage stats if MongoDB is not available
        self.usage_stats = defaultdict(int)

    def _get_full_model_name(self, model: str) -> str:
        """Convert a model shortcut to its full name for litellm."""
        if "/" in model:  # Already a full name
            return model
        return MODEL_NAME_SHORTCUTS.get(model, model)

    def _prepare_messages(
        self, prompt: str, system_message: Optional[str] = None
    ) -> list:
        """Prepare messages for the LLM request."""
        messages = []

        # Add system message if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})

        # Add user prompt
        messages.append({"role": "user", "content": prompt})

        return messages

    # ---------------------------------------------
    # region Synchronous Query Methods
    # ---------------------------------------------

    def query_llm_raw(
        self,
        prompt: str,
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        structured_output_schema: Optional[Type[BaseModel]] = None,
        **extra_kwargs,
    ) -> "ModelResponse | CustomStreamWrapper":
        """
        Raw query to the LLM - returns the complete response object.

        Args:
            prompt: The text prompt to send to the model
            system_message: Optional system message for the model
            model: Model name to use (can be a shortcut)
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            timeout: Request timeout
            max_retries: Number of times to retry failed requests
            structured_output_schema: Optional Pydantic model for structured output
            **extra_kwargs: Additional arguments to pass to the LLM

        Returns:
            Raw response from the LLM
        """

        from litellm import completion

        # Get model parameters with defaults
        model = model or self.settings.default_model
        temperature = (
            temperature
            if temperature is not None
            else self.settings.default_temperature
        )
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages
        messages = self._prepare_messages(prompt, system_message)

        # Additional parameters
        params = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "request_timeout": timeout,
            "num_retries": max_retries,
            **extra_kwargs,
        }

        # Add structured output if needed
        if structured_output_schema:
            params["response_format"] = structured_output_schema

        logger.debug(f"Querying LLM with model {full_model_name}")

        # Make the actual API call
        response = completion(model=full_model_name, messages=messages, **params)

        return response

    def query_llm_text(
        self,
        prompt: str,
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        **extra_kwargs,
    ) -> str:
        """
        Query the LLM and return just the text response.

        Arguments are the same as query_llm_raw but returns a string.
        """
        from litellm.types.utils import (
            ModelResponse,
            StreamingChoices,
        )

        response = self.query_llm_raw(
            prompt=prompt,
            system_message=system_message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            **extra_kwargs,
        )
        assert isinstance(response, ModelResponse), "Expected ModelResponse"
        choice = response.choices[0]
        assert not isinstance(choice, StreamingChoices)
        message = choice.message
        # assert isinstance(message, LLMMessage), "Expected Message"
        content = message.content
        assert content is not None, "Expected non-None content from LLM response"
        return content

    def query_llm_stream(
        self,
        prompt: str,
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        **extra_kwargs,
    ) -> Generator[str, None, None]:
        """
        Stream text chunks from the LLM.

        Arguments are the same as query_llm_raw but returns a generator of text chunks.
        """

        from litellm import completion
        from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper

        # Get model parameters with defaults
        model = model or self.settings.default_model
        temperature = (
            temperature
            if temperature is not None
            else self.settings.default_temperature
        )
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages
        messages = self._prepare_messages(prompt, system_message)

        # Make the actual API call with streaming
        response = completion(
            model=full_model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout,
            num_retries=max_retries,
            stream=True,
            **extra_kwargs,
        )
        assert isinstance(response, CustomStreamWrapper), "Expected ModelResponseStream"

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def query_llm_structured[T: BaseModel](
        self,
        prompt: str,
        output_schema: Type[T],
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        **extra_kwargs,
    ) -> T:
        """
        Query LLM with structured output.

        Args:
            output_schema: A Pydantic model class defining the structure
            Other arguments same as query_llm_raw

        Returns:
            An instance of the provided Pydantic model
        """

        from litellm import completion
        from litellm.types.utils import ModelResponse, StreamingChoices

        # Get model parameters with defaults
        model = model or self.settings.default_model

        temperature = (
            temperature
            if temperature is not None
            else self.settings.default_temperature
        )
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages and add structured output instructions
        enhanced_system = system_message or ""
        enhanced_system += "\nYou MUST respond with a valid JSON object that conforms to the specified schema."

        messages = self._prepare_messages(prompt, enhanced_system)

        # Make the API call
        response = completion(
            model=full_model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout,
            num_retries=max_retries,
            response_format=output_schema,
            **extra_kwargs,
        )

        # Track usage (approximate tokens)
        assert isinstance(response, ModelResponse), "Expected ModelResponse"
        choice = response.choices[0]
        assert not isinstance(choice, StreamingChoices)
        content = choice.message.content
        assert content is not None, "Expected non-None content from LLM response"

        # Parse the response into the Pydantic model
        result_json = json.loads(content)
        return output_schema(**result_json)

    # ---------------------------------------------
    # endregion Synchronous Query Methods
    # ---------------------------------------------

    # ---------------------------------------------
    # region Asynchronous Query Methods
    # ---------------------------------------------

    async def aquery_llm_raw(
        self,
        prompt: str,
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        structured_output_schema: Optional[Type[BaseModel]] = None,
        **extra_kwargs,
    ) -> "ModelResponse":
        """
        Async raw query to the LLM - returns the complete response object.

        Args are the same as query_llm_raw but using async/await.
        """
        from litellm import acompletion
        from litellm.types.utils import ModelResponse

        # Get model parameters with defaults
        model = model or self.settings.default_model
        temperature = (
            temperature
            if temperature is not None
            else self.settings.default_temperature
        )
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages
        messages = self._prepare_messages(prompt, system_message)

        # Additional parameters
        params = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "request_timeout": timeout,
            "num_retries": max_retries,
            **extra_kwargs,
        }

        # Add structured output if needed
        if structured_output_schema:
            params["response_format"] = structured_output_schema

        logger.debug(f"Async querying LLM with model {full_model_name}")

        # Make the actual API call
        response = await acompletion(model=full_model_name, messages=messages, **params)

        assert isinstance(
            response, ModelResponse
        ), "Expected ModelResponse but got CustomStreamWrapper"
        return response

    async def aquery_llm_text(
        self,
        prompt: str,
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        **extra_kwargs,
    ) -> str:
        """
        Async query to the LLM returning just the text response.

        Arguments are the same as aquery_llm_raw but returns a string.
        """
        from litellm.types.utils import ModelResponse, StreamingChoices

        response = await self.aquery_llm_raw(
            prompt=prompt,
            system_message=system_message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            **extra_kwargs,
        )
        assert isinstance(response, ModelResponse), "Expected ModelResponse"
        choice = response.choices[0]
        assert choice is not None and not isinstance(
            choice, StreamingChoices
        ), "Expected ModelResponse but got CustomStreamWrapper"
        content = choice.message.content
        assert content is not None, "Expected non-None content from LLM response"
        return content

    async def aquery_llm_stream(
        self,
        prompt: str,
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        **extra_kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Async stream text chunks from the LLM.

        Arguments are the same as aquery_llm_raw but returns an async generator of text chunks.
        """
        from litellm import acompletion
        from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper

        # Get model parameters with defaults
        model = model or self.settings.default_model
        temperature = (
            temperature
            if temperature is not None
            else self.settings.default_temperature
        )
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages
        messages = self._prepare_messages(prompt, system_message)

        # Make the actual API call with streaming
        response = await acompletion(
            model=full_model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout,
            num_retries=max_retries,
            stream=True,
            **extra_kwargs,
        )
        assert isinstance(response, CustomStreamWrapper)
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def aquery_llm_structured[T: BaseModel](
        self,
        prompt: str,
        output_schema: Type[T],
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        **extra_kwargs,
    ) -> T:
        """
        Async query LLM with structured output.

        Args:
            output_schema: A Pydantic model class defining the structure
            Other arguments same as aquery_llm_raw

        Returns:
            An instance of the provided Pydantic model
        """
        from litellm import acompletion
        from litellm.types.utils import ModelResponse, StreamingChoices

        # Get model parameters with defaults
        model = model or self.settings.default_model
        temperature = (
            temperature
            if temperature is not None
            else self.settings.default_temperature
        )
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages and add structured output instructions
        enhanced_system = system_message or ""
        enhanced_system += "\nYou MUST respond with a valid JSON object that conforms to the specified schema."

        messages = self._prepare_messages(prompt, enhanced_system)

        # Make the API call
        response = await acompletion(
            model=full_model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout,
            num_retries=max_retries,
            response_format=output_schema,
            **extra_kwargs,
        )

        # Track usage (approximate tokens)
        assert isinstance(response, ModelResponse)
        choice = response.choices[0]
        assert not isinstance(choice, StreamingChoices)
        content = choice.message.content

        assert content is not None, "Expected non-None content from LLM response"

        # Parse the response into the Pydantic model
        result_text = content
        result_json = json.loads(result_text)
        return output_schema(**result_json)

    # ---------------------------------------------
    # endregion Asynchronous Query Methods
    # ---------------------------------------------


# ---------------------------------------------
# endregion LLM Provider Implementation
# ---------------------------------------------


# ---------------------------------------------
# region Initialization and Dispatcher Setup
# ---------------------------------------------


def initialize(settings: LLMProviderSettings) -> LLMProvider:
    """Initialize the LLM Provider component."""
    logger.info("Initializing LLM Provider component")
    
    # Check if litellm is installed
    try:
        import litellm
        logger.debug("litellm version: %s", litellm.api_version)
    except ImportError:
        logger.error(
            "litellm is not installed. Please install it to use the LLM Provider component."
        )
        raise ImportError(
            "litellm is not installed. Run 'poetry add litellm' or 'pip install litellm'"
        )
    
    # Check for API keys
    if not settings.skip_import_check:
        api_keys_env_names = {
            "OpenAI": "OPENAI_API_KEY",
            "Anthropic": "ANTHROPIC_API_KEY", 
            "Google/Gemini": "GEMINI_API_KEY",
            "xAI/Grok": "XAI_API_KEY",
            "Huggingface": "HUGGINGFACE_TOKEN",
            "Cohere": "COHERE_API_KEY",
            "Mistral": "MISTRAL_API_KEY",
            "Deepseek": "DEEPSEEK_API_KEY",
            "Fireworks": "FIREWORKS_API_KEY",
        }
        
        # Check which API keys are available
        available_keys = []
        for provider_name, env_key in api_keys_env_names.items():
            api_key = os.getenv(env_key)
            if api_key:
                logger.info(f"✅ {provider_name} API key found ({env_key})")
                available_keys.append(provider_name)
            else:
                logger.debug(f"⚠️ {provider_name} API key not found ({env_key})")
        
        if not available_keys:
            logger.warning(
                "No API keys found. You'll need to set at least one API key to use LLM features.\n"
                "Common keys: OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY"
            )

    provider = LLMProvider(settings)

    return provider


# ---------------------------------------------
# endregion Initialization and Dispatcher Setup
# ---------------------------------------------


# ---------------------------------------------
# region Utils
# ---------------------------------------------


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Get the LLM Provider from dependency manager."""
    litellm_provider = initialize(LLMProviderSettings())
    return litellm_provider


# Convenience functions for direct use
def query_llm_text(
    prompt: str,
    *,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Query the LLM and return the text response.

    This is a convenience function that uses the global LLM provider.
    """
    provider = get_llm_provider()
    return provider.query_llm_text(
        prompt=prompt, system_message=system_message, model=model, **kwargs
    )


def query_llm_raw(
    prompt: str,
    *,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> "ModelResponse | CustomStreamWrapper":
    """
    Raw query to the LLM - returns the complete response object.

    This is a convenience function that uses the global LLM provider.

    Args:
        prompt: The text prompt to send to the LLM
        system_message: Optional system message to prepend
        model: Optional model to use (defaults to provider default)
        **kwargs: Additional arguments to pass to the LLM provider

    Returns:
        Raw response from the LLM with full metadata and usage stats
    """
    provider = get_llm_provider()
    return provider.query_llm_raw(
        prompt=prompt, system_message=system_message, model=model, **kwargs
    )


def query_llm_structured(
    prompt: str,
    output_schema: Type[BaseModel],
    *,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> BaseModel:
    """
    Query LLM with structured output.

    This is a convenience function that uses the global LLM provider.

    Args:
        prompt: The text prompt to send to the LLM
        output_schema: A Pydantic model class defining the structure
        system_message: Optional system message to prepend
        model: Optional model to use (defaults to provider default)
        **kwargs: Additional arguments to pass to the LLM provider

    Returns:
        An instance of the provided Pydantic model
    """
    provider = get_llm_provider()
    return provider.query_llm_structured(
        prompt=prompt,
        output_schema=output_schema,
        system_message=system_message,
        model=model,
        **kwargs,
    )


async def aquery_llm_text(
    prompt: str,
    *,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Async query the LLM and return the text response.

    This is a convenience function that uses the global LLM provider.
    """
    provider = get_llm_provider()
    return await provider.aquery_llm_text(
        prompt=prompt, system_message=system_message, model=model, **kwargs
    )


async def astream_llm(
    prompt: str,
    *,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> AsyncGenerator[str, None]:
    """
    Async stream text chunks from the LLM.

    This is a convenience function that uses the global LLM provider.

    Args:
        prompt: The text prompt to send to the LLM
        system_message: Optional system message to prepend
        model: Optional model to use (defaults to provider default)
        **kwargs: Additional arguments to pass to the LLM provider

    Returns:
        An async generator that yields text chunks as they become available
    """
    provider = get_llm_provider()
    async for chunk in provider.aquery_llm_stream(
        prompt=prompt, system_message=system_message, model=model, **kwargs
    ):
        yield chunk


async def aquery_llm_structured[T: BaseModel](
    prompt: str,
    output_schema: Type[T],
    *,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> T:
    """
    Async query LLM with structured output.

    This is a convenience function that uses the global LLM provider.

    Args:
        prompt: The text prompt to send to the LLM
        output_schema: A Pydantic model class defining the structure
        system_message: Optional system message to prepend
        model: Optional model to use (defaults to provider default)
        **kwargs: Additional arguments to pass to the LLM provider

    Returns:
        An instance of the provided Pydantic model
    """
    provider = get_llm_provider()
    return await provider.aquery_llm_structured(
        prompt=prompt,
        output_schema=output_schema,
        system_message=system_message,
        model=model,
        **kwargs,
    )


async def aquery_llm_raw(
    prompt: str,
    *,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> "ModelResponse":
    """
    Async raw query to the LLM - returns the complete response object.

    This is a convenience function that uses the global LLM provider.

    Args:
        prompt: The text prompt to send to the LLM
        system_message: Optional system message to prepend
        model: Optional model to use (defaults to provider default)
        **kwargs: Additional arguments to pass to the LLM provider

    Returns:
        Raw response from the LLM with full metadata and usage stats
    """
    provider = get_llm_provider()
    return await provider.aquery_llm_raw(
        prompt=prompt, system_message=system_message, model=model, **kwargs
    )


# ---------------------------------------------
# endregion Utils
# ---------------------------------------------


if __name__ == "__main__":
    print("Hello, world!")
