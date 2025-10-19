"""
Engine implementations for user interaction backends
"""

from abc import ABC, abstractmethod
from typing import Any


class UserInteractionEngine(ABC):
    """Base class for user interaction engines"""

    @abstractmethod
    async def ask_user(self, question: str, **kwargs) -> str | None:
        """Ask user a text question and get string response"""
        pass

    @abstractmethod
    async def ask_user_choice(
        self, question: str, choices: list[str] | dict[str, str], **kwargs
    ) -> str | None:
        """Ask user to choose from options"""
        pass

    @abstractmethod
    async def ask_user_confirmation(self, question: str, **kwargs) -> bool | None:
        """Ask user yes/no question and get boolean response"""
        pass

    @abstractmethod
    async def ask_user_raw(self, question: str, **kwargs) -> Any | None:
        """Ask user and return raw response object"""
        pass


class PythonInputEngine(UserInteractionEngine):
    """Basic Python input() engine"""

    async def ask_user(self, question: str, **kwargs) -> str | None:
        try:
            return input(f"{question}: ").strip()
        except (KeyboardInterrupt, EOFError):
            return None

    async def ask_user_choice(
        self, question: str, choices: list[str] | dict[str, str], **kwargs
    ) -> str | None:
        if isinstance(choices, list):
            choices_dict = {str(i + 1): choice for i, choice in enumerate(choices)}
        else:
            choices_dict = choices

        print(f"\n{question}")
        for key, value in choices_dict.items():
            print(f"  {key}) {value}")

        try:
            response = input("Choice: ").strip()
            if response in choices_dict:
                return choices_dict[response] if isinstance(choices, list) else response
            # Allow direct text input for choice value
            for key, value in choices_dict.items():
                if response.lower() == value.lower():
                    return value if isinstance(choices, list) else key
            return response  # Return raw input if no match
        except (KeyboardInterrupt, EOFError):
            return None

    async def ask_user_confirmation(self, question: str, **kwargs) -> bool | None:
        try:
            response = input(f"{question} (y/n): ").strip().lower()
            if response in ["y", "yes", "1", "true"]:
                return True
            elif response in ["n", "no", "0", "false"]:
                return False
            return None
        except (KeyboardInterrupt, EOFError):
            return None

    async def ask_user_raw(self, question: str, **kwargs) -> Any | None:
        # For basic input engine, raw is the same as regular
        return self.ask_user(question, **kwargs)


class TyperEngine(UserInteractionEngine):
    """Typer CLI engine using rich prompts"""

    def __init__(self):
        try:
            import typer
            from rich.prompt import Confirm, Prompt

            self.typer = typer
            self.Prompt = Prompt
            self.Confirm = Confirm
        except ImportError:
            raise ImportError("typer and rich are required for TyperEngine")

    async def ask_user(self, question: str, **kwargs) -> str | None:
        try:
            return self.Prompt.ask(question)
        except (KeyboardInterrupt, EOFError):
            return None

    async def ask_user_choice(
        self, question: str, choices: list[str] | dict[str, str], **kwargs
    ) -> str | None:
        if isinstance(choices, list):
            choices_list = choices
        else:
            choices_list = list(choices.values())

        try:
            from rich.prompt import Prompt

            return Prompt.ask(question, choices=choices_list)
        except (KeyboardInterrupt, EOFError):
            return None

    async def ask_user_confirmation(self, question: str, **kwargs) -> bool | None:
        try:
            return self.Confirm.ask(question)
        except (KeyboardInterrupt, EOFError):
            return None

    async def ask_user_raw(self, question: str, **kwargs) -> Any | None:
        return self.ask_user(question, **kwargs)


class BotspotEngine(UserInteractionEngine):
    """Botspot Telegram engine integration"""

    def __init__(self, chat_id: int | None = None, state=None):
        try:
            from botspot.user_interactions import (
                ask_user_choice as botspot_ask_user_choice,
                ask_user_confirmation as botspot_ask_user_confirmation,
                ask_user_raw as botspot_ask_user_raw,
            )

            self.botspot_ask_user = botspot_ask_user
            self.botspot_ask_user_choice = botspot_ask_user_choice
            self.botspot_ask_user_confirmation = botspot_ask_user_confirmation
            self.botspot_ask_user_raw = botspot_ask_user_raw
            self.chat_id = chat_id
            self.state = state
        except ImportError:
            raise ImportError("botspot is required for BotspotEngine")

    async def _ask_user(self, question: str, **kwargs) -> str | None:
        from botspot.user_interactions import ask_user

        return await ask_user(self.chat_id, question, self.state, **kwargs)

    async def ask_user_choice(
        self, question: str, choices: list[str] | dict[str, str], **kwargs
    ) -> str | None:
        from botspot.user_interactions import ask_user_choice

        return await ask_user_choice(
            self.chat_id, question, choices, self.state, **kwargs
        )

    async def ask_user_confirmation(self, question: str, **kwargs) -> bool | None:
        from botspot.user_interactions import ask_user_confirmation

        return await ask_user_confirmation(self.chat_id, question, self.state, **kwargs)

    async def ask_user_raw(self, question: str, **kwargs) -> Any | None:
        from botspot.user_interactions import ask_user_raw

        return await ask_user_raw(self.chat_id, question, self.state, **kwargs)


