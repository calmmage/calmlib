import json
from typing import TYPE_CHECKING
from loguru import logger

from calmlib.telegram.chat_utils import chat_is_channel, chat_is_group
from calmlib.utils import cleanup_none

# todo: remove hard telethon dependencies
from telethon.types import (
    Channel,
    ChannelForbidden,
    Chat,
    ChatForbidden,
    Message,
    User,
    UserEmpty,
)
CHAT_ENTITY_CLASSES = {
    "User": User,
    "Chat": Chat,
    "Channel": Channel,
    "ChatForbidden": ChatForbidden,
    "ChannelForbidden": ChannelForbidden,
    "UserEmpty": UserEmpty,
}
if TYPE_CHECKING:
    from telethon.types import (
        Channel,
        ChannelForbidden,
        Chat,
        ChatForbidden,
        Message,
        User,
        UserEmpty,
    )
    from telethon.tl.types import DialogFilter, DialogFilterChatlist, DialogFilterDefault

def get_chat_entity_class(entity_type: str):
    from telethon.types import (
        Channel,
        ChannelForbidden,
        Chat,
        ChatForbidden,
        Message,
        User,
        UserEmpty,
    )
    CHAT_ENTITY_CLASSES = {
        "User": User,
        "Chat": Chat,
        "Channel": Channel,
        "ChatForbidden": ChatForbidden,
        "ChannelForbidden": ChannelForbidden,
        "UserEmpty": UserEmpty,
    }
    return CHAT_ENTITY_CLASSES[entity_type]

def get_folder_entity_class(entity_type: str):
    from telethon.tl.types import DialogFilter, DialogFilterChatlist, DialogFilterDefault
    FOLDER_ENTITY_CLASSES = {
        "DialogFilter": DialogFilter,
        "DialogFilterChatlist": DialogFilterChatlist,
        "DialogFilterDefault": DialogFilterDefault,
    }
    return FOLDER_ENTITY_CLASSES[entity_type]


class TelegramMessage:
    def __init__(self, entity: "Message"):
        self.entity = entity

    def to_json(self):
        pass

    @classmethod
    def from_json(cls, json_str: str):
        pass

    # todo 1: pass forward essential fields from entity
    # todo 2: "Download file / media / whatever from the message" - using pyrogram I guess
    # todo 3: text, html text

    @property
    def text(self):
        return self.entity.message

    # @property
    # def html_text(self):
    #     if hasattr(self.entity, "html_text"):
    #         return self.entity.html_text
    #     if hasattr(self.entity, "caption_html"):
    #         return self.entity.caption_html
    #     return None

    @property
    def date(self):
        assert self.entity.date is not None
        return self.entity.date.date()

    # id: int
    # chat_id: int
    # date: datetime
    # text: Optional[str] = None

    # # Sender info
    # from_id: Optional[int] = None
    # from_username: Optional[str] = None

    # # Message metadata
    # reply_to_msg_id: Optional[int] = None
    # forward_from_id: Optional[int] = None
    # edit_date: Optional[datetime] = None

    # # Media info
    # has_media: bool = False
    # media_type: Optional[str] = None  # 'photo', 'document', 'video', etc.
    # file_size: Optional[int] = None

    # # Raw message data (for fallback access)
    # message_data: Dict[str, Any] = Field(default_factory=dict)

    # @property
    # def is_outgoing(self) -> bool:
    #     """Check if message was sent by the current user."""
    #     return self.message_data.get('out', False)

    @property
    def sender_id(self):
        if self.entity.from_id:
            # from_id is a Peer object (PeerUser, PeerChannel, etc)
            # Extract the actual integer ID
            if hasattr(self.entity.from_id, "user_id"):
                return self.entity.from_id.user_id
            elif hasattr(self.entity.from_id, "channel_id"):
                return self.entity.from_id.channel_id
            elif hasattr(self.entity.from_id, "chat_id"):
                return self.entity.from_id.chat_id
            else:
                return self.entity.from_id
        if self.entity.peer_id:
            # peer_id is also a Peer object
            if hasattr(self.entity.peer_id, "user_id"):
                return self.entity.peer_id.user_id
            elif hasattr(self.entity.peer_id, "channel_id"):
                return self.entity.peer_id.channel_id
            elif hasattr(self.entity.peer_id, "chat_id"):
                return self.entity.peer_id.chat_id
            else:
                return self.entity.peer_id
        raise ValueError(f"Can't determine sender_id for message {self.entity.id}")

    @property
    def sender_username(self):
        # todo: store a map id -> user somewhere accessible?
        raise NotImplementedError(
            "sender_username is not implemented for TelegramMessage"
        )

    @property
    def reactions(self):
        """Get reactions on this message (MessageReactions object or None)"""
        return self.entity.reactions if hasattr(self.entity, "reactions") else None


