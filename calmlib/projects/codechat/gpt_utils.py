import os
from functools import lru_cache
from pathlib import Path
from typing import Union, Generator

from dotenv import load_dotenv

Pathlike = Union[str, Path]
load_dotenv()


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


def build_langchain_prompt(system: str, warmup_messages=None, prompt_template="{prompt}") -> ChatPromptTemplate:
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


def _query_llm(llm, system, prompt, warmup_messages=None, use_langfuse=False, stream=False):
    config = {}
    if use_langfuse:
        from langfuse.callback import CallbackHandler

        langfuse_callback = CallbackHandler()
        config["callbacks"] = [langfuse_callback]

    if isinstance(system, str):
        chat_prompt = build_langchain_prompt(system, warmup_messages=warmup_messages)
    else:
        chat_prompt = system

    chain = chat_prompt | llm

    if stream:
        return chain.stream(input={"prompt": prompt}, config=config)
    else:
        result = chain.invoke(input={"prompt": prompt}, config=config)
        return result.content


def query_openai(
    prompt: str,
    system: str = "You're a helpful assistant",
    warmup_messages=None,
    model_name="gpt-3.5-turbo",
    use_langfuse=False,
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    **kwargs,
) -> str:
    from langchain_community.chat_models import ChatOpenAI

    # config = {}
    # if use_langfuse:
    #     langfuse_callback = get_langfuse_callback()
    #     config["callbacks"] = [langfuse_callback]
    # Initialize the language model
    llm = ChatOpenAI(
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries,
        **kwargs,
    )

    return _query_llm(llm, system, prompt, use_langfuse=use_langfuse, warmup_messages=warmup_messages)

    # # Build the prompt
    # chat_prompt = build_langchain_prompt(system)
    #
    # # Set up the LangChain chain
    # chain = chat_prompt | llm
    # result = chain.invoke(input={"prompt": prompt}, config=config)
    #
    # return result.content


models_per_engine = {
    "openai": ["gpt-4o", "gpt-4", "gpt-3.5-turbo"],
    "azure": ["us4o", "blankgpt4_32k"],
    "local": ["llama3"],
    "anthropic": ["claude-3-5-sonnet-20240620", "claude-3-sonnet-20240229"],
}
DEFAULT_ENGINE = "anthropic"
DEFAULT_MODEL = models_per_engine[DEFAULT_ENGINE][0]


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
    from langchain_community.chat_models.azureml_endpoint import (
        AzureMLChatOnlineEndpoint,
        AzureMLEndpointApiType,
    )
    from langchain_community.chat_models.azureml_endpoint import CustomOpenAIChatContentFormatter

    common_params = {
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "max_retries": max_retries,
        "streaming": streaming,
        **kwargs,
    }

    if engine == "openai":
        from langchain_community.chat_models import ChatOpenAI

        return ChatOpenAI(model_name=model, **common_params)
    elif engine == "azure":
        from langchain_community.chat_models import AzureChatOpenAI

        return AzureChatOpenAI(
            deployment_name=model,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            **common_params,
        )
    elif engine == "local":
        from langchain_community.chat_models import ChatOllama

        return ChatOllama(model=model, **common_params)
    elif engine == "azure_llama":
        return AzureMLChatOnlineEndpoint(
            endpoint_url=os.getenv("AZURE_ENDPOINT_URL"),
            endpoint_api_type=AzureMLEndpointApiType.serverless,
            endpoint_api_key=os.getenv("AZURE_OPENAI_KEY"),
            content_formatter=CustomOpenAIChatContentFormatter(),
            **common_params,
        )
    elif engine == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, **common_params)
    else:
        raise ValueError(f"Unknown engine: {engine}, should be one of {models_per_engine.keys()}")


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
    **kwargs,
) -> Union[str, Generator[str, None, None]]:
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

    result = _query_llm(llm, system, prompt, use_langfuse=use_langfuse, warmup_messages=warmup_messages, stream=stream)

    if stream:
        return (chunk.content for chunk in result)
    else:
        return result


def escape_curly_braces(text):
    return text.replace("{", "{{").replace("}", "}}")


def langfuse_env_available():
    return bool(os.getenv("LANGFUSE_SECRET_KEY"))


if __name__ == "__main__":
    load_dotenv()
    prompt = "Tell me a random scientific concept / theory"

    # Non-streaming example
    response = query_gpt(prompt, system="You're a helpful assistant", use_langfuse=langfuse_env_available())
    print("Non-streaming response:", response)

    # Streaming example
    print("\nStreaming response:")
    for chunk in query_gpt(
        prompt, system="You're a helpful assistant", use_langfuse=langfuse_env_available(), stream=True
    ):
        print(chunk, end="", flush=True)
    print()  # New line after streaming is complete
