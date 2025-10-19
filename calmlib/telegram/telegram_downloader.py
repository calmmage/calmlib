from loguru import logger
from telethon import TelegramClient
from telethon.tl.custom.dialog import Dialog
from tqdm.asyncio import tqdm

from calmlib.telegram.telegram_cache import TelegramCache
from calmlib.utils import Singleton
from calmlib.utils.env_discovery import find_calmmage_env_key


class TelegramDownloader(metaclass=Singleton):
    """
    Telegram downloader for synchronizing all chats with local cache.

    Features:
    - Smart incremental updates (only downloads chats with new messages)
    - Progress tracking with tqdm
    - Leverages existing TelegramCache infrastructure
    """

    def __init__(
        self,
        cache: TelegramCache | None = None,
        telethon_client: TelegramClient | None = None,
        telethon_account: str = "secondary",
        mongo_conn_str: str | None = None,
        db_name: str | None = None,
    ):
        if cache is None:
            if mongo_conn_str is None:
                mongo_conn_str = find_calmmage_env_key(
                    "CALMMAGE_TELEGRAM_CACHE_MONGO_CONN_STR",
                    default="mongodb://localhost:27017",
                )
            if db_name is None:
                db_name = find_calmmage_env_key(
                    "CALMMAGE_TELEGRAM_CACHE_MONGO_DB_NAME", default="telegram_cache"
                )

            cache = TelegramCache(
                telethon_client=telethon_client,
                telethon_account=telethon_account,
                mongo_conn_str=mongo_conn_str,
                db_name=db_name,
            )

        self.cache = cache

    async def get_telethon_client(self) -> TelegramClient:
        """Get the Telethon client instance."""
        return await self.cache.get_telethon_client()

    async def get_outdated_chats(self) -> list[tuple[Dialog, str]]:
        """
        Get list of chats that need updating.

        Returns:
            List of tuples (dialog, reason) where reason explains why it needs updating
        """
        logger.info("Checking for outdated chats...")

        # Get all dialogs
        dialogs = await self.cache.get_raw_dialogs()

        outdated_chats = []

        for dialog in dialogs:
            chat_id = dialog.entity.id
            dialog_date = dialog.date

            if dialog_date is None:
                continue

            # Check if we have any cached messages for this chat
            has_cache = await self.cache._has_cached_messages(chat_id)

            if not has_cache:
                outdated_chats.append((dialog, "No cached messages"))
                continue

            # Get the latest cached message timestamp
            if self.cache.mongo_enabled:
                try:
                    min_date, max_date, count = await self.cache._get_message_range(
                        chat_id
                    )
                    if max_date is None:
                        outdated_chats.append((dialog, "Empty cache"))
                        continue
                    latest_cached_date = max_date
                except Exception as e:
                    logger.debug(f"Error getting message range for chat {chat_id}: {e}")
                    outdated_chats.append((dialog, "Cache error"))
                    continue
            else:
                # JSON not implemented - mark all chats as needing update
                outdated_chats.append((dialog, "JSON storage - always update"))
                continue

            # Compare with dialog date
            if dialog_date > latest_cached_date:
                time_diff = dialog_date - latest_cached_date
                outdated_chats.append((dialog, f"Behind by {time_diff}"))

        logger.info(
            f"Found {len(outdated_chats)} outdated chats out of {len(dialogs)} total"
        )
        return outdated_chats

    async def download_chat(
        self, chat_id: int, limit: int | None = None, **kwargs
    ) -> int:
        """
        Download/update messages for a single chat.

        Args:
            chat_id: ID of the chat to update
            limit: Maximum number of messages to fetch
            **kwargs: Additional arguments passed to get_raw_messages

        Returns:
            Number of new messages downloaded
        """
        logger.debug(f"Downloading chat {chat_id}...")

        # Get current message count if using MongoDB
        initial_count = 0
        if self.cache.mongo_enabled:
            try:
                _, _, initial_count = await self.cache._get_message_range(chat_id)
            except Exception:
                initial_count = 0  # Fallback if error

        # Trigger message download (this will handle incremental updates automatically)
        messages = await self.cache.get_raw_messages(chat_id, limit=limit, **kwargs)

        # Calculate new messages downloaded
        if self.cache.mongo_enabled:
            try:
                _, _, final_count = await self.cache._get_message_range(chat_id)
                new_messages = final_count - initial_count
            except Exception:
                new_messages = 0  # Can't determine new vs existing
        else:
            # For JSON files, we can't easily determine new vs existing
            new_messages = len(messages)

        logger.debug(f"Downloaded {new_messages} new messages for chat {chat_id}")
        return new_messages

    async def download_all_chats(
        self,
        limit_per_chat: int | None = None,
        only_outdated: bool = True,
        chat_filters: dict | None = None,
        **kwargs,
    ) -> dict:
        """
        Download/update messages for all chats with progress tracking.

        Args:
            limit_per_chat: Maximum messages per chat (None = all)
            only_outdated: If True, only update chats that need it
            chat_filters: Filters to apply (min_users, max_users, is_owned, etc.)
            **kwargs: Additional arguments passed to download_chat

        Returns:
            Dictionary with download statistics
        """
        logger.info("Starting bulk chat download...")

        # Get list of chats to download
        if only_outdated:
            outdated_info = await self.get_outdated_chats()
            dialogs_to_process = [dialog for dialog, reason in outdated_info]
            logger.info(f"Processing {len(dialogs_to_process)} outdated chats")
        else:
            dialogs_to_process = await self.cache.get_raw_dialogs()
            logger.info(f"Processing all {len(dialogs_to_process)} chats")

        # Apply chat filters if provided
        if chat_filters:
            filtered_dialogs = []
            for dialog in dialogs_to_process:
                entity = dialog.entity

                # Apply min_users filter
                if chat_filters.get("min_users"):
                    participants = getattr(entity, "participants_count", None)
                    if participants is None or participants < chat_filters["min_users"]:
                        continue

                # Apply max_users filter
                if chat_filters.get("max_users"):
                    participants = getattr(entity, "participants_count", None)
                    if (
                        participants is not None
                        and participants > chat_filters["max_users"]
                    ):
                        continue

                # Apply is_owned filter
                if chat_filters.get("is_owned") is not None:
                    creator = getattr(entity, "creator", False)
                    if chat_filters["is_owned"] != creator:
                        continue

                filtered_dialogs.append(dialog)

            dialogs_to_process = filtered_dialogs
            logger.info(f"After filtering: {len(dialogs_to_process)} chats to process")

        # Download with progress tracking
        stats = {
            "total_chats": len(dialogs_to_process),
            "processed_chats": 0,
            "total_new_messages": 0,
            "errors": 0,
            "skipped": 0,
        }

        if not dialogs_to_process:
            logger.info("No chats to process")
            return stats

        progress_bar = tqdm(dialogs_to_process, desc="Downloading chats", unit="chat")

        for dialog in progress_bar:
            chat_id = dialog.entity.id
            chat_title = getattr(
                dialog.entity,
                "title",
                getattr(dialog.entity, "first_name", f"Chat {chat_id}"),
            )

            try:
                progress_bar.set_description(f"Downloading: {chat_title[:30]}")

                new_messages = await self.download_chat(
                    chat_id, limit=limit_per_chat, **kwargs
                )

                stats["total_new_messages"] += new_messages
                stats["processed_chats"] += 1

                if new_messages == 0:
                    stats["skipped"] += 1

            except Exception as e:
                logger.error(f"Error downloading chat {chat_id} ({chat_title}): {e}")
                stats["errors"] += 1
                continue

        progress_bar.close()

        logger.info(
            f"Download complete! Processed {stats['processed_chats']} chats, "
            f"{stats['total_new_messages']} new messages, "
            f"{stats['errors']} errors, {stats['skipped']} already up-to-date"
        )

        return stats

    async def sync_all(self, **kwargs) -> dict:
        """
        Convenience method to sync all chats (alias for download_all_chats).

        Args:
            **kwargs: Arguments passed to download_all_chats

        Returns:
            Download statistics dictionary
        """
        return await self.download_all_chats(**kwargs)
