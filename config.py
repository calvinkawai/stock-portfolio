from functools import lru_cache
from typing import Annotated

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    REGISTER_KEY: str

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings():
    return Settings()

settings = get_settings()
