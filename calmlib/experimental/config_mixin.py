from pydantic import BaseSettings
from typing import Type


class ConfigMixin:
    config_type: Type[BaseSettings]

    def __init__(self, **kwargs):
        self.config = self.config_type(**kwargs)
        super().__init__(**kwargs)
