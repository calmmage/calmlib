import asyncio
import json
from functools import lru_cache, partial
from typing import TYPE_CHECKING

import loguru
from dotenv import load_dotenv

# load_dotenv()

if TYPE_CHECKING:
    pass

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
    import openai

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
        import openai

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
                raise ValueError(
                    f"Item {item} is too big to fit into a single group with limit {limit}"
                )
            groups.append(group)
            group = []
            group_weight = 0
        group.append(item)
        group_weight += item_weight

    if group:  # If there are items left in the current group, append it to groups.
        groups.append(group)

    return groups


async def apply_command_recursively(
    command, chunks, model="gpt-3.5-turbo", merger=None, logger=None
):
    """
    Apply GPT command recursively to the data
    """
    if logger is None:
        logger = loguru.logger
    if merger is None:
        merger = default_merger
    token_limit = token_limit_by_model[model]
    while len(chunks) > 1:
        groups = split_by_weight(
            chunks, partial(get_token_count, model=model), token_limit
        )
        if len(groups) == len(chunks):
            raise ValueError(
                f"Chunk size is too big for model {model} with limit {token_limit}"
            )
        logger.debug(f"Split into {len(groups)} groups")
        # apply merger
        merged_chunks = map(merger, groups)
        # apply command
        chunks = await amap_gpt_command(merged_chunks, command, model=model)
        logger.debug(f"Intermediate Result: {chunks}")

    return chunks[0]


def map_gpt_command(
    chunks, command, all_results=False, model="gpt-3.5-turbo", logger=None
):
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
        merge_command = MERGE_COMMAND_TEMPLATE.format(
            command=command, keyword="TEMPORARY_RESULT:"
        ).strip()
        return apply_command_recursively(merge_command, completed_tasks, model=model)
    else:
        return completed_tasks


# region langchain


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
    from calmlib.utils.llm_utils.gpt_utils import _query_llm

    return _query_llm(
        llm, system, prompt, use_langfuse=use_langfuse, warmup_messages=warmup_messages
    )

    # # Build the prompt
    # chat_prompt = build_langchain_prompt(system)
    #
    # # Set up the LangChain chain
    # chain = chat_prompt | llm
    # result = chain.invoke(input={"prompt": prompt}, config=config)
    #
    # return result.content


# endregion langchain

if __name__ == "__main__":
    load_dotenv()
    prompt = "Tell me a random scientific concept / theory"

    # Non-streaming example
    response = query_gpt(
        prompt,
        system="You're a helpful assistant",
        use_langfuse=langfuse_env_available(),
    )
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
