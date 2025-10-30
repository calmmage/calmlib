"""
Utility functions for Telegram folder operations.
Based on logic from telegram_downloader data_model.py
"""



def chat_is_bot(entity):
    """Check if a chat entity is a bot."""
    from telethon.types import User
    if isinstance(entity, User):
        return entity.bot
    return False


def chat_is_private(entity):
    """Check if a chat entity is a private chat (user, not bot)."""
    from telethon.types import User
    if isinstance(entity, User):
        return not entity.bot
    return False


def chat_is_group(entity):
    """Check if a chat entity is a group (including megagroups)."""
    from telethon.types import Channel, Chat
    if isinstance(entity, Chat):
        return True
    elif isinstance(entity, Channel):
        # Megagroups are technically channels but function as groups
        return entity.megagroup
    return False


def chat_is_channel(entity):
    """Check if a chat entity is a channel (broadcast channel, not megagroup)."""
    from telethon.types import Channel
    if isinstance(entity, Channel):
        # Only broadcast channels, not megagroups
        return not entity.megagroup
    return False


def chat_is_broadcast(entity):
    """Alias for chat_is_channel - check if entity is a broadcast channel."""
    return chat_is_channel(entity)


def get_chat_type(entity):
    """Get the type of chat as a string."""
    if chat_is_bot(entity):
        return "bot"
    elif chat_is_private(entity):
        return "private"
    elif chat_is_group(entity):
        return "group"
    elif chat_is_channel(entity):
        return "channel"
    return "unknown"


def get_peer_id(peer):
    """Extract ID from different InputPeer types."""
    if hasattr(peer, "user_id"):
        return peer.user_id
    elif hasattr(peer, "chat_id"):
        return peer.chat_id
    elif hasattr(peer, "channel_id"):
        return peer.channel_id
    return None


def chat_is_in_folder(dialog, folder):
    """
    Check if a dialog/chat is in a specific folder.

    Args:
        dialog: Telethon dialog object (has .entity property)
        folder: Telegram folder/filter object

    Returns:
        bool: True if chat is in folder, False otherwise
    """
    entity = dialog.entity
    entity_id = entity.id

    # Collect included and excluded peer IDs
    included_ids = set()
    excluded_ids = set()

    # Check include_peers (explicitly added chats)
    for peer in getattr(folder, "include_peers", []):
        peer_id = get_peer_id(peer)
        if peer_id:
            included_ids.add(peer_id)

    # Check pinned_peers (also explicitly included)
    for peer in getattr(folder, "pinned_peers", []):
        peer_id = get_peer_id(peer)
        if peer_id:
            included_ids.add(peer_id)

    # Check exclude_peers
    for peer in getattr(folder, "exclude_peers", []):
        peer_id = get_peer_id(peer)
        if peer_id:
            excluded_ids.add(peer_id)

    # First check: if explicitly excluded, not in folder
    if entity_id in excluded_ids:
        return False

    # Second check: if explicitly included or pinned, definitely in folder
    if entity_id in included_ids:
        return True

    # Third check: Apply filter flags (these work alongside pinned/included peers)
    if getattr(folder, "bots", False) and chat_is_bot(entity):
        pass  # Will check exclusion filters below
    elif getattr(folder, "broadcasts", False) and chat_is_channel(entity):
        pass  # Will check exclusion filters below
    elif getattr(folder, "groups", False) and chat_is_group(entity):
        pass  # Will check exclusion filters below
    elif getattr(folder, "contacts", False) and chat_is_private(entity):
        # Note: We can't easily determine if user is a contact from entity alone
        # This would require additional API calls or context
        # For now, we'll include all private chats when contacts filter is on
        pass  # Will check exclusion filters below
    elif getattr(folder, "non_contacts", False) and chat_is_private(entity):
        # Same limitation as contacts
        pass  # Will check exclusion filters below
    else:
        # Doesn't match any filter
        return False

    # Apply exclusion filters (muted, read, archived)
    if getattr(folder, "exclude_muted", False):
        if hasattr(dialog, "dialog") and dialog.dialog.mute_until:
            return False

    if getattr(folder, "exclude_read", False):
        if hasattr(dialog, "unread_count") and dialog.unread_count == 0:
            return False

    if getattr(folder, "exclude_archived", False):
        if hasattr(dialog, "archived") and dialog.archived:
            return False

    return True


def get_folder_stats(dialogs, folder):
    """
    Get statistics for a folder.

    Args:
        dialogs: List of Telethon dialog objects
        folder: Telegram folder/filter object

    Returns:
        dict: Statistics including counts by type
    """
    stats = {
        "total": 0,
        "bots": 0,
        "private": 0,
        "groups": 0,
        "channels": 0,
        "unread_total": 0,
    }

    for dialog in dialogs:
        if chat_is_in_folder(dialog, folder):
            stats["total"] += 1

            entity = dialog.entity
            if chat_is_bot(entity):
                stats["bots"] += 1
            elif chat_is_private(entity):
                stats["private"] += 1
            elif chat_is_group(entity):
                stats["groups"] += 1
            elif chat_is_channel(entity):
                stats["channels"] += 1

            # Add unread count
            if hasattr(dialog, "unread_count"):
                stats["unread_total"] += dialog.unread_count or 0

    return stats
