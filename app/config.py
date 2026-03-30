from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(..., alias="BOT_TOKEN")
    support_group_id: int = Field(..., alias="SUPPORT_GROUP_ID")
    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    ticket_id_offset: int = Field(default=100000, alias="TICKET_ID_OFFSET")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO", alias="LOG_LEVEL")
    staff_seed_ids: str | None = Field(default=None, alias="STAFF_SEED_IDS")

    @property
    def parsed_staff_seed_ids(self) -> list[int]:
        if not self.staff_seed_ids:
            return []

        result: list[int] = []
        for raw_value in self.staff_seed_ids.split(","):
            value = raw_value.strip()
            if not value:
                continue
            result.append(int(value))
        return result


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
