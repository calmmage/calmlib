"""
Test incremental message updates in TelegramCache.

This test verifies that when the cache has some messages but is missing recent ones,
calling get_raw_messages will properly fetch and add only the new messages.
"""

import asyncio
from pathlib import Path

from calmlib.telegram.telegram_cache import TelegramCache


async def clear_cache(chat_id: int, mongo_enabled: bool):
    """Clear cache for a specific chat"""
    if mongo_enabled:
        cache = TelegramCache()
        await cache.init_messages_collection()
        await cache.messages_collection.delete_many({"chat_id": chat_id})
    else:
        cache_file = Path(f"messages_{chat_id}.json")
        if cache_file.exists():
            cache_file.unlink()


async def incremental_message_update():
    """
    Test scenario:
    1. Load initial messages with offset (simulating yesterday's download)
    2. Call get_raw_messages again (simulating today's update)
    3. Verify that missing recent messages are fetched and cached
    """

    # Test configuration from conftest
    EXPECTED_NEWEST_DATE = "2024-03-07"  # Replace with expected newest message date
    EXPECTED_OLDEST_DATE = "2024-01-12"  # Replace with expected oldest message date
    CHAT_ID = 433071421
    TOTAL_MESSAGES = 8  # 8 messages total
    SMALL_LIMIT = 5  # Small subset for testing
    LARGE_LIMIT = 8  # All messages

    # Use MongoDB mode for testing with temp path
    temp_path = "/tmp/telegram_cache"
    cache = TelegramCache(root_path=Path(temp_path), mongo_enabled=True)

    # Clear any existing cache for this chat
    await cache.clear_cache(CHAT_ID)

    chat_id = CHAT_ID

    print("\n=== STEP 1: Initial load with offset (simulating old cache) ===")
    # Load only some messages, leaving recent ones missing
    initial_messages = await cache.get_raw_messages(
        chat_id,
        limit=SMALL_LIMIT,  # Only get 5 out of 8 messages
        offset=3,  # Skip 3 most recent messages
    )

    initial_count = len(initial_messages)
    if initial_count > 0:
        oldest_date = initial_messages[-1].date
        newest_date = initial_messages[0].date
        print(f"Loaded {initial_count} messages")
        print(f"Date range: {oldest_date} to {newest_date}")
        print(f"Message IDs: {[m.id for m in initial_messages[:3]]}...")

    # Get current cache state - check what's actually in cache
    print(f"Cache now has {initial_count} messages after first load")

    print("\n=== STEP 2: Update call (simulating next day update) ===")
    # Now call without offset - should fetch the missing recent messages
    updated_messages = await cache.get_raw_messages(
        chat_id,
    )
    await cache.clear_cache()

    updated_count = len(updated_messages)
    if updated_count > 0:
        newest_after_update = updated_messages[0].date
        print(f"After update: {updated_count} total messages")
        print(f"Newest message date: {newest_after_update}")
        print(f"Message IDs: {[m.id for m in updated_messages[:3]]}...")

    # Verify cache was updated by checking the returned message count
    print(f"Final call returned {updated_count} messages")

    print("\n=== VERIFICATION ===")
    # The key test: we should have MORE messages now
    new_messages_added = updated_count - initial_count
    print(f"New messages fetched and added: {new_messages_added}")

    # Expected: initial=5, final=8, added=3
    expected_added = TOTAL_MESSAGES - SMALL_LIMIT

    if new_messages_added == expected_added and updated_count == TOTAL_MESSAGES:
        print("✅ Test PASSED: Cache successfully updated with new messages")
        print(f"   Initial: {initial_count} messages (expected {SMALL_LIMIT})")
        print(f"   Final: {updated_count} messages (expected {TOTAL_MESSAGES})")
        print(
            f"   Added: {new_messages_added} new messages (expected {expected_added})"
        )
    else:
        print("❌ Test FAILED: Unexpected message counts")
        print(
            f"   Expected: initial={SMALL_LIMIT}, final={TOTAL_MESSAGES}, added={expected_added}"
        )
        print(
            f"   Actual: initial={initial_count}, final={updated_count}, added={new_messages_added}"
        )

    # Show the newest messages that were missing before
    if updated_count > initial_count:
        print("\nNewly added message IDs (were missing before):")
        new_msg_ids = [m.id for m in updated_messages[:new_messages_added]]
        print(f"   {new_msg_ids}")

    return new_messages_added == expected_added and updated_count == TOTAL_MESSAGES


if __name__ == "__main__":
    success = asyncio.run(incremental_message_update())
    exit(0 if success else 1)
