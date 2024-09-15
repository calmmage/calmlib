import abc
import re
from typing import List, Dict


class LangchainFewshotPromptBase(abc.ABC):
    SYSTEM_TEMPLATE: str
    HUMAN_TEMPLATE: str
    SAMPLE_MESSAGES: List[Dict[str, str]]
    OUTPUT_FORMAT: str

    @staticmethod
    def trim_extra_whitespace(text):
        # Replace multiple spaces with a single space
        text = re.sub(r" +", " ", text)

        # Replace combinations of newlines and spaces with newlines only
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)

        # Replace more than two consecutive newlines with two newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        return text

    @staticmethod
    def escape_curly_braces(text):
        return text.replace("{", "{{").replace("}", "}}")

    @classmethod
    def get_prompt(cls, trim_extra_whitespace=False):
        from langchain.prompts import ChatPromptTemplate

        role_message = cls.SYSTEM_TEMPLATE
        human_template = cls.HUMAN_TEMPLATE
        # output_example = "output_example"
        messages = [
            ("system", role_message),
        ]
        for sample_message in cls.SAMPLE_MESSAGES:
            messages.append(
                (
                    "human",
                    cls.escape_curly_braces(cls.HUMAN_TEMPLATE.format(**sample_message)),
                )
            )
            messages.append(
                (
                    "ai",
                    cls.escape_curly_braces(cls.OUTPUT_FORMAT.format(**sample_message)),
                )
            )

        messages.append(("human", human_template))
        # for role, message in messages:
        #     print(role, message)

        if trim_extra_whitespace:
            messages = [(role, cls.trim_extra_whitespace(message)) for role, message in messages]

        full_prompt = ChatPromptTemplate.from_messages(messages)
        return full_prompt
