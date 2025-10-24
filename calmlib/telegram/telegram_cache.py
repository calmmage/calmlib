import datetime
import json
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field
from pymongo import AsyncMongoClient
from telethon import TelegramClient
from telethon.helpers import TotalList
from telethon.tl import types as tl_types
from telethon.tl.custom.dialog import Dialog
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.patched import Message
from telethon.tl.types import Channel, Chat, User
from telethon.tl.types.messages import DialogFilters
from telethon.types import ChatForbidden
from tqdm.asyncio import tqdm


class MessageTitle(BaseModel):
    """Schema for AI-generated message title"""
    title: str = Field(..., description="A short, concise title (max 10 words) summarizing the message content")

from calmlib.telegram.chat_utils import (
    chat_is_bot,
    chat_is_channel,
    chat_is_group,
    chat_is_private,
)
from calmlib.telegram.models import (
    CHAT_ENTITY_CLASSES,
    TelegramBotChat,
    TelegramChannel,
    TelegramChat,
    TelegramFolder,
    TelegramGroupChat,
    TelegramMessage,
    TelegramUserChat,
)
from calmlib.telegram.telethon_client import get_telethon_client
from calmlib.telegram.utils import get_chat_id
from calmlib.utils import Singleton, cleanup_none, dict_to_namespace
from calmlib.utils.env_discovery import find_calmmage_env_key

# Threshold for switching from individual message checks to loading all dialogs
NEWEST_MESSAGE_CHECK_THRESHOLD = 5


