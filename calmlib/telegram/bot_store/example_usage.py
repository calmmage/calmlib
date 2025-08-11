#!/usr/bin/env python3
"""
Example usage of the Telegram Bot Key Store
"""

from calmlib import BotKeyStore

def main():
    # Initialize the bot key store
    store = BotKeyStore()
    
    print("🔑 Telegram Bot Key Store Example")
    print("=" * 40)
    
    # Add some bot keys (you would replace these with real tokens)
    print("\n📝 Adding bot keys...")
    try:
        store.add_bot_key(
            token="123456:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",
            username="my_test_bot_1",
            owner="petrlavrov"
        )
        store.add_bot_key(
            token="789012:BBHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw", 
            username="my_test_bot_2",
            owner="petrlavrov"
        )
        print("✅ Bot keys added successfully")
    except Exception as e:
        print(f"⚠️  Keys might already exist: {e}")
    
    # Check available keys
    print(f"\n📊 Available keys: {store.get_free_key_count()}")
    print(f"📊 Busy keys: {store.get_busy_key_count()}")
    
    # Get a key for your project
    print("\n🎯 Getting a key for my project...")
    bot_key = store.get_free_key("my_awesome_project")
    
    if bot_key:
        print(f"✅ Got bot key: {bot_key.username}")
        print(f"   Token: {bot_key.token[:20]}...")
        print(f"   Used by: {bot_key.used_by}")
        
        # Use the bot key in your project here...
        print("🤖 Using bot for project work...")
        
        # Release the key when done
        print(f"\n🔓 Releasing key: {bot_key.username}")
        store.release_key(bot_key.username)
        print("✅ Key released")
    else:
        print("❌ No free keys available")
    
    # Final status
    print("\n📊 Final status:")
    print(f"   Free keys: {store.get_free_key_count()}")
    print(f"   Busy keys: {store.get_busy_key_count()}")
    
    # Clean up
    store.close()
    print("\n✨ Done!")

if __name__ == "__main__":
    main()