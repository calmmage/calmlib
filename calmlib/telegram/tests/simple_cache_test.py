#!/usr/bin/env python3
"""
Dead simple, isolated test for TelegramCache.
No pytest, no fixtures, no complications.
"""

import asyncio
import traceback
from pathlib import Path

from loguru import logger

from calmlib.telegram.telegram_cache import TelegramCache

EXPECTED_NEWEST_DATE = "2024-03-07"  # Replace with expected newest message date
EXPECTED_OLDEST_DATE = "2024-01-12"  # Replace with expected oldest message date
# Test configuration from conftest
CHAT_ID = 433071421
TOTAL_MESSAGES = 8  # 8 messages total
SMALL_LIMIT = 5  # Small subset for testing
LARGE_LIMIT = 8  # All messages


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


async def basic_fetch(mongo_enabled: bool):
    """Test 1: Basic message fetch"""
    logger.info("🧪 Test 1: Basic message fetch")

    try:
        cache = TelegramCache(telethon_account="secondary", mongo_enabled=mongo_enabled)

        # Clear cache
        await clear_cache(CHAT_ID, mongo_enabled)

        # Fetch messages
        messages = await cache.get_raw_messages(CHAT_ID, limit=SMALL_LIMIT)

        # Assertions
        assert len(messages) == SMALL_LIMIT, (
            f"Expected {SMALL_LIMIT} messages, got {len(messages)}"
        )
        assert messages[0].date is not None, "First message should have date"
        assert messages[-1].date is not None, "Last message should have date"
        assert messages[0].date >= messages[-1].date, (
            "Messages should be sorted newest first"
        )

        # Verify cache was created
        has_cache = await cache._has_cached_messages(CHAT_ID)
        assert has_cache, "Cache should be created after fetch"

        logger.info(f"✓ Fetched {len(messages)} messages")
        logger.info(f"  Newest: {messages[0].date}")
        logger.info(f"  Oldest: {messages[-1].date}")
        logger.info(f"✓ Cache created: {has_cache}")

        return messages

    except Exception as e:
        logger.error(f"❌ Test 1 failed: {e}")
        raise


async def cached_fetch(mongo_enabled: bool):
    """Test 2: Cached message fetch (should be fast)"""
    logger.info("🧪 Test 2: Cached message fetch")

    try:
        cache = TelegramCache(telethon_account="secondary", mongo_enabled=mongo_enabled)

        # Fetch from cache (should be quick)
        import time

        start = time.time()
        messages = await cache.get_raw_messages(CHAT_ID, limit=SMALL_LIMIT)
        end = time.time()

        # Assertions
        assert len(messages) == SMALL_LIMIT, (
            f"Expected {SMALL_LIMIT} messages, got {len(messages)}"
        )
        assert end - start < 2.0, (
            f"Cache fetch took too long: {end - start:.2f}s (should be < 2s)"
        )
        assert messages[0].date >= messages[-1].date, (
            "Messages should be sorted newest first"
        )

        logger.info(
            f"✓ Fetched {len(messages)} messages from cache in {end - start:.2f}s"
        )
        logger.info(f"  Newest: {messages[0].date}")
        logger.info(f"  Oldest: {messages[-1].date}")

        return messages

    except Exception as e:
        logger.error(f"❌ Test 2 failed: {e}")
        raise


