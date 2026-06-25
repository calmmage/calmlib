"""
Engine implementations for user interaction backends
"""

from abc import ABC, abstractmethod
from typing import Any

import httpx
from loguru import logger

from calmlib.utils.env_discovery import find_calmmage_env_key


class UserInteractionEngine(ABC):
    """Base class for user interaction engines"""

    @abstractmethod
    async def ask_user(self, question: str, timeout: float | None = None) -> str | None:
        """Ask user a text question and get string response"""
        raise NotImplementedError

    @abstractmethod
    async def ask_user_choice(
        self,
        question: str,
        choices: list[str] | dict[str, str],
        timeout: float | None = None,
    ) -> str | None:
        """Ask user to choose from options"""
        raise NotImplementedError

    @abstractmethod
    async def ask_user_confirmation(
        self, question: str, timeout: float | None = None
    ) -> bool | None:
        """Ask user yes/no question and get boolean response"""
        raise NotImplementedError

    @abstractmethod
    async def ask_user_raw(
        self, question: str, timeout: float | None = None
    ) -> Any | None:
        """Ask user and return raw response object"""
        raise NotImplementedError

    @abstractmethod
    async def notify_user(self, message: str):
        """Notify user with a message"""
        raise NotImplementedError


class PythonInputEngine(UserInteractionEngine):
    """Basic Python input() engine"""

    async def ask_user(self, question: str, timeout: float | None = None) -> str | None:
        import asyncio

        async def _input():
            try:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, lambda: input(f"{question}: ").strip()
                )
            except (KeyboardInterrupt, EOFError):
                return None

        try:
            if timeout:
                return await asyncio.wait_for(_input(), timeout=timeout)
            else:
                return await _input()
        except asyncio.TimeoutError:
            print(
                f"\nTimeout after {timeout}s - WARNING: stdin may be polluted, press Enter to clear before next input"
            )
            return None

    async def ask_user_choice(
        self,
        question: str,
        choices: list[str] | dict[str, str],
        timeout: float | None = None,
    ) -> str | None:
        import asyncio

        if isinstance(choices, list):
            choices_dict = {str(i + 1): choice for i, choice in enumerate(choices)}
        else:
            choices_dict = choices

        async def _input():
            print(f"\n{question}")
            for key, value in choices_dict.items():
                print(f"  {key}) {value}")

            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, lambda: input("Choice: ").strip()
                )
                if response in choices_dict:
                    return (
                        choices_dict[response]
                        if isinstance(choices, list)
                        else response
                    )
                # Allow direct text input for choice value
                for key, value in choices_dict.items():
                    if response.lower() == value.lower():
                        return value if isinstance(choices, list) else key
                return response  # Return raw input if no match
            except (KeyboardInterrupt, EOFError):
                return None

        try:
            if timeout:
                return await asyncio.wait_for(_input(), timeout=timeout)
            else:
                return await _input()
        except asyncio.TimeoutError:
            print(
                f"\nTimeout after {timeout}s - WARNING: stdin may be polluted, press Enter to clear before next input"
            )
            return None

    async def ask_user_confirmation(
        self, question: str, timeout: float | None = None
    ) -> bool | None:
        import asyncio

        async def _input():
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, lambda: input(f"{question} (y/n): ").strip().lower()
                )
                if response in ["y", "yes", "1", "true"]:
                    return True
                elif response in ["n", "no", "0", "false"]:
                    return False
                return None
            except (KeyboardInterrupt, EOFError):
                return None

        try:
            if timeout:
                return await asyncio.wait_for(_input(), timeout=timeout)
            else:
                return await _input()
        except asyncio.TimeoutError:
            print(
                f"\nTimeout after {timeout}s - WARNING: stdin may be polluted, press Enter to clear before next input"
            )
            return None

    async def ask_user_raw(
        self, question: str, timeout: float | None = None
    ) -> Any | None:
        # For basic input engine, raw is the same as regular
        return await self.ask_user(question, timeout=timeout)

    async def notify_user(self, message: str):
        """Notify user with a message"""
        print(message)


