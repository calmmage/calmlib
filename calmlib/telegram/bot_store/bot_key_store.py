from datetime import datetime
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field
from pymongo import MongoClient


class BotStatus(str, Enum):
    FREE = "free"
    BUSY = "busy"


class BotKey(BaseModel):
    token: str = Field(..., description="Telegram bot token")
    username: str = Field(..., description="Bot username (without @)")
    owner: str = Field(..., description="Owner of the bot")
    status: BotStatus = Field(default=BotStatus.FREE, description="Current status")
    used_by: Optional[str] = Field(default=None, description="Project/tool currently using this bot")
    created_at: datetime = Field(default_factory=datetime.now)
    last_used_at: Optional[datetime] = Field(default=None)
    
    class Config:
        use_enum_values = True


class BotKeyStore:
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017", db_name: str = "calmmage"):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db.telegram_bot_keys
        
        # Create indexes for better performance
        self.collection.create_index("username", unique=True)
        self.collection.create_index("token", unique=True)
        self.collection.create_index("status")
    
    def add_bot_key(self, token: str, username: str, owner: str) -> BotKey:
        """Add a new bot key to the store."""
        bot_key = BotKey(token=token, username=username, owner=owner)
        
        # Insert into MongoDB
        result = self.collection.insert_one(bot_key.model_dump())
        
        return bot_key
    
    def get_free_key(self, used_by: str) -> Optional[BotKey]:
        """Get the first available free bot key and mark it as busy."""
        # Find a free bot and update it to busy in one atomic operation
        result = self.collection.find_one_and_update(
            {"status": BotStatus.FREE.value},
            {
                "$set": {
                    "status": BotStatus.BUSY.value,
                    "used_by": used_by,
                    "last_used_at": datetime.now()
                }
            },
            return_document=True
        )
        
        if result:
            return BotKey(**result)
        return None
    
    def release_key(self, username: str) -> bool:
        """Release a bot key back to the free pool."""
        result = self.collection.update_one(
            {"username": username},
            {
                "$set": {
                    "status": BotStatus.FREE.value,
                    "used_by": None
                }
            }
        )
        return result.modified_count > 0
    
    def get_free_key_count(self) -> int:
        """Get the count of free bot keys."""
        return self.collection.count_documents({"status": BotStatus.FREE.value})
    
    def get_busy_key_count(self) -> int:
        """Get the count of busy bot keys."""
        return self.collection.count_documents({"status": BotStatus.BUSY.value})
    
    def get_all_keys(self) -> List[BotKey]:
        """Get all bot keys."""
        results = self.collection.find()
        return [BotKey(**result) for result in results]
    
    def get_keys_by_status(self, status: BotStatus) -> List[BotKey]:
        """Get all bot keys with a specific status."""
        results = self.collection.find({"status": status.value})
        return [BotKey(**result) for result in results]
    
    def get_key_by_username(self, username: str) -> Optional[BotKey]:
        """Get a specific bot key by username."""
        result = self.collection.find_one({"username": username})
        if result:
            return BotKey(**result)
        return None
    
    def delete_key(self, username: str) -> bool:
        """Delete a bot key from the store."""
        result = self.collection.delete_one({"username": username})
        return result.deleted_count > 0
    
    def close(self):
        """Close the MongoDB connection."""
        self.client.close()