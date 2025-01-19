import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional
from typing import Type, AsyncGenerator
from typing import Union, Generator, TYPE_CHECKING, Any

from deprecated import deprecated
from pydantic import BaseModel

if TYPE_CHECKING:
    from langchain.prompts import ChatPromptTemplate

    from langchain.prompts import ChatPromptTemplate

models_per_engine = {
    "openai": ["gpt-4o", "gpt-4", "gpt-3.5-turbo"],
    "azure": ["us4o", "blankgpt4_32k"],
    "local": ["llama3"],
    "anthropic": ["claude-3-5-sonnet-20240620", "claude-3-sonnet-20240229"],
}
DEFAULT_ENGINE = "anthropic"
DEFAULT_MODEL = models_per_engine[DEFAULT_ENGINE][0]


def _assume_alternating_messages(warmup_messages):
    for i, msg in enumerate(warmup_messages):
        if i % 2 == 0:
            # yield HumanMessage(content=msg)
            yield ("human", msg)
        else:
            # yield AIMessage(content=msg)
            yield ("ai", msg)


role_map = {
    "system": "system",
    "user": "human",
    "assistant": "ai",
    "human": "human",
    "ai": "ai",
}

def build_langchain_prompt(system: str, warmup_messages=None, prompt_template="{prompt}") -> "ChatPromptTemplate":
    from langchain.prompts import ChatPromptTemplate

    # messages = [SystemMessage(content=system)]
    messages = [("system", system)]
    if warmup_messages:
        # option 1: list of strings -> assume alternating messages
        # option 2: list of dicts (role, content) -> convert to messages
        # option 3: list of Message objects -> use as is
        if isinstance(warmup_messages[0], str):
            warmup_messages = _assume_alternating_messages(warmup_messages)
        elif isinstance(warmup_messages[0], dict):
            for msg in warmup_messages:
                messages.append((role_map[msg["role"]], msg["content"]))
        messages.extend(warmup_messages)

    # messages.append(HumanMessage(content=prompt_template))
    messages.append(("human", prompt_template))
    return ChatPromptTemplate.from_messages(messages=messages)


@lru_cache
def _get_llm(
        model=DEFAULT_MODEL,
        engine=DEFAULT_ENGINE,
        temperature=0.7,
        max_tokens=1024,
        timeout=None,
        max_retries=2,
        streaming=False,
        **kwargs,
):
    common_params = {
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "max_retries": max_retries,
        "streaming": streaming,
        **kwargs,
    }
    if engine == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, **common_params)
    # elif engine == "azure":
    #     from langchain_openai import AzureChatOpenAI

    #     return AzureChatOpenAI(
    #         deployment_name=model,
    #         openai_api_key=os.getenv("OPENAI_API_KEY"),
    #         **common_params,
    #     )
    elif engine == "local":
        from langchain_community.chat_models import ChatOllama

        return ChatOllama(model=model, **common_params)
    # elif engine == "azure_llama":
    #     from langchain_community.chat_models.azureml_endpoint import (
    #         AzureMLChatOnlineEndpoint,
    #         AzureMLEndpointApiType,
    #     )
    #     from langchain_community.chat_models.azureml_endpoint import (
    #         CustomOpenAIChatContentFormatter,
    #     )

    #     return AzureMLChatOnlineEndpoint(
    #         endpoint_url=os.getenv("AZURE_ENDPOINT_URL"),
    #         endpoint_api_type=AzureMLEndpointApiType.serverless,
    #         endpoint_api_key=os.getenv("AZURE_OPENAI_KEY"),
    #         content_formatter=CustomOpenAIChatContentFormatter(),
    #         **common_params,
    #     )
    elif engine == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=model, **common_params)
    elif engine == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, **common_params)
    else:
        raise ValueError(f"Unknown engine: {engine}, should be one of {models_per_engine.keys()}")


@dataclass
class LLMModelParams:
    """Parameters for configuring the LLM model"""
    model: str = DEFAULT_MODEL
    engine: str = DEFAULT_ENGINE
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout: Optional[float] = None
    max_retries: int = 2
    streaming: bool = False


@dataclass
class LLMQueryParams:
    """Parameters for the query itself"""
    warmup_messages: Optional[list] = None
    use_langfuse: Optional[bool] = None
    structured_output_schema: Optional[Any] = None


DEFAULT_SYSTEM_MESSAGE = "You're a helpful assistant"


