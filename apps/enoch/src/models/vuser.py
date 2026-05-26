"""Custom user settings."""

from typing import Optional

from async_lru import alru_cache
from pydantic import BaseModel, Field
from sqlalchemy import text

from storage import get_engine


class VUserSettings(BaseModel):
    """Represents individual user settings."""

    accessibility: bool = False

    @property
    def use_emojis(self) -> bool:
        """Whether to use emojis. Inverse of accessibility."""
        return not self.accessibility


class VUser(BaseModel):
    """Represents a user and their settings."""

    # Database primary key (None until inserted)
    id: Optional[int] = None

    user: int
    settings: VUserSettings = Field(default_factory=VUserSettings)

    # ------------------------------------------------------------------
    # SQLAlchemy persistence
    # ------------------------------------------------------------------

    async def save(self):
        """Insert or update this user in the database."""
        async with get_engine().begin() as conn:
            if self.id is None:
                result = await conn.execute(
                    text("""
                        INSERT INTO inconnu_users (user, settings)
                        VALUES (:user, :settings)
                    """),
                    {"user": self.user, "settings": self.settings.model_dump_json()},
                )
                self.id = result.lastrowid
            else:
                await conn.execute(
                    text("""
                        UPDATE inconnu_users
                        SET user=:user, settings=:settings
                        WHERE id=:id
                    """),
                    {"id": self.id, "user": self.user, "settings": self.settings.model_dump_json()},
                )

    @classmethod
    @alru_cache(maxsize=1024)
    async def get_or_fetch(cls, id: int) -> "VUser":
        """Return a cached VUser, fetch it from the database, or create a new one."""
        async with get_engine().connect() as conn:
            result = await conn.execute(
                text("SELECT * FROM inconnu_users WHERE user=:user"),
                {"user": id},
            )
            row = result.mappings().first()

        if row is None:
            return cls(user=id)

        obj = cls(
            user=row["user"],
            settings=VUserSettings.model_validate_json(row["settings"] or "{}"),
        )
        obj.id = row["id"]
        return obj