class TelegramChat:
    type: str = "unspecified_chat_type"

    def __init__(self, entity: "Chat | Channel | User | ChatForbidden"):
        self.entity: Chat | Channel | User | ChatForbidden = entity
        self._migrated_from_chat_id: int | None = None

    def to_json(self):
        entity_json = self.entity.to_json()
        assert entity_json is not None
        entity_data = json.loads(entity_json)
        # cleanup Nones
        entity_data = cleanup_none(entity_data)
        class_name = type(self.entity).__name__
        return json.dumps({"entity": entity_data, "_": class_name})

    @classmethod
    def create(cls, entity: "Chat | Channel | User"):
        """Factory method to create the appropriate TelegramChat subclass based on entity type."""

        if isinstance(entity, User):
            if entity.bot:
                return TelegramBotChat(entity)
            else:
                return TelegramUserChat(entity)
        elif chat_is_group(entity):
            # This handles both Chat entities and Channel entities with megagroup=True
            return TelegramGroupChat(entity)
        elif isinstance(entity, Channel) and chat_is_channel(entity):
            # This handles Channel entities with megagroup=False (broadcast channels)
            return TelegramChannel(entity)
        else:
            # Fallback to base class
            return cls(entity)

    @classmethod
    def from_json(cls, json_str: str):
        data = json.loads(json_str)
        entity_data = data["entity"]

        # Get class name and remove from dict
        entity_class_name = entity_data.pop("_")
        entity_class = get_chat_entity_class(entity_class_name)

        # Remove the class name from data (no longer need to assert since factory handles class selection)
        data.pop("_", None)

        # Reconstruct entity using cleaned kwargs
        entity = entity_class(**entity_data)
        return cls.create(entity)  # Use factory method

    @property
    def name(self):
        # raise NotImplementedError("name is not implemented for TelegramChat")
        if isinstance(self.entity, ChatForbidden):
            return self.entity.title or str(self.entity.id)
        else:
            raise NotImplementedError("name is not implemented for TelegramChat")

    @property
    def _id(self) -> int:
        assert self.entity.id is not None
        return self.entity.id

    def __repr__(self):
        return f"TelegramChat(name={self.name}, type={self.type}, id={self.id})"

    async def get_messages(
        self, telethon_account="primary", **kwargs
    ) -> list[TelegramMessage]:
        from calmlib.telegram.utils import get_telegram_cache

        cache = get_telegram_cache(telethon_account=telethon_account, **kwargs)
        messages = await cache.get_messages(self.id)

        # If migrated, also get old messages
        if self._migrated_from_chat_id:
            try:
                old_messages = await cache.get_messages(self._migrated_from_chat_id)
                messages.extend(old_messages)
            except Exception as e:
                logger.warning(
                    f"Could not get messages from migrated chat {self._migrated_from_chat_id}: {e}"
                )

        return messages

    # id: int
    @property
    def id(self):
        return self.entity.id


#     # Metadata
#     last_message_date: Optional[datetime] = None


#     @property
#     def is_recent(self) -> bool:
#         """Check if chat had recent activity (last 30 days)."""
#         if not self.last_message_date:
#             return False
#         from datetime import timedelta
#         return (datetime.now() - self.last_message_date) < timedelta(days=30)

#     @property
#     def is_big(self) -> bool:
#         """Check if chat is big (>1000 participants)."""
#         return (self.participants_count or 0) > 1000

