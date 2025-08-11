#!/usr/bin/env python3
"""
Simple test script for BotKeyStore
"""

from .bot_key_store import BotKeyStore


def test_bot_key_store():
    # Create a store instance
    store = BotKeyStore()
    
    print("🧪 Testing BotKeyStore...")
    
    # Test 1: Add some test bot keys
    print("\n1. Adding test bot keys...")
    try:
        bot1 = store.add_bot_key("123456:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw", "test_bot_1", "petrlavrov")
        print(f"   ✅ Added bot: {bot1.username}")
        
        bot2 = store.add_bot_key("987654:BBHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw", "test_bot_2", "petrlavrov") 
        print(f"   ✅ Added bot: {bot2.username}")
        
        bot3 = store.add_bot_key("555666:CCHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw", "test_bot_3", "petrlavrov")
        print(f"   ✅ Added bot: {bot3.username}")
        
    except Exception as e:
        print(f"   ⚠️  Bot might already exist: {e}")
    
    # Test 2: Check free key count
    print(f"\n2. Free keys count: {store.get_free_key_count()}")
    print(f"   Busy keys count: {store.get_busy_key_count()}")
    
    # Test 3: Get a free key
    print("\n3. Getting a free key for 'my_test_project'...")
    free_key = store.get_free_key("my_test_project")
    if free_key:
        print(f"   ✅ Got key: {free_key.username} (used by: {free_key.used_by})")
    else:
        print("   ❌ No free keys available")
    
    # Test 4: Check counts after getting a key
    print("\n4. After using a key:")
    print(f"   Free keys count: {store.get_free_key_count()}")
    print(f"   Busy keys count: {store.get_busy_key_count()}")
    
    # Test 5: Release the key
    if free_key:
        print(f"\n5. Releasing key: {free_key.username}")
        released = store.release_key(free_key.username)
        print(f"   ✅ Released: {released}")
    
    # Test 6: Check counts after release
    print("\n6. After releasing:")
    print(f"   Free keys count: {store.get_free_key_count()}")
    print(f"   Busy keys count: {store.get_busy_key_count()}")
    
    # Test 7: List all keys
    print("\n7. All keys in store:")
    all_keys = store.get_all_keys()
    for key in all_keys:
        print(f"   - {key.username}: {key.status} (owner: {key.owner})")
    
    # Clean up (optional - for testing)
    print("\n🧹 Cleaning up test keys...")
    cleanup_keys = ["test_bot_1", "test_bot_2", "test_bot_3"]
    for username in cleanup_keys:
        deleted = store.delete_key(username)
        if deleted:
            print(f"   ✅ Deleted: {username}")
    
    store.close()
    print("\n✨ Test completed!")


if __name__ == "__main__":
    test_bot_key_store()