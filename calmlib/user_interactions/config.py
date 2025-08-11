"""
Singleton configuration for user interaction engines
"""
from typing import Optional, Dict, Any
from .engines import UserInteractionEngine, PythonInputEngine


class UserInteractionConfig:
    """Singleton configuration for user interaction system"""
    
    _instance: Optional['UserInteractionConfig'] = None
    _engine: Optional[UserInteractionEngine] = None
    _engine_params: Dict[str, Any] = {}
    
    def __new__(cls) -> 'UserInteractionConfig':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def set_engine(self, engine: UserInteractionEngine, **params) -> None:
        """Set the current user interaction engine"""
        self._engine = engine
        self._engine_params = params
    
    def get_engine(self) -> UserInteractionEngine:
        """Get the current user interaction engine, creating default if none set"""
        if self._engine is None:
            self._engine = PythonInputEngine()
        return self._engine
    
    def get_engine_params(self) -> Dict[str, Any]:
        """Get parameters for the current engine"""
        return self._engine_params.copy()
    
    def reset(self) -> None:
        """Reset to default engine (mainly for testing)"""
        self._engine = None
        self._engine_params = {}


# Global singleton instance
_config = UserInteractionConfig()