class TelegramCache(metaclass=Singleton):
    def __init__(
        self,
        root_path: Path | None = None,
        telethon_client: TelegramClient | None = None,
        telethon_account: str = "secondary",
        mongo_conn_str: str | None = None,
        db_name: str | None = None,
        mongo_enabled: bool | None = None,
    ):
        self._root_path = root_path
        if mongo_conn_str is None:
            mongo_conn_str = find_calmmage_env_key(
                "CALMMAGE_TELEGRAM_CACHE_MONGO_CONN_STR",
                default="mongodb://localhost:27017",
            )
        if db_name is None:
            db_name = find_calmmage_env_key(
                "CALMMAGE_TELEGRAM_CACHE_MONGO_DB_NAME", default="telegram_cache"
            )

        self._telethon_client = telethon_client
        self.telethon_account = telethon_account
        self.mongo_conn_str = mongo_conn_str
        self.db_name = db_name
        self._dialogs = None
        self._user_id = None  # Cache user ID for collection naming
        self._indexes_ensured = False  # Track if indexes have been created
        self._messages_collection = None  # Cached collection instance
        self._migration_map = None  # {new_channel_id: old_chat_id}
        self._migrated_chat_ids = None  # Set of old chat IDs to filter out
        self._newest_message_call_count = 0  # Track usage of _get_newest_message_date
        self._entity_cache: dict[
            int, User | Chat | Channel
        ] = {}  # Cache for entities by ID

        # MongoDB configuration
        if mongo_enabled is None:
            # Default: check env var, fallback to True
            mongo_enabled = find_calmmage_env_key(
                "CALMMAGE_TELEGRAM_CACHE_MONGO_ENABLED", default="true"
            ).lower() in ("true", "1", "yes")
        self.mongo_enabled = mongo_enabled

        # tqdm configuration
        self.enable_tqdm = find_calmmage_env_key(
            "CALMMAGE_VERBOSE", default="true"
        ).lower() in ("true", "1", "yes")

        if root_path is not None:
            root_path.mkdir(parents=True, exist_ok=True)

    @property
    def root_path(self):
        if self._root_path is None:
            raise ValueError("root_path is not initialized")
        return self._root_path

    async def init_root_path(self, client=None):
        if client is None:
            client = await self.get_telethon_client()
        if self._root_path is None:
            from src.utils import get_data_dir

            me = await client.get_me()
            assert me is not None
            assert isinstance(me, User)
            user_id = me.id
            self._root_path = get_data_dir() / "telegram" / str(user_id)
            self._root_path.mkdir(parents=True, exist_ok=True)

    @property
    def mongo_client(self):
        if not hasattr(self, "_mongo_client"):
            self._mongo_client = AsyncMongoClient(self.mongo_conn_str)
        return self._mongo_client

    @property
    def db(self):
        return self.mongo_client[self.db_name]

    async def init_messages_collection(self):
        """Initialize messages collection with user ID in name"""
        if self._messages_collection is not None:
            return

        if self._user_id is None:
            client = await self.get_telethon_client()
            me = await client.get_me()
            assert me is not None
            assert isinstance(me, User)
            self._user_id = me.id

        self._messages_collection = self.db[f"messages_user_{self._user_id}"]

        # Ensure indexes are created once
        if self.mongo_enabled and not self._indexes_ensured:
            await self._ensure_indexes()
            self._indexes_ensured = True

    @property
    def messages_collection(self):
        """Get messages collection (must call init_messages_collection first)"""
        if self._messages_collection is None:
            raise RuntimeError(
                "messages_collection not initialized. Call init_messages_collection() first."
            )
        return self._messages_collection

    async def _ensure_indexes(self):
        """Create indexes for optimal performance"""
        if not self.mongo_enabled:
            return

        # Composite index for chat queries
        await self.messages_collection.create_index(
            [("chat_id", 1), ("date", -1)], background=True
        )

        # Index for date-based queries
        await self.messages_collection.create_index("date", background=True)

        logger.debug("MongoDB indexes ensured")

    @property
    def telethon_client(self) -> TelegramClient:
        if self._telethon_client is None:
            raise RuntimeError(
                "telethon_client not initialized. Call init_telethon_client() first."
            )
        return self._telethon_client

    async def init_telethon_client(self) -> None:
        if self._telethon_client is None:
            self._telethon_client = await get_telethon_client(self.telethon_account)
            await self.init_root_path(self._telethon_client)

    async def get_telethon_client(self) -> TelegramClient:
        await self.init_telethon_client()
        assert self._telethon_client is not None
        return self._telethon_client

    async def close(self):
        """Close and cleanup resources, especially the telethon client."""
        if self._telethon_client is not None and self._telethon_client.is_connected():
            logger.debug("Disconnecting telethon client")
            await self._telethon_client.disconnect()
            self._telethon_client = None

    async def __aenter__(self):
        """Async context manager entry - initialize the cache."""
        await self.init_telethon_client()
        await self.init_messages_collection()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources."""
        await self.close()
        return False  # Don't suppress exceptions

    async def _get_chat_id(self, source: int | str):
        if isinstance(source, int):
            return source
        else:
            username = source
            client = await self.get_telethon_client()
            logger.debug("Calling Telethon Client without cache - get_chat_id")
            return await get_chat_id(username, client)

    # -----------------------------------------------------------------------------
    # region Dialog Filters - Raw Folders
    # -----------------------------------------------------------------------------

    async def _get_raw_dialog_filters(self) -> DialogFilters:
        """Get all folders (dialog filters) from Telegram API."""
        client = await self.get_telethon_client()

        logger.debug("Calling Telethon Client without cache - get dialog filters")
        filters = await client(GetDialogFiltersRequest())
        assert filters is not None
        assert isinstance(filters, DialogFilters)
        logger.debug(
            f"Downloaded {len(filters.filters)} dialog filters from Telegram API"
        )

        self._save_raw_dialog_filters(filters)

        return filters

    @property
    def dialog_filters_path(self):
        return self.root_path / "dialog_filters.json"

    def _save_raw_dialog_filters(self, filters: DialogFilters, output_path=None):
        """Save raw folder data to JSON file."""

        if output_path is None:
            output_path = self.dialog_filters_path

        output_file = Path(output_path)
        with open(output_file, "w", encoding="utf-8") as f:
            filters_json = filters.to_json()
            assert filters_json is not None
            filters_data = json.loads(filters_json)
            cleanup_none(filters_data, none_entities=(None, "", [], {}, False))
            f.write(json.dumps(filters_data, indent=2, ensure_ascii=False))

        logger.debug(f"Saved dialog filters to {output_file}")

    def _load_raw_dialog_filters(self, input_path: Path | None = None) -> DialogFilters:
        """Load raw folders data from JSON file."""

        if input_path is None:
            input_path = self.dialog_filters_path

        filters_json = input_path.read_text()
        filters_data = json.loads(filters_json)

        type_name = filters_data.pop("_")
        assert type_name == "DialogFilters"

        filters = DialogFilters(**filters_data)
        logger.debug(f"Loaded {len(filters.filters)} DialogFilters from cache")

        return filters

    async def get_raw_dialog_filters(self, invalidate_cache=False):
        """Get raw folders with caching."""
        await self.init_root_path()

        if invalidate_cache or not self.dialog_filters_path.exists():
            logger.debug("Cache miss or invalidated - fetching dialog filters from API")
            filters = await self._get_raw_dialog_filters()
            return filters
        else:
            logger.debug("Loading dialog filters from cache file")
            return self._load_raw_dialog_filters()

    # -----------------------------------------------------------------------------
    # endregion Dialog Filters - Raw Folders
    # -----------------------------------------------------------------------------

    # -----------------------------------------------------------------------------
    # region Dialogs - Raw Chats
    # -----------------------------------------------------------------------------

    # 3) get chats
    async def get_raw_dialogs(self, invalidate_cache: bool = False) -> list[Dialog]:
        """Get all dialogs/chats with caching support."""
        if invalidate_cache:
            self._dialogs = None

        await self.init_dialogs()
        return list(self.dialogs.values())

    async def _get_dialog_entities(self):
        dialogs = await self.get_raw_dialogs()
        entities = [dialog.entity for dialog in dialogs]
        self._save_dialog_entities(entities)
        return entities

    @property
    def dialog_entities_path(self):
        return self.root_path / "dialog_entities.json"

    def _save_dialog_entities(self, entities: list, output_path: Path | None = None):
        """Save raw chat data to JSON file."""

        if output_path is None:
            output_path = self.dialog_entities_path

        result = []
        for entity in entities:
            entity_json = entity.to_json()
            assert entity_json is not None
            entity_data = json.loads(entity_json)
            cleanup_none(entity_data, none_entities=(None, "", [], {}, False))
            result.append(entity_data)

        json.dump(
            result,
            output_path.open("w", encoding="utf-8"),
            indent=2,
            ensure_ascii=False,
        )
        logger.debug(f"Saved {len(entities)} dialogs to {output_path}")

    def _load_dialog_entities(self, input_path=None):
        """Load raw chat data from JSON file."""
        if input_path is None:
            input_path = self.dialog_entities_path

        entity_dicts = json.load(input_path.open("r"))
        entities = []
        for entity_data in entity_dicts:
            class_name = entity_data.pop("_")
            assert class_name in CHAT_ENTITY_CLASSES

            # Convert nested dicts to namespace objects for dot access
            converted_data = dict_to_namespace(entity_data)

            # Create the proper external class but use converted_data.__dict__ for initialization
            try:
                entity = CHAT_ENTITY_CLASSES[class_name](**converted_data.__dict__)
                # Store the namespace version for migration access
                entity._namespace_data = converted_data
            except Exception:
                logger.error(
                    f"Failed to parse entity {class_name}: {json.dumps(entity_data, indent=2, ensure_ascii=False)}"
                )
                # Fallback: create a namespace object with the class info
                entity = converted_data
            entities.append(entity)

        logger.debug(f"Loaded {len(entities)} dialog entities from {input_path}")
        return entities

    async def get_raw_dialog_entities(self, invalidate_cache=False):
        """Get chats with caching."""
        await self.init_root_path()

        if invalidate_cache or not self.dialog_entities_path.exists():
            entities = await self._get_dialog_entities()
            return entities
        else:
            return self._load_dialog_entities()

    # @lru_cache()
    # async def get_dialogs_cached(self) -> list[Dialog]:
    #     return await self._fetch_raw_dialogs_from_api()

    @property
    def dialogs(self) -> dict[int, Dialog]:
        if self._dialogs is None:
            raise RuntimeError("dialogs not initialized. Call init_dialogs() first.")
        return self._dialogs

    async def init_dialogs(self):
        if self._dialogs is None:
            client = await self.get_telethon_client()
            logger.debug("Calling Telethon Client without cache - get dialogs")
            dialogs = await client.get_dialogs()
            self._dialogs = {d.entity.id: d for d in dialogs}
            await self._get_dialog_entities()

    async def init_migration_map(
        self, entities: list[Chat | Channel | User] | None = None
    ):
        """Initialize migration mapping from entities with migrated_to attribute."""
        if self._migration_map is not None:
            return

        if entities is None:
            entities = await self.get_raw_dialog_entities()
        self._migration_map = {}
        self._migrated_chat_ids = set()

        for entity in entities:
            migrated_to = getattr(entity, "migrated_to", None)
            if migrated_to and hasattr(migrated_to, "channel_id"):
                old_id = entity.id
                new_id = migrated_to.channel_id
                self._migration_map[new_id] = old_id
                self._migrated_chat_ids.add(old_id)
                # logger.debug(f"Found migration: chat {old_id} -> channel {new_id}")

        logger.debug(
            f"Initialized migration map with {len(self._migration_map)} migrations"
        )

    # -----------------------------------------------------------------------------
    # endregion Dialogs - Raw Chats
    # -----------------------------------------------------------------------------

    # -----------------------------------------------------------------------------
    # region Raw Messages
    # -----------------------------------------------------------------------------

    async def _get_chat_name(self, chat_id: int):
        await self.init_dialogs()
        if chat_id not in self.dialogs:
            return None
        dialog = self.dialogs[chat_id]
        entity = dialog.entity
        try:
            return entity.title
        except AttributeError:
            pass
        try:
            if entity.first_name and entity.last_name:
                return entity.first_name + " " + entity.last_name
            elif entity.first_name:
                return entity.first_name
            elif entity.last_name:
                return entity.last_name
        except AttributeError:
            pass

    async def _get_raw_messages(
        self,
        chat_id: int,
        limit: int | None = None,
        offset: int | None = None,
        offset_date: datetime.datetime | None = None,
        min_date: datetime.datetime | None = None,
        enable_tqdm: bool | None = None,
        total: int | None = None,
        **kwargs,
    ):
        logger.debug(
            f"Fetching messages from Telegram API for chat {chat_id}, limit={limit}, offset={offset}, offset_date={offset_date}, min_date={min_date}, kwargs={kwargs}"
        )

        # Warn about unexpected parameter combinations
        if offset_date is not None and offset is not None:
            logger.warning(
                f"UNEXPECTED: Both offset_date ({offset_date}) and numeric offset ({offset}) specified for chat {chat_id}. "
                "This is likely a bug - date-based and numeric offsets should not be mixed."
            )

        client = await self.get_telethon_client()

        # Get chat name for progress bar
        chat_name = await self._get_chat_name(chat_id)
        if chat_name is None:
            chat_name = "Chat"
        chat_name = f"{chat_name} [{chat_id}]"

        # Determine if tqdm should be disabled
        use_tqdm = enable_tqdm if enable_tqdm is not None else self.enable_tqdm

        messages = []
        if offset is not None:
            kwargs["add_offset"] = offset

        # Explicitly pass offset_date to Telegram API if provided
        if offset_date is not None:
            kwargs["offset_date"] = offset_date

        if total is None:
            if limit is None:
                try:
                    total = (await client.get_messages(chat_id)).total
                except:
                    total = None
            else:
                total = limit

        desc = f"Fetching messages from {chat_name}"
        logger.debug("Calling Telethon Client without cache - iter messages")
        async for m in tqdm(
            client.iter_messages(chat_id, limit=limit, **kwargs),
            desc=desc,
            total=total,
            disable=not use_tqdm,
        ):
            # Stop early if we've gone past min_date
            if min_date and m.date < min_date:
                logger.debug(f"Hit min_date ({min_date}), stopping iteration at message date {m.date}")
                break
            messages.append(m)

        logger.debug(
            f"Fetched {len(messages)} messages from Telegram API for chat {chat_id}"
        )
        await self._save_raw_messages(chat_id=chat_id, messages=messages)

        return messages

    async def _save_messages_to_mongo(self, chat_id: int, messages: list):
        await self.init_messages_collection()
        if not messages:
            return

        docs = []
        for m in messages:
            message_data = json.loads(m.to_json())
            cleanup_none(message_data, none_entities=(None, [], {}, False, ""))
            message_data["chat_id"] = chat_id
            message_data["_id"] = f"{chat_id}_{message_data['id']}"  # Composite key
            docs.append(message_data)

        # Bulk upsert for deduplication
        from pymongo import UpdateOne

        operations = [
            UpdateOne({"_id": doc["_id"]}, {"$set": doc}, upsert=True) for doc in docs
        ]

        if operations:
            result = await self.messages_collection.bulk_write(
                operations, ordered=False
            )
            logger.debug(
                f"Saved {result.upserted_count} new, {result.modified_count} updated messages"
            )

    # todo: update args and kwargs to actual parameter names
    async def _save_raw_messages(self, *args, **kwargs):
        if self.mongo_enabled:
            await self._save_messages_to_mongo(*args, **kwargs)
        else:
            await self._save_messages_to_json(*args, **kwargs)

    async def _save_messages_to_json(
        self, chat_id: int, messages: list, output_path=None
    ):
        # todo: rework to mongo
        # for now, save to disk.
        if output_path is None:
            output_path = self._get_messages_json_path(chat_id)

        logger.debug(f"Saving {len(messages)} messages to {output_path}")
        data = []
        for m in messages:
            message_json = m.to_json()
            message_data = json.loads(message_json)
            cleanup_none(message_data, none_entities=(None, [], {}, False, ""))
            data.append(message_data)

        if output_path.exists():
            # load existing data
            existing_data = json.load(output_path.open("r"))
            logger.debug(f"Found {len(existing_data)} existing messages in cache file")
            data += existing_data
            data = self._deduplicate_messages_dicts(data)
            logger.debug(f"After deduplication: {len(data)} messages")
            data = sorted(data, key=lambda x: x["date"], reverse=True)

        json.dump(
            data, output_path.open("w", encoding="utf-8"), indent=2, ensure_ascii=False
        )
        logger.debug(f"Saved {len(data)} messages to {output_path}")

    @staticmethod
    def extract_dialog_id(data: dict) -> int:
        if "channel_id" in data:
            return data.get("channel_id")
        elif "chat_id" in data:
            # todo: check if this code path is ever executed
            return data.get("chat_id")
        elif "user_id" in data:
            return data.get("user_id")
        else:
            raise ValueError(f"Unknown peer_id structure: {data}")

    @staticmethod
    def reconstruct_tl_object(data):
        """
        Recursively reconstruct Telethon TL objects from dict/list structures.

        Handles nested dicts that contain a "_" type field indicating the Telethon class.
        """
        # Base cases
        if not isinstance(data, (dict, list)):
            return data

        # Handle lists
        if isinstance(data, list):
            return [TelegramCache.reconstruct_tl_object(item) for item in data]

        # Handle dicts
        if not isinstance(data, dict):
            return data

        # If no "_" field, it's just a regular dict - recurse on values
        if "_" not in data:
            return {k: TelegramCache.reconstruct_tl_object(v) for k, v in data.items()}

        # Extract type and create TL object
        type_name = data.pop("_")

        # Recursively reconstruct nested objects
        reconstructed_data = {}
        for key, value in data.items():
            reconstructed_data[key] = TelegramCache.reconstruct_tl_object(value)

        # Try to get the Telethon class and instantiate it
        try:
            tl_class = getattr(tl_types, type_name, None)
            if tl_class is None:
                # Put the "_" back and return the dict
                reconstructed_data["_"] = type_name
                return reconstructed_data
            return tl_class(**reconstructed_data)
        except Exception as e:
            logger.debug(f"Failed to reconstruct {type_name}: {e}, returning as dict")
            reconstructed_data["_"] = type_name
            return reconstructed_data

    async def _load_messages_from_mongo(
        self,
        chat_id: int,
        limit: int | None = None,
        offset: int | None = None,
        min_date: datetime.datetime | None = None,
        max_date: datetime.datetime | None = None,
    ) -> list[Message]:
        await self.init_messages_collection()
        query: dict[str, Any] = {"chat_id": chat_id}

        if min_date or max_date:
            query["date"] = {}
            if min_date:
                # Convert datetime to ISO string for MongoDB query (dates are stored as strings)
                query["date"]["$gte"] = min_date.isoformat()
            if max_date:
                # Convert datetime to ISO string for MongoDB query (dates are stored as strings)
                query["date"]["$lte"] = max_date.isoformat()

        cursor = self.messages_collection.find(query).sort("date", -1)

        if offset:
            cursor = cursor.skip(offset)
        if limit:
            cursor = cursor.limit(limit)

        messages = []
        async for doc in cursor:
            doc: dict
            doc.pop("_id")
            doc.pop("chat_id", None)
            doc.pop("_")  # message_type

            # Convert nested structures
            if "from_id" in doc and isinstance(doc["from_id"], dict):
                doc["from_id"] = self.extract_dialog_id(doc["from_id"])
            if "peer_id" in doc and isinstance(doc["peer_id"], dict):
                doc["peer_id"] = self.extract_dialog_id(doc["peer_id"])
            if "date" in doc and isinstance(doc["date"], str):
                doc["date"] = datetime.datetime.fromisoformat(doc["date"])

            # Reconstruct TL objects from nested dicts
            if "reactions" in doc and isinstance(doc["reactions"], dict):
                doc["reactions"] = self.reconstruct_tl_object(doc["reactions"])
            if "fwd_from" in doc and isinstance(doc["fwd_from"], dict):
                doc["fwd_from"] = self.reconstruct_tl_object(doc["fwd_from"])

            try:
                message = Message(**doc)
            except:
                logger.error(f"Failed to parse message {doc.get('id')}: {doc}")
                raise
            messages.append(message)

        logger.debug(f"Loaded {len(messages)} messages from MongoDB for chat {chat_id}")
        return messages

    # todo: update args and kwargs to actual parameter names
    async def _load_raw_messages(self, *args, **kwargs):
        if self.mongo_enabled:
            return await self._load_messages_from_mongo(*args, **kwargs)
        else:
            return await self._load_messages_to_json(*args, **kwargs)

    # todo: add same parameters as mongo
    def _get_messages_json_path(self, chat_id):
        return self.root_path / f"messages_{chat_id}.json"

    async def _load_messages_to_json(
        self, chat_id: int, input_path=None
    ) -> list[Message]:
        if input_path is None:
            input_path = self._get_messages_json_path(chat_id)

        logger.debug(f"Loading messages from cache file {input_path}")
        data = json.load(input_path.open("r"))
        logger.debug(f"Loaded {len(data)} message records from cache file")

        messages = []
        for message_data in data:
            message_type = message_data.pop("_")
            if "from_id" in message_data:
                message_data["from_id"] = message_data["from_id"]["user_id"]
            if "date" in message_data:
                message_data["date"] = datetime.datetime.fromisoformat(
                    message_data["date"]
                )
            assert message_type == "Message"
            message = Message(**message_data)
            messages.append(message)

        logger.debug(f"Parsed {len(messages)} messages from cache")
        return messages

    async def _get_message_range(
        self, chat_id: int
    ) -> tuple[datetime.datetime | None, datetime.datetime | None, int]:
        """Get min/max timestamps and count for a chat"""
        if not self.mongo_enabled:
            raise NotImplementedError(
                "_get_message_range is only implemented for MongoDB. JSON storage not supported."
            )

        pipeline = [
            {"$match": {"chat_id": chat_id}},
            {
                "$group": {
                    "_id": None,
                    "min_date": {"$min": "$date"},
                    "max_date": {"$max": "$date"},
                    "count": {"$sum": 1},
                }
            },
        ]
        # todo list(self.messages_collection.aggregate()) - should be async for or await ... to_list()
        aggregate = await self.messages_collection.aggregate(pipeline)
        result = await aggregate.to_list(length=None)
        if result:
            min_date = result[0]["min_date"]
            max_date = result[0]["max_date"]
            count = result[0]["count"]

            # Convert string dates to datetime objects if needed
            if isinstance(min_date, str):
                min_date = datetime.datetime.fromisoformat(
                    min_date.replace("Z", "+00:00")
                )
            if isinstance(max_date, str):
                max_date = datetime.datetime.fromisoformat(
                    max_date.replace("Z", "+00:00")
                )

            return min_date, max_date, count
        return None, None, 0

    async def _get_newest_message_date(self, chat_id: int) -> datetime.datetime | None:
        """Get the newest message date for a chat, with smart switching to dialogs when heavily used."""
        # If dialogs are already loaded, use them (fast lookup)
        if self._dialogs is not None:
            if chat_id in self.dialogs:
                dialog = self.dialogs[chat_id]
                return dialog.date
            else:
                logger.warning(f"Chat {chat_id} not found in loaded dialogs")

        # Increment usage counter
        self._newest_message_call_count += 1

        # If we've called this method too many times, switch to loading all dialogs
        if self._newest_message_call_count >= NEWEST_MESSAGE_CHECK_THRESHOLD:
            logger.debug(
                f"Usage threshold ({NEWEST_MESSAGE_CHECK_THRESHOLD}) reached, loading all dialogs for efficiency"
            )
            await self.init_dialogs()
            # Now use the loaded dialogs
            if chat_id in self.dialogs:
                dialog = self.dialogs[chat_id]
                return dialog.date
            else:
                logger.warning(f"Chat {chat_id} not found in loaded dialogs")

        # If dialogs not loaded and under threshold, get newest message directly (single API call)
        try:
            client = await self.get_telethon_client()
            logger.debug(
                f"Calling Telethon Client without cache - get newest message for chat {chat_id} (call #{self._newest_message_call_count})"
            )
            async for message in client.iter_messages(chat_id, limit=1):
                return message.date
            # No messages found
            return None
        except Exception as e:
            logger.warning(f"Failed to get newest message for chat {chat_id}: {e}")
            return None

    async def _load_newer_messages(
        self, chat_id: int, messages: list[Message]
    ) -> list[Message]:
        if self.mongo_enabled:
            # Use MongoDB aggregation for efficient checking
            min_date, max_date, count = await self._get_message_range(chat_id)

            if not max_date:
                return messages

            # Check for latest message date
            dialog_date = await self._get_newest_message_date(chat_id)
            if dialog_date is None:
                logger.debug(f"No messages found for chat {chat_id}")
                return messages

            if dialog_date <= max_date:
                logger.debug(f"No new messages for chat {chat_id}")
                return messages

            # Fetch only new messages
            new_messages = await self._get_raw_messages(
                chat_id, offset_date=max_date, reverse=True
            )

            logger.debug(
                f"Fetched {len(new_messages)} newer messages for chat {chat_id}"
            )
            return messages  # MongoDB handles dedup automatically
        else:
            # Original logic for JSON files
            if len(messages) == 0:
                logger.debug(
                    f"No cached messages for chat {chat_id}, skipping newer messages check"
                )
                return messages

            latest_message_timestamp = messages[0].date
            logger.debug(
                f"Latest cached message timestamp for chat {chat_id}: {latest_message_timestamp}"
            )

            # look at timestamp of the newest message
            dialog_timestamp = await self._get_newest_message_date(chat_id)
            logger.debug(f"Dialog timestamp for chat {chat_id}: {dialog_timestamp}")
            if dialog_timestamp is None:
                logger.debug(f"No messages found for chat {chat_id}")
                return messages

            assert latest_message_timestamp is not None
            if latest_message_timestamp < dialog_timestamp:
                logger.debug(
                    f"Found newer messages in dialog for chat {chat_id}, fetching messages after {latest_message_timestamp}"
                )
                new_messages = await self._get_raw_messages(
                    chat_id,
                    reverse=True,
                    offset_date=latest_message_timestamp,
                )
                logger.debug(
                    f"Fetched {len(new_messages)} newer messages for chat {chat_id}"
                )
                messages = list(reversed(new_messages)) + messages
            else:
                logger.debug(f"No newer messages found for chat {chat_id}")

            return messages

    async def _has_older_messages_in_range(
        self, chat_id: int, min_date: datetime.datetime
    ) -> bool:
        """
        Check if we need to fetch older messages to satisfy min_date requirement.

        Returns True if:
        - MongoDB has no messages at all
        - Oldest cached message is newer than min_date (missing older messages)
        """
        min_date_mongo, max_date_mongo, count = await self._get_message_range(chat_id)

        if count == 0:
            logger.debug(f"No messages in MongoDB for chat {chat_id}")
            return True  # No messages cached - need to fetch

        # If oldest cached message is newer than min_date, we're missing older messages
        if min_date_mongo > min_date:
            logger.debug(
                f"MongoDB oldest message ({min_date_mongo}) is newer than min_date ({min_date}), need older messages"
            )
            return True

        logger.debug(
            f"MongoDB has messages back to {min_date_mongo}, covers min_date {min_date}"
        )
        return False

    async def _load_missing_messages(
        self,
        chat_id: int,
        messages: list[Message],
        limit: int | None = None,
        offset: int | None = None,
        min_date: datetime.datetime | None = None,
    ) -> list[Message]:
        logger.debug(
            f"Checking for missing messages for chat {chat_id}, current cached: {len(messages)}, requested limit: {limit}, offset: {offset}, min_date={min_date}"
        )

        # NEW: Smart range-based loading when min_date is specified
        if min_date is not None:
            # Check if we need to fetch older messages to satisfy min_date requirement
            if await self._has_older_messages_in_range(chat_id, min_date):
                # Get oldest cached message date to start iteration from there
                min_date_mongo, _, _ = await self._get_message_range(chat_id)

                logger.debug(
                    f"Fetching older messages from {min_date_mongo} back to {min_date}"
                )

                # Fetch older messages starting from oldest cached date, stopping at min_date
                older_messages = await self._get_raw_messages(
                    chat_id,
                    offset_date=min_date_mongo,  # Start from oldest cached DATE
                    min_date=min_date,            # Stop at min_date (early break)
                )
                logger.debug(
                    f"Loaded {len(older_messages)} older messages for chat {chat_id}"
                )
            else:
                logger.debug(
                    f"MongoDB already has messages back to {min_date}, no older messages needed"
                )

            # Messages already filtered by MongoDB query, no need to extend
            return messages

        # Original logic for non-date-filtered queries (full history sync)
        client: TelegramClient = await self.get_telethon_client()
        all_messages = await client.get_messages(chat_id)
        if isinstance(all_messages, Message):
            total_message_count = 1
        elif all_messages is None:
            total_message_count = 0
        else:
            assert isinstance(all_messages, TotalList)
            total_message_count = all_messages.total
        logger.debug(f"Total message count in chat {chat_id}: {total_message_count}")

        if offset is not None:
            total_message_count -= offset
            logger.debug(
                f"Adjusted total message count for offset {offset}: {total_message_count}"
            )
        else:
            offset = 0

        if limit is None:
            # count how many messages are in total
            limit = total_message_count
            logger.debug(f"No limit specified, using total message count: {limit}")
        else:
            limit = min(limit, total_message_count)
            logger.debug(
                f"Using limit: {limit} (min of requested {limit} and total {total_message_count})"
            )

        if len(messages) < limit:
            # need to load the rest of the messages
            offset += len(messages)
            limit -= len(messages)
            logger.debug(
                f"Need to load more messages. New target parameters: limit={limit}, offset={offset}"
            )

            # Use offset_date to start from oldest cached message if available
            min_date_mongo, _, count = await self._get_message_range(chat_id)
            older_messages = await self._get_raw_messages(
                chat_id,
                limit=limit,
                offset=offset,
                offset_date=min_date_mongo if count > 0 else None,  # Start from oldest cached DATE
            )
            logger.debug(
                f"Loaded {len(older_messages)} older messages for chat {chat_id}"
            )

            messages.extend(older_messages)
        else:
            logger.debug(f"No additional messages needed for chat {chat_id}")

        return messages

    # @staticmethod
    # def get_message_id(message):
    #     try:
    #         return message.id
    #     except AttributeError:
    #         return message["id"]

    def _deduplicate_messages(self, messages: list[Message]) -> list[Message]:
        # match by message id
        # keep the newest one
        logger.debug(f"Deduplicating {len(messages)} messages")
        message_ids = set()
        result = []
        duplicates_count = 0
        for m in messages:
            message_id = m.id
            if message_id in message_ids:
                duplicates_count += 1
                continue
            message_ids.add(message_id)
            result.append(m)
        logger.debug(
            f"Removed {duplicates_count} duplicate messages, {len(result)} unique messages remain"
        )
        return result

    def _deduplicate_messages_dicts(self, messages: list[dict]) -> list[dict]:
        # match by message id
        # keep the newest one
        logger.debug(f"Deduplicating {len(messages)} messages")
        message_ids = set()
        result = []
        duplicates_count = 0
        for m in messages:
            message_id = m["id"]
            if message_id in message_ids:
                duplicates_count += 1
                continue
            message_ids.add(message_id)
            result.append(m)
        logger.debug(
            f"Removed {duplicates_count} duplicate messages, {len(result)} unique messages remain"
        )
        return result

    async def _has_cached_messages(self, chat_id: int) -> bool:
        if self.mongo_enabled:
            await self.init_messages_collection()
            return (
                await self.messages_collection.find_one({"chat_id": chat_id})
                is not None
            )
        else:
            # for now - checks file on disk
            cache_file = self._get_messages_json_path(chat_id)
            has_cache = cache_file.exists()
            logger.debug(
                f"Cache file check for chat {chat_id}: {cache_file} exists={has_cache}"
            )
            return has_cache

    async def _get_messages_with_migration(
        self, chat_id: int, ignore_cache=False, limit=None, offset=None,
        min_date: datetime.datetime | None = None,
        max_date: datetime.datetime | None = None,
        **kwargs
    ) -> list[Message]:
        """
        Get messages for a chat, handling migrations by fetching from both old and new chats.

        If the chat was migrated, this will fetch messages from both the old chat ID
        and the new channel ID, then merge and deduplicate them.
        """
        # Initialize migration map
        await self.init_migration_map()

        # Check if this chat was migrated from an old chat
        old_chat_id = self._migration_map.get(chat_id)

        if old_chat_id is None:
            # No migration, just fetch normally
            logger.debug(f"Chat {chat_id} has no migration history")
            return await self._get_messages_for_single_chat(
                chat_id, ignore_cache=ignore_cache, limit=limit, offset=offset,
                min_date=min_date, max_date=max_date,
                **kwargs
            )

        # This chat was migrated - fetch messages from BOTH old and new chats
        logger.info(f"Chat {chat_id} was migrated from {old_chat_id}, fetching messages from both")

        # Fetch from new chat (current channel)
        new_messages = await self._get_messages_for_single_chat(
            chat_id, ignore_cache=ignore_cache, limit=None, offset=None,
            min_date=min_date, max_date=max_date,
            **kwargs
        )

        # Fetch from old chat (original group)
        old_messages = await self._get_messages_for_single_chat(
            old_chat_id, ignore_cache=ignore_cache, limit=None, offset=None,
            min_date=min_date, max_date=max_date,
            **kwargs
        )

        # Merge messages
        all_messages = new_messages + old_messages
        logger.debug(
            f"Merging messages: {len(new_messages)} from new chat + {len(old_messages)} from old chat = {len(all_messages)} total"
        )

        # Deduplicate and sort
        all_messages = self._deduplicate_messages(all_messages)
        all_messages = sorted(all_messages, key=lambda x: x.date, reverse=True)

        # Apply limit if specified
        if limit and len(all_messages) > limit:
            logger.debug(f"Truncating merged messages to limit {limit}")
            all_messages = all_messages[:limit]

        logger.info(
            f"Merged migration messages for chat {chat_id}: {len(all_messages)} total messages"
        )
        return all_messages

    async def get_raw_messages(
        self, source: str | int, ignore_cache=False, limit=None, offset=None,
        min_date: datetime.datetime | None = None,
        max_date: datetime.datetime | None = None,
        **kwargs
    ):
        """Get messages with automatic migration handling."""
        chat_id = await self._get_chat_id(source)
        logger.debug(
            f"Getting messages for chat {chat_id} (source: {source}), ignore_cache={ignore_cache}, limit={limit}, offset={offset}, min_date={min_date}, max_date={max_date}, kwargs={kwargs}"
        )

        return await self._get_messages_with_migration(
            chat_id, ignore_cache=ignore_cache, limit=limit, offset=offset,
            min_date=min_date, max_date=max_date,
            **kwargs
        )

    async def _get_messages_for_single_chat(
        self, chat_id: int, ignore_cache=False, limit=None, offset=None,
        min_date: datetime.datetime | None = None,
        max_date: datetime.datetime | None = None,
        **kwargs
    ) -> list[Message]:
        """Get messages for a single chat ID without migration handling."""
        has_cache = await self._has_cached_messages(chat_id)

        if ignore_cache or not has_cache or offset is not None or kwargs:
            # Load the messages directly from Telegram API
            # NOTE: min_date is passed to enable early break in iteration
            logger.debug(
                f"Loading messages directly from API for chat {chat_id} (ignore_cache={ignore_cache}, has_cache={has_cache}, offset={offset}, min_date={min_date}, kwargs={bool(kwargs)})"
            )
            return await self._get_raw_messages(
                chat_id, limit=limit, offset=offset, min_date=min_date, **kwargs
            )
        else:
            if self.mongo_enabled:
                # MongoDB path - simple and efficient
                logger.debug(f"Using MongoDB cache for chat {chat_id} (min_date={min_date}, max_date={max_date})")

                # Check for newer messages and fetch if needed
                await self._load_newer_messages(chat_id, [])

                # Load from MongoDB with date filtering
                messages = await self._load_raw_messages(
                    chat_id, limit=limit, offset=offset,
                    min_date=min_date, max_date=max_date  # Pass date filters to MongoDB
                )

                # Check for missing historical messages
                messages = await self._load_missing_messages(
                    chat_id, messages, limit=limit, offset=offset, min_date=min_date
                )

                logger.debug(f"Returning {len(messages)} messages for chat {chat_id}")
                return messages
            else:
                # Original JSON file path
                logger.debug(f"Using JSON cache for chat {chat_id}")
                messages = await self._load_raw_messages(chat_id)
                # load fresh messages if present
                messages = await self._load_newer_messages(chat_id, messages)
                messages = await self._load_missing_messages(
                    chat_id, messages, limit=limit
                )
                # todo: ensure dediplication runs only if there actually multiple sources of data (new messages or older messages)
                messages = self._deduplicate_messages(messages)
                messages = sorted(messages, key=lambda x: x.date, reverse=True)
                if limit and len(messages) > limit:
                    logger.debug(
                        f"Truncating messages to limit {limit} for chat {chat_id}"
                    )
                    messages = messages[:limit]
                logger.debug(f"Returning {len(messages)} messages for chat {chat_id}")
                return messages

    async def clear_cache(self, chat_id: int):
        """Clear cache for a specific chat"""
        if self.mongo_enabled:
            await self.init_messages_collection()
            await self.messages_collection.delete_many({"chat_id": chat_id})
        else:
            cache_file = self.root_path / f"messages_{chat_id}.json"
            if cache_file.exists():
                cache_file.unlink()

    # -----------------------------------------------------------------------------
    # endregion Raw Messages
    # -----------------------------------------------------------------------------

    async def get_entity(self, entity_id: int) -> User | Chat | Channel:
        """Get entity by ID with async-safe caching."""
        # Check cache first
        if entity_id in self._entity_cache:
            return self._entity_cache[entity_id]

        # Fetch from Telethon client
        entity = await self.telethon_client.get_entity(entity_id)

        # Cache the result
        self._entity_cache[entity_id] = entity

        return entity

    # -----------------------------------------------------------------------------
    # region Rich Model Methods
    # -----------------------------------------------------------------------------

    async def get_chats(
        self,
        ignore_cache: bool = False,
        min_users: int | None = None,
        max_users: int | None = None,
        is_owned: bool | None = None,
        **kwargs,
    ) -> list[TelegramChat]:
        """Get all chats as rich TelegramChat objects."""
        entities = await self.get_raw_dialog_entities(invalidate_cache=ignore_cache)
        await self.init_migration_map(entities)  # Initialize migration data
        chats = []

        for entity in entities:
            chat_obj = None

            # Use proper chat type detection from chat_utils
            if chat_is_group(entity):
                chat_obj = TelegramGroupChat(entity)
            elif chat_is_channel(entity):
                chat_obj = TelegramChannel(entity)
            elif chat_is_private(entity):
                chat_obj = TelegramUserChat(entity)
            elif chat_is_bot(entity):
                chat_obj = TelegramBotChat(entity)
            else:
                if isinstance(entity, ChatForbidden):
                    logger.debug("Encountered ChatForbidden entity type")
                else:
                    logger.warning(
                        f"Unknown chat type: {type(entity)}, using TelegramChat fallback"
                    )
                chat_obj = TelegramChat(entity)

            if chat_obj and self._filter_chat(chat_obj, min_users, max_users, is_owned):
                chats.append(chat_obj)

        # Process migrations separately
        chats = self._process_migrations(chats)
        return chats

    async def get_folders(
        self, ignore_cache: bool = False, **kwargs
    ) -> list[TelegramFolder]:
        """Get all folders as rich TelegramFolder objects."""
        filters = await self.get_raw_dialog_filters(invalidate_cache=ignore_cache)
        folders = []

        for filter_entity in filters.filters:
            folders.append(TelegramFolder(filter_entity))

        return folders

    async def get_messages(
        self, source: str | int, ignore_cache: bool = False,
        min_date: datetime.datetime | None = None,
        max_date: datetime.datetime | None = None,
        **kwargs
    ) -> list[TelegramMessage]:
        """Get messages as rich TelegramMessage objects."""
        raw_messages = await self.get_raw_messages(
            source, ignore_cache=ignore_cache,
            min_date=min_date, max_date=max_date,
            **kwargs
        )
        return [TelegramMessage(message) for message in raw_messages]

    async def get_users(
        self, ignore_cache: bool = False, **kwargs
    ) -> list[TelegramUserChat]:
        """Get all user chats as TelegramUserChat objects."""
        chats = await self.get_chats(ignore_cache=ignore_cache, **kwargs)
        return [chat for chat in chats if isinstance(chat, TelegramUserChat)]

    async def get_channels(
        self,
        ignore_cache: bool = False,
        min_users: int | None = None,
        max_users: int | None = None,
        is_owned: bool | None = None,
        **kwargs,
    ) -> list[TelegramChannel]:
        """Get all channels as TelegramChannel objects."""
        chats = await self.get_chats(
            ignore_cache=ignore_cache,
            min_users=min_users,
            max_users=max_users,
            is_owned=is_owned,
            **kwargs,
        )
        return [chat for chat in chats if isinstance(chat, TelegramChannel)]

    async def get_group_chats(
        self,
        ignore_cache: bool = False,
        min_users: int | None = None,
        max_users: int | None = None,
        is_owned: bool | None = None,
        **kwargs,
    ) -> list[TelegramGroupChat]:
        """Get all group chats as TelegramGroupChat objects."""
        chats = await self.get_chats(
            ignore_cache=ignore_cache,
            min_users=min_users,
            max_users=max_users,
            is_owned=is_owned,
            **kwargs,
        )
        return [chat for chat in chats if isinstance(chat, TelegramGroupChat)]

    def _filter_chat(
        self,
        chat: TelegramChat,
        min_users: int | None = None,
        max_users: int | None = None,
        is_owned: bool | None = None,
    ) -> bool:
        """Apply filters to chat objects."""
        entity = chat.entity

        # Filter by user count (for channels/groups)
        if min_users is not None or max_users is not None:
            if isinstance(entity, (Channel, Chat)):
                participants_count = getattr(entity, "participants_count", None)
                if participants_count is not None:
                    if min_users is not None and participants_count < min_users:
                        return False
                    if max_users is not None and participants_count > max_users:
                        return False

        # Filter by ownership
        if is_owned is not None:
            if isinstance(entity, (Channel, Chat)):
                creator = getattr(entity, "creator", False)
                if is_owned != creator:
                    return False

        return True

    def _process_migrations(self, chats: list[TelegramChat]) -> list[TelegramChat]:
        """Filter out migrated chats and link migration info."""
        if self._migration_map is None or self._migrated_chat_ids is None:
            raise RuntimeError(
                "migration_map not initialized. Call init_migration_map() first."
            )

        filtered_chats = []
        skipped_count = 0

        for chat in chats:
            # Skip old migrated chats
            if chat.id in self._migrated_chat_ids:
                skipped_count += 1
                # logger.debug(f"Skipping migrated chat {chat.id} ({getattr(chat, 'name', 'Unknown')})")
                continue

            # Add migration info if this is a migrated-to chat
            if chat.id in self._migration_map:
                chat._migrated_from_chat_id = self._migration_map[chat.id]
                # logger.debug(f"Linked migration: chat {chat.id} <- {chat._migrated_from_chat_id}")

            filtered_chats.append(chat)

        logger.debug(
            f"Filtered out {skipped_count} migrated chats, {len(filtered_chats)} remaining"
        )
        return filtered_chats

    # -----------------------------------------------------------------------------
    # endregion Rich Model Methods
    # -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# Helper functions for context manager usage
# -----------------------------------------------------------------------------

class _TelegramCacheContextManager:
    """
    Temporary TelegramCache instance that properly cleans up after use.

    This bypasses the Singleton pattern to create a fresh instance that
    will be properly closed when the context exits.
    """
    def __init__(self, **kwargs):
        # Create instance directly without Singleton
        self._cache = object.__new__(TelegramCache)
        TelegramCache.__init__(self._cache, **kwargs)

    async def __aenter__(self):
        """Initialize and return the cache instance."""
        await self._cache.init_telethon_client()
        await self._cache.init_messages_collection()
        return self._cache

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup the cache instance."""
        await self._cache.close()
        return False  # Don't suppress exceptions


def get_telegram_cache_context(**kwargs):
    """
    Create a temporary TelegramCache instance for use in a context manager.

    This is the recommended way to use TelegramCache when you want to ensure
    proper cleanup of the telethon client connection.

    Usage:
        async with get_telegram_cache_context() as cache:
            messages = await cache.get_messages(chat_id)
            # Client will be automatically disconnected when exiting the block

    Args:
        **kwargs: Arguments to pass to TelegramCache constructor

    Returns:
        Context manager that yields an initialized TelegramCache instance

    Example:
        # Use with default secondary account
        async with get_telegram_cache_context() as cache:
            chats = await cache.get_chats()

        # Use with primary account
        async with get_telegram_cache_context(telethon_account="primary") as cache:
            messages = await cache.get_messages(chat_id, limit=100)
    """
    return _TelegramCacheContextManager(**kwargs)
