import asyncio
import json
import os
from functools import lru_cache, partial
from typing import Union, Generator, TYPE_CHECKING, Any

import loguru
import openai
from dotenv import load_dotenv

load_dotenv()

if TYPE_CHECKING:
    from langchain.prompts import ChatPromptTemplate

GPT_RATE_LIMIT = 200  # 200 requests per minute


@lru_cache
def get_limiter(name, rate_limit=GPT_RATE_LIMIT):
    from aiolimiter import AsyncLimiter

    return AsyncLimiter(rate_limit, 60)


# Then use atranscribe_audio_limited instead of atranscribe_audio

token_limit_by_model = {
    "gpt-3.5-turbo": 4096,
    "gpt-4": 8192,
    "gpt-3.5-turbo-16k": 16384,
}


def get_token_count(text, model="gpt-3.5-turbo"):
    """
    calculate amount of tokens in text
    model: gpt-3.5-turbo, gpt-4
    """
    # To get the tokeniser corresponding to a specific model in the OpenAI API:
    import tiktoken

    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))


# todo: add retry in case of error. Or at least handle gracefully
def run_command_with_gpt(command: str, data: str, model="gpt-3.5-turbo"):
    messages = [
        {"role": "system", "content": command},
        {"role": "user", "content": data},
    ]
    response = openai.ChatCompletion.create(messages=messages, model=model)
    return response.choices[0].message.content


# todo: if reason is length - continue generation
async def arun_command_with_gpt(command: str, data: str, model="gpt-3.5-turbo"):
    messages = [
        {"role": "system", "content": command},
        {"role": "user", "content": data},
    ]
    gpt_limiter = get_limiter("gpt")
    async with gpt_limiter:
        response = await openai.ChatCompletion.acreate(messages=messages, model=model)
    return response.choices[0].message.content


def default_merger(chunks, keyword="TEMPORARY_RESULT:"):
    return "\n".join([f"{keyword}\n{chunk}" for chunk in chunks])


def split_by_weight(items, weight_func, limit):
    groups = []
    group = []
    group_weight = 0

    for item in items:
        item_weight = weight_func(item)
        if group_weight + item_weight > limit:
            if not group:
                raise ValueError(f"Item {item} is too big to fit into a single group with limit {limit}")
            groups.append(group)
            group = []
            group_weight = 0
        group.append(item)
        group_weight += item_weight

    if group:  # If there are items left in the current group, append it to groups.
        groups.append(group)

    return groups


async def apply_command_recursively(command, chunks, model="gpt-3.5-turbo", merger=None, logger=None):
    """
    Apply GPT command recursively to the data
    """
    if logger is None:
        logger = loguru.logger
    if merger is None:
        merger = default_merger
    token_limit = token_limit_by_model[model]
    while len(chunks) > 1:
        groups = split_by_weight(chunks, partial(get_token_count, model=model), token_limit)
        if len(groups) == len(chunks):
            raise ValueError(f"Chunk size is too big for model {model} with limit {token_limit}")
        logger.debug(f"Split into {len(groups)} groups")
        # apply merger
        merged_chunks = map(merger, groups)
        # apply command
        chunks = await amap_gpt_command(merged_chunks, command, model=model)
        logger.debug(f"Intermediate Result: {chunks}")

    return chunks[0]


def map_gpt_command(chunks, command, all_results=False, model="gpt-3.5-turbo", logger=None):
    """
    Run GPT command on each chunk one by one
    Accumulating temporary results and supplying them to the next chunk
    """
    if logger is None:
        logger = loguru.logger
    logger.debug(f"Running command: {command}")

    temporary_results = None
    results = []
    for chunk in chunks:
        data = {"TEXT": chunk, "TEMPORARY_RESULTS": temporary_results}
        data_str = json.dumps(data, ensure_ascii=False)
        temporary_results = run_command_with_gpt(command, data_str, model=model)
        results.append(temporary_results)

    logger.debug(f"Results: {results}")
    if all_results:
        return results
    else:
        return results[-1]


MERGE_COMMAND_TEMPLATE = """
You're merge assistant. The following command was applied to each chunk.
The results are separated by keyword "{keyword}"
You have to merge all the results into one. 
COMMAND:
{command}
"""


async def amap_gpt_command(chunks, command, model="gpt-3.5-turbo", merge=False):
    """
    Run GPT command on each chunk in parallel
    Merge results if merge=True
    """
    tasks = [arun_command_with_gpt(command, chunk, model=model) for chunk in chunks]

    # Using asyncio.gather to collect all results
    completed_tasks = await asyncio.gather(*tasks)

    if merge:
        merge_command = MERGE_COMMAND_TEMPLATE.format(command=command, keyword="TEMPORARY_RESULT:").strip()
        return apply_command_recursively(merge_command, completed_tasks, model=model)
    else:
        return completed_tasks


# region langchain


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
        # timeout=timeout,
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

        return ChatOpenAI(model_name=model, **common_params)
    elif engine == "azure":
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            deployment_name=model,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            **common_params,
        )
    elif engine == "local":
        from langchain_community.chat_models import ChatOllama

        return ChatOllama(model=model, **common_params)
    elif engine == "azure_llama":
        from langchain_community.chat_models.azureml_endpoint import (
            AzureMLChatOnlineEndpoint,
            AzureMLEndpointApiType,
        )
        from langchain_community.chat_models.azureml_endpoint import (
            CustomOpenAIChatContentFormatter,
        )

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


def escape_curly_braces(text):
    return text.replace("{", "{{").replace("}", "}}")


def langfuse_env_available():
    return bool(os.getenv("LANGFUSE_SECRET_KEY"))


# endregion langchain

if __name__ == "__main__":
    load_dotenv()
    prompt = "Tell me a random scientific concept / theory"

    # Non-streaming example
    response = query_gpt(prompt, system="You're a helpful assistant", use_langfuse=langfuse_env_available())
    print("Non-streaming response:", response)

    # Streaming example
    print("\nStreaming response:")
    for chunk in query_gpt(
        prompt,
        system="You're a helpful assistant",
        use_langfuse=langfuse_env_available(),
        stream=True,
    ):
        print(chunk, end="", flush=True)
    print()  # New line after streaming is complete