class ServiceTelegramBotEngine(UserInteractionEngine):
    """Service telegram bot engine using calmmage service bot"""

    def __init__(
        self, chat_id: int | None = None, use_dev: bool = False, timeout: int = 300
    ):
        """
        Initialize telegram service bot engine

        Args:
            chat_id: Telegram chat ID to send messages to (defaults to CALMMAGE_TELEGRAM_MY_CHAT_ID)
            use_dev: Use development bot instead of production
            timeout: Timeout in seconds for waiting for response
        """
        import os

        from calmlib.telegram.service_bot import get_dev_bot, get_prod_bot

        # Get chat_id from env if not provided
        if chat_id is None:
            chat_id = os.getenv("CALMMAGE_TELEGRAM_MY_CHAT_ID")
            if chat_id:
                chat_id = int(chat_id)
            else:
                raise ValueError(
                    "chat_id not provided and CALMMAGE_TELEGRAM_MY_CHAT_ID not found in environment. "
                    "Run env setup tool or provide chat_id explicitly."
                )

        self.chat_id = chat_id
        self.timeout = timeout
        self.bot = get_dev_bot() if use_dev else get_prod_bot()
        self.loop = None

    def _ensure_loop(self):
        """Ensure we have an event loop"""
        import asyncio

        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            # No loop running, create one
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    async def _send_and_wait(self, text: str, reply_markup=None) -> str | None:
        """Send message and wait for response"""
        import asyncio

        # Send the message
        msg = await self.bot.send_message(self.chat_id, text, reply_markup=reply_markup)

        # Wait for response with timeout
        start_time = asyncio.get_event_loop().time()
        last_offset = None

        while (asyncio.get_event_loop().time() - start_time) < self.timeout:
            updates = await self.bot.get_updates(offset=last_offset, timeout=10)

            for update in updates:
                last_offset = update.update_id + 1

                # Check for message reply
                if update.message and update.message.chat.id == self.chat_id:
                    if (
                        update.message.reply_to_message
                        and update.message.reply_to_message.message_id == msg.message_id
                    ):
                        return update.message.text
                    # Also accept any message from the user after our question
                    elif update.message.date.timestamp() > msg.date.timestamp():
                        return update.message.text

                # Check for callback query (inline button press)
                if (
                    update.callback_query
                    and update.callback_query.message.chat.id == self.chat_id
                ):
                    await self.bot.answer_callback_query(update.callback_query.id)
                    return update.callback_query.data

            await asyncio.sleep(1)

        return None  # Timeout

    def ask_user(self, question: str, **kwargs) -> str | None:
        """Ask user a text question via telegram"""
        self._ensure_loop()

        async def _ask():
            return await self._send_and_wait(question)

        if self.loop.is_running():
            # We're already in an async context
            import nest_asyncio

            nest_asyncio.apply()

        return self.loop.run_until_complete(_ask())

    def ask_user_choice(
        self, question: str, choices: list[str] | dict[str, str], **kwargs
    ) -> str | None:
        """Ask user to choose via inline keyboard"""
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        self._ensure_loop()

        # Build inline keyboard
        keyboard = InlineKeyboardMarkup(row_width=1)

        if isinstance(choices, list):
            for choice in choices:
                keyboard.add(InlineKeyboardButton(text=choice, callback_data=choice))
        else:
            for key, value in choices.items():
                keyboard.add(InlineKeyboardButton(text=value, callback_data=key))

        async def _ask():
            response = await self._send_and_wait(question, reply_markup=keyboard)
            # If it's a list, return the value; if dict, return as-is (the key)
            if isinstance(choices, list):
                return response
            else:
                return response  # Already the key from callback_data

        if self.loop.is_running():
            import nest_asyncio

            nest_asyncio.apply()

        return self.loop.run_until_complete(_ask())

    def ask_user_confirmation(self, question: str, **kwargs) -> bool | None:
        """Ask yes/no via inline keyboard"""
        choices = {"yes": "✅ Yes", "no": "❌ No"}
        response = self.ask_user_choice(question, choices, **kwargs)

        if response == "yes":
            return True
        elif response == "no":
            return False
        return None

    def ask_user_raw(self, question: str, **kwargs) -> Any | None:
        """Return raw text response"""
        return self.ask_user(question, **kwargs)
