"""End-to-end Telegram bot tester using Telethon service client.

Usage:
    from calmlib.telegram.bot_tester import BotTester

    async with BotTester("@my_bot") as tester:
        resp = await tester.send_and_wait("/start")
        assert "Hello" in resp.text
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from telethon import TelegramClient
from telethon.tl.custom.message import Message
from telethon.tl.types import KeyboardButtonCallback


class BotTester:
    """Test a Telegram bot by sending real messages as the service user."""

    def __init__(
        self,
        bot_username: str,
        timeout: float = 10.0,
        account: str = "service",
    ):
        self.bot_username = bot_username.lstrip("@")
        self.timeout = timeout
        self.account = account
        self.client: Optional[TelegramClient] = None
        self._cm = None

    async def __aenter__(self) -> "BotTester":
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    async def connect(self):
        from calmlib.telegram.telethon_client import get_telethon_client_context

        self._cm = get_telethon_client_context(account=self.account)
        self.client = await self._cm.__aenter__()
        me = await self.client.get_me()
        logger.info(f"Connected as {me.first_name} (@{me.username}), testing @{self.bot_username}")

    async def disconnect(self):
        if self._cm:
            await self._cm.__aexit__(None, None, None)
            self._cm = None
            self.client = None

    async def send_and_wait(self, text: str, timeout: Optional[float] = None) -> Message:
        """Send a message to the bot and wait for a reply."""
        assert self.client is not None, "Not connected — use 'async with BotTester(...)'"
        timeout = timeout or self.timeout
        sent_at = datetime.now(timezone.utc).replace(microsecond=0)

        await self.client.send_message(self.bot_username, text)
        logger.debug(f"Sent: {text}")

        # Poll for response
        await asyncio.sleep(0.5)
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            messages = await self.client.get_messages(self.bot_username, limit=5)
            for msg in messages:
                if not msg.out and msg.date >= sent_at:
                    logger.debug(f"Got: {msg.text[:100] if msg.text else '<no text>'}...")
                    return msg
            await asyncio.sleep(0.5)

        raise TimeoutError(f"No response from @{self.bot_username} within {timeout}s")

    async def click_button(self, message: Message, button_text: str) -> None:
        """Click an inline button on a message by matching button text."""
        assert self.client is not None
        if not message.reply_markup:
            raise ValueError("Message has no inline keyboard")

        for row in message.reply_markup.rows:
            for button in row.buttons:
                if isinstance(button, KeyboardButtonCallback) and button_text in button.text:
                    await message.click(data=button.data)
                    logger.debug(f"Clicked: {button.text}")
                    return

        available = [b.text for row in message.reply_markup.rows for b in row.buttons]
        raise ValueError(f"Button '{button_text}' not found. Available: {available}")

    async def get_latest_message(self) -> Message:
        """Get the most recent message from the bot."""
        assert self.client is not None
        messages = await self.client.get_messages(self.bot_username, limit=5)
        for msg in messages:
            if not msg.out:
                return msg
        raise ValueError("No bot messages found")

    async def get_edited_message(self, original: Message, timeout: Optional[float] = None) -> Message:
        """Wait for a message to be edited (e.g. after inline button click)."""
        assert self.client is not None
        timeout = timeout or self.timeout
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            messages = await self.client.get_messages(self.bot_username, ids=original.id)
            if messages and messages[0].edit_date and messages[0].edit_date > (original.edit_date or original.date):
                return messages[0]
            await asyncio.sleep(0.5)

        raise TimeoutError(f"Message {original.id} was not edited within {timeout}s")