#     @property
#     def display_name(self) -> str:
#         """Get display name for the chat."""
#         if self.entity_type == 'private_chat':
#             parts = []
#             if self.first_name:
#                 parts.append(self.first_name)
#             if self.last_name:
#                 parts.append(self.last_name)
#             if parts:
#                 name = ' '.join(parts)
#             else:
#                 name = self.username or f"User_{self.id}"
#         else:
#             name = self.title or self.username or f"Chat_{self.id}"

#         if self.username:
#             name += f" @{self.username}"

#         return f"{name} [{self.id}]"


class TelegramGroupChat(TelegramChat):
    type = "group"
    entity: "Chat | Channel"

    def __init__(self, entity: "Chat | Channel"):
        super().__init__(entity)

    @property
    def name(self):
        return self.entity.title

    @property
    def is_owned(self):
        return self.entity.creator

    @property
    def title(self):
        return self.entity.title

    @property
    def participants_count(self):
        return self.entity.participants_count


class TelegramChannel(TelegramChat):
    type = "channel"
    entity: "Channel"

    def __init__(self, entity: "Channel"):
        super().__init__(entity)

    @property
    def name(self):
        return self.entity.title

    @property
    def is_owned(self):
        return self.entity.creator

    @property
    def username(self):
        return self.entity.username

    @property
    def title(self):
        return self.entity.title

    @property
    def participants_count(self):
        return self.entity.participants_count


#     # Group/Channel specific fields
#     is_verified: bool = False
#     is_megagroup: bool = False
#     is_broadcast: bool = False


class TelegramUserChat(TelegramChat):
    type = "user"
    entity: "User"

    def __init__(self, entity: "User"):
        super().__init__(entity)

    @property
    def name(self) -> str:
        if self.entity.first_name and self.entity.last_name:
            return self.entity.first_name + " " + self.entity.last_name
        elif self.entity.first_name:
            return self.entity.first_name
        elif self.entity.last_name:
            return self.entity.last_name
        if self.entity.username:
            return f"@{self.entity.username}"
        return ""

    @property
    def username(self):
        return self.entity.username

    # name: str
    # title: Optional[str] = None

    # User-specific fields
    # first_name: Optional[str] = None
    # last_name: Optional[str] = None
    # phone: Optional[str] = None


class TelegramBotChat(TelegramUserChat):
    type = "bot"

    def __init__(self, entity: "User"):
        super().__init__(entity)


class TelegramFolder:
    def __init__(
        self,
        entity: "DialogFilter",
        chats: list["TelegramChat"] | None = None,
    ):
        self.entity: "DialogFilter"    = entity
        self.chats = chats or []

    def to_json(self):
        entity_json = self.entity.to_json()
        assert entity_json is not None
        entity_data = json.loads(entity_json)
        # cleanup Nones
        entity_data = cleanup_none(entity_data)
        return json.dumps(
            {
                "entity": entity_data,
                "chats": [json.loads(chat.to_json()) for chat in self.chats],
            }
        )

    @property
    def name(self):
        return (
            self.entity.title.text
            if hasattr(self.entity.title, "text")
            else str(self.entity.title)
        )

    @classmethod
    def from_json(cls, json_str: str):
        data = json.loads(json_str)
        entity_data = data["entity"]

        # Get class name and remove from dict
        class_name = entity_data.pop("_")
        entity_class = get_folder_entity_class(class_name)
        entity = entity_class(**entity_data)

        # Reconstruct chats using factory method
        chats = [
            TelegramChat.from_json(json.dumps(chat_data)) for chat_data in data["chats"]
        ]

        return cls(entity, chats)

    # id: int
    # title: str

    # # Chat filters
    # include_peers: List[int] = Field(default_factory=list)
    # exclude_peers: List[int] = Field(default_factory=list)
    # pinned_peers: List[int] = Field(default_factory=list)

    # # Content filters
    # filter_bots: bool = False
    # filter_broadcasts: bool = False
    # filter_groups: bool = False
    # filter_contacts: bool = False
    # filter_non_contacts: bool = False

    # # Status filters
    # exclude_muted: bool = False
    # exclude_read: bool = False
    # exclude_archived: bool = False

    # # Raw folder data (for fallback access)
    # folder_data: Dict[str, Any] = Field(default_factory=dict)


# TelegramChat = Union[TelegramGroupChat, TelegramChannel, TelegramUserChat]