def query_llm_raw(
        prompt: str,
        system: str = DEFAULT_SYSTEM_MESSAGE,
        *,
        # Model configuration
        model: str = DEFAULT_MODEL,
        engine: str = DEFAULT_ENGINE,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        # Query configuration
        warmup_messages: Optional[list] = None,
        use_langfuse: Optional[bool] = None,
        structured_output_schema: Optional[Any] = None,
        **extra_kwargs
) -> Any:
    """Raw LLM query - returns the complete response object from the underlying LLM."""
    model_params = LLMModelParams(
        model=model,
        engine=engine,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries
    )

    query_params = LLMQueryParams(
        warmup_messages=warmup_messages,
        use_langfuse=use_langfuse,
        structured_output_schema=structured_output_schema
    )

    llm = _get_llm(**vars(model_params), **extra_kwargs)
    
    if structured_output_schema:
        llm = llm.with_structured_output(structured_output_schema)

    chat_prompt = build_langchain_prompt(
        system,
        warmup_messages=warmup_messages
    ) if isinstance(system, str) else system

    chain = chat_prompt | llm

    config = {}
    if use_langfuse:
        from langfuse.callback import CallbackHandler
        config["callbacks"] = [CallbackHandler()]

    return chain.invoke(input={"prompt": prompt}, config=config)


def query_llm_text(
    prompt: str,
        system: str = DEFAULT_SYSTEM_MESSAGE,
        *,
        # Model configuration
        model: str = DEFAULT_MODEL,
        engine: str = DEFAULT_ENGINE,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        # Query configuration
        warmup_messages: Optional[list] = None,
        use_langfuse: Optional[bool] = None,
        **extra_kwargs
) -> str:
    """LLM query that returns just the text response."""
    result = query_llm_raw(
        prompt=prompt,
        system=system,
        model=model,
        engine=engine,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries,
        warmup_messages=warmup_messages,
        use_langfuse=use_langfuse,
        **extra_kwargs
    )
    return result.content


def query_llm_stream(
        prompt: str,
        system: str,
        model: str = DEFAULT_MODEL,
        engine: str = DEFAULT_ENGINE,
        **kwargs
) -> Generator[str, None, None]:
    """Stream text chunks from LLM."""
    llm = _get_llm(model=model, engine=engine, streaming=True, **kwargs)
    chat_prompt = build_langchain_prompt(system) if isinstance(system, str) else system
    chain = chat_prompt | llm

    for chunk in chain.stream(input={"prompt": prompt}):
        yield chunk.content


def query_llm_structured(
        prompt: str,
        system: str,
        output_schema: Type[BaseModel],
        model: str = DEFAULT_MODEL,
        engine: str = DEFAULT_ENGINE,
        **kwargs
) -> BaseModel:
    """Query LLM with structured output."""
    llm = _get_llm(model=model, engine=engine, streaming=False, **kwargs)
    llm = llm.with_structured_output(output_schema)
    chat_prompt = build_langchain_prompt(system) if isinstance(system, str) else system
    chain = chat_prompt | llm
    return chain.invoke(input={"prompt": prompt})


def query_llm_structured_stream(
        prompt: str,
        system: str,
        output_schema: Type[BaseModel],
        model: str = DEFAULT_MODEL,
        engine: str = DEFAULT_ENGINE,
        **kwargs
) -> Generator[BaseModel, None, None]:
    """Stream structured output from LLM."""
    llm = _get_llm(model=model, engine=engine, streaming=True, **kwargs)
    llm = llm.with_structured_output(output_schema)
    chat_prompt = build_langchain_prompt(system) if isinstance(system, str) else system
    chain = chat_prompt | llm

    for chunk in chain.stream(input={"prompt": prompt}):
        yield chunk


# Async versions
async def aquery_llm_raw(
        prompt: str,
        system: str,
        model: str = DEFAULT_MODEL,
        engine: str = DEFAULT_ENGINE,
        **kwargs
) -> Any:
    llm = _get_llm(model=model, engine=engine, streaming=False, **kwargs)
    chat_prompt = build_langchain_prompt(system) if isinstance(system, str) else system
    chain = chat_prompt | llm
    return await chain.ainvoke(input={"prompt": prompt})


async def aquery_llm_text(
        prompt: str,
        system: str = DEFAULT_SYSTEM_MESSAGE,
        *,
        # Model configuration
        model: str = DEFAULT_MODEL,
        engine: str = DEFAULT_ENGINE,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        # Query configuration
        warmup_messages: Optional[list] = None,
        use_langfuse: Optional[bool] = None,
        **extra_kwargs
) -> str:
    """Async LLM query that returns just the text response."""
    result = await aquery_llm_raw(
        prompt=prompt,
        system=system,
        model=model,
        engine=engine,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries,
        warmup_messages=warmup_messages,
        use_langfuse=use_langfuse,
        **extra_kwargs
    )
    return result.content


async def aquery_llm_stream(
        prompt: str,
        system: str,
        model: str = DEFAULT_MODEL,
        engine: str = DEFAULT_ENGINE,
        **kwargs
) -> AsyncGenerator[str, None]:
    llm = _get_llm(model=model, engine=engine, streaming=True, **kwargs)
    chat_prompt = build_langchain_prompt(system) if isinstance(system, str) else system
    chain = chat_prompt | llm

    async for chunk in chain.astream(input={"prompt": prompt}):
        yield chunk.content


