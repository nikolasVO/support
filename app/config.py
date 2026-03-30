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
    waiting_user_timeout_hours: int = Field(default=48, alias="WAITING_USER_TIMEOUT_HOURS")
    autoclose_check_interval_seconds: int = Field(default=120, alias="AUTOCLOSE_CHECK_INTERVAL_SECONDS")
    staff_name_map: str | None = Field(default=None, alias="STAFF_NAME_MAP")

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

    @property
    def parsed_staff_name_map(self) -> dict[int, str]:
        if not self.staff_name_map:
            return {}

        mapping: dict[int, str] = {}
        for raw_pair in self.staff_name_map.split(","):
            pair = raw_pair.strip()
            if not pair or ":" not in pair:
                continue
            staff_id_raw, name_raw = pair.split(":", 1)
            staff_id = staff_id_raw.strip()
            display_name = name_raw.strip()
            if not staff_id or not display_name:
                continue
            mapping[int(staff_id)] = display_name
        return mapping


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
