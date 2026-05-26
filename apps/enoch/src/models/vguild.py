"""models/vguild.py - Guild-wide settings class."""

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Optional

from async_lru import alru_cache
from discord import Guild
from pydantic import BaseModel, Field
from sqlalchemy import text

from storage import get_engine


def utcnow() -> datetime:
    """Gets the current UTC time as a naive datetime."""
    return datetime.now(UTC).replace(tzinfo=None)


class ExpPerms(StrEnum):
    """An enum for experience adjustment permissions."""

    UNRESTRICTED = "unrestricted"
    UNSPENT_ONLY = "unspent_only"
    LIFETIME_ONLY = "lifetime_only"
    ADMIN_ONLY = "admin_only"

    @property
    def description(self) -> str:
        """Human-readable description."""
        match self:
            case ExpPerms.UNRESTRICTED:
                return "Players can adjust unspent and lifetime XP"
            case ExpPerms.UNSPENT_ONLY:
                return "Players can adjust unspent XP only"
            case ExpPerms.LIFETIME_ONLY:
                return "Players can adjust lifetime XP only"
            case ExpPerms.ADMIN_ONLY:
                return "Only admins can adjust XP"


class ResonanceMode(StrEnum):
    """An enum for a guild's Resonance setting."""

    STANDARD = "standard"
    TATTERED_FACADE = "tattered_facade"  # Resonance chart per Tattered Facade
    ADD_EMPTY = "add_empty"  # Custom: Fifth probability for Empty Resonance

    @property
    def description(self) -> str:
        """Human-readable description."""
        match self:
            case ResonanceMode.STANDARD:
                return "Use V5 core distribution"
            case ResonanceMode.TATTERED_FACADE:
                return "Use alternate distribution from Tattered Facade"
            case ResonanceMode.ADD_EMPTY:
                return "Add 16.7% chance for Empty Resonance"

    @property
    def short(self) -> str:
        """Short description."""
        match self:
            case ResonanceMode.STANDARD:
                return "Using standard V5 distribution."
            case ResonanceMode.TATTERED_FACADE:
                return "Using Tattered Facade distribution."
            case ResonanceMode.ADD_EMPTY:
                return "Using standard distribution with small chance for Empty Resonance."


class VGuildSettings(BaseModel):
    """Represents an individual guild's settings."""

    accessibility: bool = False
    experience_permissions: ExpPerms = ExpPerms.UNRESTRICTED
    oblivion_stains: list[int] = Field(default_factory=lambda: [1, 10])
    update_channel: Optional[int] = None
    changelog_channel: Optional[int] = None
    deletion_channel: Optional[int] = None
    add_empty_resonance: bool = False
    resonance: ResonanceMode = ResonanceMode.STANDARD
    max_hunger: int = Field(ge=5, le=10, default=5)

    @property
    def use_emojis(self) -> bool:
        """Whether to use emojis. Inverse of accessibility."""
        return not self.accessibility


class VGuild(BaseModel):
    """Represents a guild and its settings."""

    # Database primary key (None until inserted)
    id: Optional[int] = None

    guild: int
    name: str
    active: bool = True
    joined: datetime = Field(default_factory=utcnow)
    left: Optional[datetime] = None
    settings: VGuildSettings = Field(default_factory=VGuildSettings)

    def join(self):
        """Register the join date."""
        self.joined = utcnow()

    def leave(self):
        """Register the left date."""
        self.left = utcnow()

    # ------------------------------------------------------------------
    # SQLAlchemy persistence
    # ------------------------------------------------------------------

    def _to_row_params(self) -> dict:
        """Serialize fields for SQL parameter binding."""
        return {
            "guild": self.guild,
            "name": self.name,
            "active": int(self.active),
            "joined": self.joined.isoformat() if self.joined else "",
            "left": self.left.isoformat() if self.left else "",
            "settings": self.settings.model_dump_json(),
        }

    @classmethod
    def from_row(cls, row) -> "VGuild":
        """Deserialize from a database row mapping."""
        joined_str = row["joined"] or ""
        left_str = row["left"] or ""
        obj = cls(
            guild=row["guild"],
            name=row["name"],
            active=bool(row["active"]),
            joined=datetime.fromisoformat(joined_str) if joined_str else utcnow(),
            left=datetime.fromisoformat(left_str) if left_str else None,
            settings=VGuildSettings.model_validate_json(row["settings"] or "{}"),
        )
        obj.id = row["id"]
        return obj

    async def save(self):
        """Insert or update this guild in the database."""
        async with get_engine().begin() as conn:
            if self.id is None:
                result = await conn.execute(
                    text("""
                        INSERT INTO inconnu_guilds (guild, name, active, joined, left, settings)
                        VALUES (:guild, :name, :active, :joined, :left, :settings)
                    """),
                    self._to_row_params(),
                )
                self.id = result.lastrowid
            else:
                await conn.execute(
                    text("""
                        UPDATE inconnu_guilds
                        SET guild=:guild, name=:name, active=:active,
                            joined=:joined, left=:left, settings=:settings
                        WHERE id=:id
                    """),
                    {"id": self.id, **self._to_row_params()},
                )

    @classmethod
    @alru_cache(maxsize=1024)
    async def get_or_fetch(cls, guild: Guild | None) -> "VGuild":
        """Return a cached VGuild, fetch it from the database, or create a new one."""
        if guild is None:
            return VGuild(guild=0, name="DMs")

        async with get_engine().connect() as conn:
            result = await conn.execute(
                text("SELECT * FROM inconnu_guilds WHERE guild=:guild"),
                {"guild": guild.id},
            )
            row = result.mappings().first()

        if row is None:
            vguild = cls(guild=guild.id, name=guild.name)
            await vguild.save()
            return vguild

        return cls.from_row(row)