class TyperEngine(UserInteractionEngine):
    """Typer CLI engine using rich prompts"""

    def __init__(self):
        import typer
        from rich.prompt import Confirm, Prompt

        self.typer = typer
        self.Prompt = Prompt
        self.Confirm = Confirm

    async def ask_user(self, question: str, timeout: float | None = None) -> str | None:
        import asyncio

        async def _input():
            try:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, lambda: self.Prompt.ask(question)
                )
            except (KeyboardInterrupt, EOFError):
                return None

        try:
            if timeout:
                return await asyncio.wait_for(_input(), timeout=timeout)
            else:
                return await _input()
        except asyncio.TimeoutError:
            print(
                f"\nTimeout after {timeout}s - WARNING: stdin may be polluted, press Enter to clear before next input"
            )
            return None

    async def ask_user_choice(
        self,
        question: str,
        choices: list[str] | dict[str, str],
        timeout: float | None = None,
    ) -> str | None:
        import asyncio

        if isinstance(choices, list):
            choices_list = choices
        else:
            choices_list = list(choices.values())

        async def _input():
            try:
                from rich.prompt import Prompt

                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, lambda: Prompt.ask(question, choices=choices_list)
                )
            except (KeyboardInterrupt, EOFError):
                return None

        try:
            if timeout:
                return await asyncio.wait_for(_input(), timeout=timeout)
            else:
                return await _input()
        except asyncio.TimeoutError:
            print(
                f"\nTimeout after {timeout}s - WARNING: stdin may be polluted, press Enter to clear before next input"
            )
            return None

    async def ask_user_confirmation(
        self, question: str, timeout: float | None = None
    ) -> bool | None:
        import asyncio

        async def _input():
            try:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, lambda: self.Confirm.ask(question)
                )
            except (KeyboardInterrupt, EOFError):
                return None

        try:
            if timeout:
                return await asyncio.wait_for(_input(), timeout=timeout)
            else:
                return await _input()
        except asyncio.TimeoutError:
            print(
                f"\nTimeout after {timeout}s - WARNING: stdin may be polluted, press Enter to clear before next input"
            )
            return None

    async def ask_user_raw(
        self, question: str, timeout: float | None = None
    ) -> Any | None:
        return await self.ask_user(question, timeout=timeout)

    async def notify_user(self, message: str):
        """Notify user with a message"""
        self.typer.echo(message)


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

    async def ask_user(self, question: str, timeout: float | None = None) -> str | None:
        from botspot.user_interactions import ask_user

        return await ask_user(self.chat_id, question, self.state, timeout=timeout)

    async def ask_user_choice(
        self,
        question: str,
        choices: list[str] | dict[str, str],
        timeout: float | None = None,
    ) -> str | None:
        from botspot.user_interactions import ask_user_choice

        return await ask_user_choice(
            self.chat_id, question, choices, self.state, timeout=timeout
        )

    async def ask_user_confirmation(
        self, question: str, timeout: float | None = None
    ) -> bool | None:
        from botspot.user_interactions import ask_user_confirmation

        return await ask_user_confirmation(
            self.chat_id, question, self.state, timeout=timeout
        )

    async def ask_user_raw(
        self, question: str, timeout: float | None = None
    ) -> Any | None:
        from botspot.user_interactions import ask_user_raw

        return await ask_user_raw(self.chat_id, question, self.state, timeout=timeout)

    async def notify_user(self, message: str):
        from botspot.utils import send_safe

        return await send_safe(self.chat_id, message)


class ServiceTelegramHttpEngine(UserInteractionEngine):
    """User interaction engine backed by local FastAPI service."""

    def __init__(
        self,
        base_url: str | None = None,
        chat_id: int | None = None,
        timeout: int | None = None,
    ):
        if base_url is None:
            base_url = find_calmmage_env_key(
                "CALMMAGE_USER_INTERACTIONS_SERVICE_URL",
                default="http://127.0.0.1:8777",
            )
        self.base_url = base_url.rstrip("/")
        self.chat_id = chat_id
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=None)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            res = await self._client.post(url, json=payload)
            res.raise_for_status()
            return res.json()
        except Exception as exc:
            logger.error(f"ServiceTelegramHttpEngine request failed: {exc}")
            raise

    async def ask_user(self, question: str, timeout: float | None = None) -> str | None:
        payload = {
            "question": question,
            "timeout_sec": int(timeout) if timeout else self.timeout,
            "chat_id": self.chat_id,
        }
        data = await self._post("/ask/text", payload)
        return data.get("response")

    async def ask_user_choice(
        self,
        question: str,
        choices: list[str] | dict[str, str],
        timeout: float | None = None,
    ) -> str | None:
        payload: dict[str, Any] = {
            "question": question,
            "timeout_sec": int(timeout) if timeout else self.timeout,
            "chat_id": self.chat_id,
        }
        if isinstance(choices, list):
            payload["choices"] = choices
        else:
            payload["choices_map"] = choices
        data = await self._post("/ask/choice", payload)
        return data.get("response")

    async def ask_user_confirmation(
        self, question: str, timeout: float | None = None
    ) -> bool | None:
        payload = {
            "question": question,
            "timeout_sec": int(timeout) if timeout else self.timeout,
            "chat_id": self.chat_id,
        }
        data = await self._post("/ask/confirmation", payload)
        return data.get("response")

    async def ask_user_raw(
        self, question: str, timeout: float | None = None
    ) -> Any | None:
        return await self.ask_user(question, timeout=timeout)

    async def notify_user(self, message: str):
        payload = {"message": message, "chat_id": self.chat_id}
        await self._post("/notify", payload)