async def aquery_llm_structured(
        prompt: str,
        system: str,
        output_schema: Type[BaseModel],
        model: str = DEFAULT_MODEL,
        engine: str = DEFAULT_ENGINE,
        **kwargs
) -> BaseModel:
    llm = _get_llm(model=model, engine=engine, streaming=False, **kwargs)
    llm = llm.with_structured_output(output_schema)
    chat_prompt = build_langchain_prompt(system) if isinstance(system, str) else system
    chain = chat_prompt | llm
    return await chain.ainvoke(input={"prompt": prompt})


async def aquery_llm_structured_stream(
        prompt: str,
        system: str,
        output_schema: Type[BaseModel],
        model: str = DEFAULT_MODEL,
        engine: str = DEFAULT_ENGINE,
        **kwargs
) -> AsyncGenerator[BaseModel, None]:
    llm = _get_llm(model=model, engine=engine, streaming=True, **kwargs)
    llm = llm.with_structured_output(output_schema)
    chat_prompt = build_langchain_prompt(system) if isinstance(system, str) else system
    chain = chat_prompt | llm

    async for chunk in chain.astream(input={"prompt": prompt}):
        yield chunk


def escape_curly_braces(text):
    return text.replace("{", "{{").replace("}", "}}")


def langfuse_env_available():
    return bool(os.getenv("LANGFUSE_SECRET_KEY"))


@deprecated(reason="deprecated together with query_gpt and aquery_gpt")
def _query_llm(
        llm,
        system,
        prompt,
        warmup_messages=None,
        use_langfuse=False,
        stream=False,
        structured_output_schema=None,
):
    config = {}
    if use_langfuse:
        from langfuse.callback import CallbackHandler

        langfuse_callback = CallbackHandler()
        config["callbacks"] = [langfuse_callback]

    if isinstance(system, str):
        chat_prompt = build_langchain_prompt(system, warmup_messages=warmup_messages)
    else:
        chat_prompt = system

    if structured_output_schema:
        llm = llm.with_structured_output(structured_output_schema)

    chain = chat_prompt | llm

    if stream:
        return chain.stream(input={"prompt": prompt}, config=config)
    else:
        result = chain.invoke(input={"prompt": prompt}, config=config)
        if structured_output_schema:
            return result
        else:
            return result.content


@deprecated(
    reason="deprecated in favor of typed methods - query_llm_text, query_llm_stream, query_llm_structured, query_llm_structured_stream")
def query_gpt(
        prompt,
        system,
        warmup_messages=None,
        model=DEFAULT_MODEL,
        engine=DEFAULT_ENGINE,
        use_langfuse=None,
        temperature=0.7,
        max_tokens=1024,
        timeout=None,
        max_retries=2,
        stream=False,
        structured_output_schema=None,
        **kwargs,
) -> Union[str, Generator[str, None, None], Any]:
    if use_langfuse is None:
        use_langfuse = langfuse_env_available()
    llm = _get_llm(
        model=model,
        engine=engine,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries,
        streaming=stream,
        **kwargs,
    )

    result = _query_llm(
        llm,
        system,
        prompt,
        use_langfuse=use_langfuse,
        warmup_messages=warmup_messages,
        stream=stream,
        structured_output_schema=structured_output_schema,
    )

    if stream:
        return (chunk.content for chunk in result)
    else:
        return result


@deprecated(
    reason="deprecated in favor of typed methods - aquery_llm_text, aquery_llm_stream, aquery_llm_structured, aquery_llm_structured_stream")
async def aquery_gpt(
        prompt,
        system,
        warmup_messages=None,
        model=DEFAULT_MODEL,
        engine=DEFAULT_ENGINE,
        use_langfuse=None,
        temperature=0.7,
        max_tokens=1024,
        timeout=None,
        max_retries=2,
        stream=False,
        structured_output_schema=None,
        **kwargs,
):
    """Async version of query_gpt using langchain's .ainvoke()"""
    if use_langfuse is None:
        use_langfuse = langfuse_env_available()

    llm = _get_llm(
        model=model,
        engine=engine,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries,
        streaming=stream,
        **kwargs,
    )

    if structured_output_schema:
        llm = llm.with_structured_output(structured_output_schema)

    chat_prompt = build_langchain_prompt(system, warmup_messages=warmup_messages) if isinstance(system, str) else system

    chain = chat_prompt | llm

    config = {}
    if use_langfuse:
        from langfuse.callback import CallbackHandler

        config["callbacks"] = [CallbackHandler()]

    if stream:

        async def config_stream():
            async for chunk in chain.astream(input={"prompt": prompt}, config=config):
                yield chunk.content if not structured_output_schema else chunk

        return config_stream()
    else:
        result = await chain.ainvoke(input={"prompt": prompt}, config=config)

    return result if structured_output_schema else result.content
