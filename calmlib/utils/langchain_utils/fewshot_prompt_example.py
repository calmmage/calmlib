from textwrap import dedent

from calmlib.utils.langchain_utils.langchain_fewshot_prompt_base import LangchainFewshotPromptBase
from langchain_openai import ChatOpenAI


class DummyPrompt(LangchainFewshotPromptBase):
    # todo: replace this sample system message with a specific command for generation
    DEFAULT_COMMAND = "reply_text"

    SYSTEM_TEMPLATE = dedent(
        f"""
        You're command executor. Out of the following commands, which one would you like to execute?. 
        By default, you have the following command available: {DEFAULT_COMMAND}
        """
    )

    # todo: polish the human template for ...
    HUMAN_TEMPLATE = dedent(
        """
        AVAILABLE COMMANDS:
        {commands_list}
        USER INPUT
        {user_input}
        """
    )

    SAMPLE_MESSAGES = [
        {
            "commands_list": "",
            "user_input": "What commands do you have available?",
            "output": f"I currently only have 1 command available. It is: {DEFAULT_COMMAND}",
            "output_command": f"{DEFAULT_COMMAND}",
        },
        {
            "commands_list": dedent(
                """
            - save_code
            - list_files
            """
            ),
            "user_input": "What commands do you have available?",
            "output": f"I currently have 3 commands available. They are: save_code, list_files, and {DEFAULT_COMMAND}",
            "output_command": f"{DEFAULT_COMMAND}",
        },
        {
            "commands_list": dedent(
                """
            - save_code
            - list_files
            """
            ),
            "user_input": "Can you list the files we saved?",
            "output": "",
            "output_command": "list_files",
        },
    ]
    OUTPUT_FORMAT = dedent(
        """
    {{
        "output_command": "{output_command}",
        "output": "{output}"
    }}
    """
    )


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    full_prompt = DummyPrompt.get_prompt(True)
    llm = ChatOpenAI(model="gpt-4")

    chain = full_prompt | llm

    data = dict(
        commands_list="- print_test_page (activates printer) - apply_patch (patches the wound)",
        user_input="What commands do you have available?",
    )

    response = chain.invoke(data)
    print(response.content)