async def fresh_vs_cached(mongo_enabled: bool):
    """Test 3: Compare fresh vs cached"""
    logger.info("🧪 Test 3: Fresh vs cached comparison")

    try:
        cache = TelegramCache(telethon_account="secondary", mongo_enabled=mongo_enabled)

        # Get cached
        cached = await cache.get_raw_messages(CHAT_ID, limit=SMALL_LIMIT)

        # Get fresh
        fresh = await cache.get_raw_messages(
            CHAT_ID, limit=SMALL_LIMIT, ignore_cache=True
        )

        # Compare
        cached_ids = [m.id for m in cached]
        fresh_ids = [m.id for m in fresh]

        # Assertions
        assert len(cached) == len(fresh), (
            f"Length mismatch: cached={len(cached)}, fresh={len(fresh)}"
        )
        assert cached_ids == fresh_ids, (
            "Message IDs should match between cached and fresh"
        )

        logger.info("✓ Cached vs fresh match: True")
        logger.info(f"  Cached: {len(cached)} messages")
        logger.info(f"  Fresh: {len(fresh)} messages")

    except AssertionError as e:
        logger.error(f"❌ Test 3 assertion failed: {e}")
        logger.error(f"    Cached IDs: {cached_ids[:3]}...")
        logger.error(f"    Fresh IDs: {fresh_ids[:3]}...")
        raise
    except Exception as e:
        logger.error(f"❌ Test 3 failed: {e}")
        raise


async def partial_cache(mongo_enabled):
    """Test 4: Partial cache behavior (fetch subset, then all)"""
    logger.info("🧪 Test 4: Partial cache behavior")

    try:
        cache = TelegramCache(telethon_account="secondary", mongo_enabled=mongo_enabled)

        # Clear cache
        await clear_cache(CHAT_ID, mongo_enabled)

        # Fetch subset first (offset=2, limit=3 out of 8 total)
        partial = await cache.get_raw_messages(CHAT_ID, limit=3, offset=2)

        # Then fetch all (should include the partial ones)
        all_msgs = await cache.get_raw_messages(CHAT_ID, limit=LARGE_LIMIT)

        # Assertions
        assert len(partial) == 3, f"Expected 3 partial messages, got {len(partial)}"
        assert len(all_msgs) <= TOTAL_MESSAGES, (
            f"Too many messages: {len(all_msgs)} > {TOTAL_MESSAGES}"
        )
        assert len(all_msgs) >= len(partial), (
            "All messages should include partial messages"
        )

        # Verify no duplicates
        all_ids = [m.id for m in all_msgs]
        assert len(all_ids) == len(set(all_ids)), "Found duplicate messages"

        logger.info(f"✓ Partial fetch: {len(partial)} messages")
        logger.info(f"✓ Full fetch: {len(all_msgs)} messages")
        logger.info("✓ No duplicates found")

    except Exception as e:
        logger.error(f"❌ Test 4 failed: {e}")
        raise


async def main():
    """Run all tests"""
    logger.info("🚀 Starting simple TelegramCache tests...")
    logger.info(f"  Chat ID: {CHAT_ID}")
    logger.info(f"  Expected total messages: {TOTAL_MESSAGES}")
    # logger.info(f"  MongoDB enabled: {MONGO_ENABLED}")

    tests = [
        ("Basic fetch", basic_fetch),
        ("Cached fetch", cached_fetch),
        ("Fresh vs cached", fresh_vs_cached),
        ("Partial cache", partial_cache),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            await test_func(mongo_enabled=False)
            logger.success(f"✅ {name}: PASSED")
            passed += 1
        except Exception as e:
            logger.error(f"❌ {name}: FAILED")
            logger.error(f"   Error: {e}")
            failed += 1
            traceback.print_exc()
            # Continue with other tests
        try:
            await test_func(mongo_enabled=True)
            logger.success(f"✅ {name}: PASSED")
            passed += 1
        except Exception as e:
            logger.error(f"❌ {name}: FAILED")
            logger.error(f"   Error: {e}")
            failed += 1
            traceback.print_exc()
            # Continue with other tests

    await clear_cache(CHAT_ID, mongo_enabled=False)

    logger.info("\n📊 Test Summary:")
    logger.info(f"  Passed: {passed}")
    logger.info(f"  Failed: {failed}")
    logger.info(f"  Total:  {len(tests)}")

    if failed == 0:
        logger.success("🎉 All tests passed!")
    else:
        logger.error(f"💥 {failed} test(s) failed!")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
