"""The shared message cache, for scripts that read Mongo directly (sync pymongo).

One place decides which collection belongs to which account: the ``[accounts]`` map in the
config. Scripts never spell ``messages_user_<id>`` themselves, so two consumers of the same
account always read the same collection and never another account's.

    from calmlib.telegram.store import messages_collection
    col = messages_collection("primary")
    col.count_documents({"chat_id": chat_id})
"""

from __future__ import annotations

from calmlib.telegram.config import AccountNotBound, get_config


def collection_name(user_id: int) -> str:
    """Name of a Telegram user's message collection. The only spelling of it."""
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise AccountNotBound(f"not a Telegram user id: {user_id!r}")
    return f"messages_user_{user_id}"


def account_user_id(account: str) -> int:
    uid = get_config().account_id(account)
    if uid is None:
        raise AccountNotBound(
            f"no user id for account {account!r}: add it under [accounts] in the telegram config"
        )
    return uid


def messages_collection(account: str, client=None, timeout_ms: int = 3000):
    """The account's message collection in the shared Mongo cache (read it; the cache writes)."""
    config = get_config()
    uid = account_user_id(account)
    if client is None:
        from pymongo import MongoClient

        client = MongoClient(config.mongo, serverSelectionTimeoutMS=timeout_ms)
    return client[config.db][collection_name(uid)]


def chat_id_filter(chat_ids) -> dict:
    """Match chats whether a row stored chat_id as int or as str (older cache rows did)."""
    ids = [int(c) for c in chat_ids]
    return {"chat_id": {"$in": ids + [str(c) for c in ids]}}
