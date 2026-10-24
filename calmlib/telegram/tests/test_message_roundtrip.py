"""Offline round-trip tests for cached Telegram messages.

Regression: messages loaded back from the cache (Mongo or JSON) used to have
`from_id` / `peer_id` flattened to bare ints, and replies / entities / action
left as raw dicts, so `m.from_id.user_id`, `m.chat_id` and Telethon's
`m.sender_id` were wrong for cached messages.
"""

import asyncio
import datetime
import json

from telethon.tl import types
from telethon.tl.patched import Message, MessageService

from calmlib.telegram.models import TelegramMessage
from calmlib.telegram.telegram_cache import TelegramCache
from calmlib.utils import cleanup_none

DATE = datetime.datetime(2026, 9, 17, 12, 0, tzinfo=datetime.timezone.utc)


def _stored(message) -> dict:
    """Exactly what _save_messages_to_mongo / _save_messages_to_json store."""
    data = json.loads(message.to_json())
    cleanup_none(data, none_entities=(None, [], {}, False, ""))
    return data


def _group_message() -> Message:
    return Message(
        id=42,
        peer_id=types.PeerChannel(channel_id=3824413874),
        date=DATE,
        message="hello @bob",
        from_id=types.PeerUser(user_id=682619),
        reply_to=types.MessageReplyHeader(reply_to_msg_id=41, reply_to_top_id=40),
        fwd_from=types.MessageFwdHeader(
            date=DATE - datetime.timedelta(days=1),
            from_id=types.PeerChannel(channel_id=777),
        ),
        media=types.MessageMediaPhoto(
            photo=types.Photo(
                id=1,
                access_hash=2,
                file_reference=b"\x00\x01ref",
                date=DATE,
                sizes=[types.PhotoSize(type="x", w=10, h=10, size=100)],
                dc_id=2,
            )
        ),
        entities=[types.MessageEntityMention(offset=6, length=4)],
        replies=types.MessageReplies(replies=3, replies_pts=9),
        edit_date=DATE + datetime.timedelta(minutes=5),
    )


def test_group_message_roundtrip_keeps_peers_and_nested_objects():
    original = _group_message()
    restored = TelegramCache.message_from_dict(_stored(original))

    assert isinstance(restored, Message)
    assert isinstance(restored.from_id, types.PeerUser)
    assert restored.from_id.user_id == 682619
    assert isinstance(restored.peer_id, types.PeerChannel)
    assert restored.chat_id == original.chat_id == -1003824413874
    assert restored.sender_id == original.sender_id == 682619
    assert restored.reply_to.reply_to_msg_id == 41
    assert restored.fwd_from.date == original.fwd_from.date
    assert isinstance(restored.fwd_from.from_id, types.PeerChannel)
    assert restored.media.photo.file_reference == b"\x00\x01ref"
    assert isinstance(restored.entities[0], types.MessageEntityMention)
    assert isinstance(restored.replies, types.MessageReplies)
    assert restored.edit_date == original.edit_date
    assert restored.to_dict() == original.to_dict()

    wrapped = TelegramMessage(restored)
    assert wrapped.sender_id == 682619
    assert wrapped.reply_to_msg_id == 41
    assert wrapped.media_type == "MessageMediaPhoto"


def test_private_incoming_message_sender_from_peer():
    # incoming private messages carry no from_id; sender comes from peer_id
    original = Message(
        id=7, peer_id=types.PeerUser(user_id=555), date=DATE, message="hi"
    )
    restored = TelegramCache.message_from_dict(_stored(original))
    assert restored.from_id is None
    assert restored.sender_id == original.sender_id == 555
    assert TelegramMessage(restored).sender_id == 555


def test_channel_author_and_service_message():
    anon_admin = Message(
        id=8,
        peer_id=types.PeerChannel(channel_id=1),
        date=DATE,
        message="x",
        from_id=types.PeerChannel(channel_id=1),
    )
    restored = TelegramCache.message_from_dict(_stored(anon_admin))
    assert restored.from_id.channel_id == 1
    assert restored.sender_id == anon_admin.sender_id

    service = MessageService(
        id=9,
        peer_id=types.PeerChannel(channel_id=1),
        date=DATE,
        action=types.MessageActionPinMessage(),
        from_id=types.PeerUser(user_id=3),
    )
    restored = TelegramCache.message_from_dict(_stored(service))
    assert isinstance(restored, MessageService)
    assert isinstance(restored.action, types.MessageActionPinMessage)
    assert restored.to_dict() == service.to_dict()


def test_mongo_doc_extra_keys_ignored_and_input_not_mutated():
    doc = _stored(_group_message())
    doc["_id"] = "-1003824413874_42"
    doc["chat_id"] = -1003824413874
    snapshot = json.dumps(doc, sort_keys=True)
    restored = TelegramCache.message_from_dict(doc)
    assert restored.id == 42
    assert json.dumps(doc, sort_keys=True) == snapshot


def test_json_cache_file_roundtrip(tmp_path):
    path = tmp_path / "messages.json"
    messages = [
        _group_message(),
        Message(
            id=10,
            peer_id=types.PeerChannel(channel_id=1),
            date=DATE,
            message="channel-authored",
            from_id=types.PeerChannel(channel_id=1),
        ),
    ]
    path.write_text(json.dumps([_stored(m) for m in messages]))

    cache = object.__new__(TelegramCache)  # bypass singleton / telethon setup
    loaded = asyncio.run(cache._load_messages_to_json(chat_id=0, input_path=path))
    assert [m.to_dict() for m in loaded] == [m.to_dict() for m in messages]
