"""Rolepost models."""

import json
from datetime import UTC, datetime, timezone
from typing import TYPE_CHECKING, Optional

import discord
from pydantic import AnyUrl, BaseModel, Field
from sqlalchemy import text

from models.rpheader import HeaderSubdoc
from storage import get_engine

if TYPE_CHECKING:
    from models import VChar


class PostHistoryEntry(BaseModel):
    """Represents historic post content and a date of modification."""

    date: datetime
    content: str


class _EmptyAsyncCursor:
    """An empty async cursor stub returned by RPPost.find() until search is ported."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration

    def sort(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self


class RPPost(BaseModel):
    """Represents a Rolepost with the ability to maintain deltas."""

    # Database primary key (None until inserted)
    id: Optional[int] = None

    # Metadata
    date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    date_modified: Optional[datetime] = None
    guild: int
    channel: int
    user: int
    message_id: int
    url: Optional[AnyUrl]
    deleted: bool = False
    deletion_date: Optional[datetime] = None
    id_chain: list[int] = Field(default_factory=list)

    # Content
    header: HeaderSubdoc
    content: str
    mentions: list[int] = Field(default_factory=list)
    history: list[PostHistoryEntry] = Field(default_factory=list)

    # Custom
    title: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

    @property
    def utc_date(self) -> datetime:
        """The UTC-aware post date."""
        return self.date.replace(tzinfo=timezone.utc)

    @classmethod
    def new(
        cls,
        *,
        interaction: discord.Interaction,
        character: "VChar",
        header: HeaderSubdoc,
        content: str,
        message: discord.Message,
        mentions: list[int],
        title: str | None,
        tags: list[str],
    ):
        """Create a Rolepost."""
        if interaction.channel_id is None:
            raise ValueError("Interaction channel has no ID")
        if interaction.user is None:
            raise ValueError("Interaction user does not exist")

        return cls(
            guild=character.guild,
            channel=interaction.channel_id,
            user=interaction.user.id,
            message_id=message.id,
            header=header,
            content=content,
            url=AnyUrl(message.jump_url),
            mentions=mentions,
            title=title,
            tags=tags,
        )

    def edit_post(self, new_post: str):
        """Update the post content, if necessary."""
        if new_post != self.content:
            # We only bother with this if the post was actually changed
            entry = PostHistoryEntry(
                date=self.date_modified or self.date,
                content=self.content,
            )
            self.history.insert(0, entry)
            self.content = new_post
            self.date_modified = datetime.now(UTC)

    # ------------------------------------------------------------------
    # SQLAlchemy persistence
    # ------------------------------------------------------------------

    def _to_row_params(self) -> dict:
        """Serialize fields for SQL parameter binding."""
        return {
            "date": self.date.isoformat() if self.date else "",
            "date_modified": self.date_modified.isoformat() if self.date_modified else "",
            "guild": self.guild,
            "channel": self.channel,
            "user": self.user,
            "message_id": self.message_id,
            "url": str(self.url) if self.url else "",
            "deleted": int(self.deleted),
            "deletion_date": self.deletion_date.isoformat() if self.deletion_date else "",
            "id_chain": json.dumps(self.id_chain),
            "header": self.header.model_dump_json(),
            "content": self.content,
            "mentions": json.dumps(self.mentions),
            "history": json.dumps([h.model_dump(mode="json") for h in self.history]),
            "title": self.title or "",
            "tags": json.dumps(self.tags),
        }

    @classmethod
    def from_row(cls, row) -> "RPPost":
        """Deserialize from a database row mapping."""
        obj = cls(
            date=datetime.fromisoformat(row["date"]) if row["date"] else datetime.now(UTC),
            date_modified=datetime.fromisoformat(row["date_modified"])
            if row["date_modified"]
            else None,
            guild=row["guild"],
            channel=row["channel"],
            user=row["user"],
            message_id=row["message_id"],
            url=AnyUrl(row["url"]) if row["url"] else None,
            deleted=bool(row["deleted"]),
            deletion_date=datetime.fromisoformat(row["deletion_date"])
            if row["deletion_date"]
            else None,
            id_chain=json.loads(row["id_chain"] or "[]"),
            header=HeaderSubdoc.model_validate_json(row["header"] or "{}"),
            content=row["content"] or "",
            mentions=json.loads(row["mentions"] or "[]"),
            history=[
                PostHistoryEntry.model_validate(e)
                for e in json.loads(row["history"] or "[]")
            ],
            title=row["title"] or None,
            tags=json.loads(row["tags"] or "[]"),
        )
        obj.id = row["id"]
        return obj

    async def insert(self):
        """Insert this RPPost into the database and set self.id."""
        async with get_engine().begin() as conn:
            result = await conn.execute(
                text("""
                    INSERT INTO inconnu_rp_posts
                        (date, date_modified, guild, channel, user, message_id, url,
                         deleted, deletion_date, id_chain, header, content, mentions,
                         history, title, tags)
                    VALUES
                        (:date, :date_modified, :guild, :channel, :user, :message_id, :url,
                         :deleted, :deletion_date, :id_chain, :header, :content, :mentions,
                         :history, :title, :tags)
                """),
                self._to_row_params(),
            )
            self.id = result.lastrowid

    async def save(self):
        """Persist current state to the database."""
        params = self._to_row_params()
        params["id"] = self.id
        async with get_engine().begin() as conn:
            await conn.execute(
                text("""
                    UPDATE inconnu_rp_posts
                    SET date=:date, date_modified=:date_modified,
                        guild=:guild, channel=:channel, user=:user,
                        message_id=:message_id, url=:url,
                        deleted=:deleted, deletion_date=:deletion_date,
                        id_chain=:id_chain, header=:header, content=:content,
                        mentions=:mentions, history=:history, title=:title, tags=:tags
                    WHERE id=:id
                """),
                params,
            )

    @classmethod
    async def find_by_id(cls, oid: int) -> "RPPost | None":
        """Fetch an RPPost by its primary key."""
        async with get_engine().connect() as conn:
            result = await conn.execute(
                text("SELECT * FROM inconnu_rp_posts WHERE id=:id"),
                {"id": oid},
            )
            row = result.mappings().first()
        return cls.from_row(row) if row else None

    @classmethod
    async def find_one(cls, query: dict) -> "RPPost | None":
        """Find a single RPPost by a simple equality query.

        Supported keys: ``id``, ``message_id``.
        All other queries return None (stub until fully ported).
        """
        if not isinstance(query, dict):
            return None
        if "id" in query:
            return await cls.find_by_id(query["id"])
        if "message_id" in query:
            async with get_engine().connect() as conn:
                result = await conn.execute(
                    text("SELECT * FROM inconnu_rp_posts WHERE message_id=:mid"),
                    {"mid": query["message_id"]},
                )
                row = result.mappings().first()
            return cls.from_row(row) if row else None
        # Complex/unsupported queries — stub
        return None

    @classmethod
    def find(cls, query: dict) -> _EmptyAsyncCursor:
        """Return an empty async cursor (search not yet ported from MongoDB)."""
        return _EmptyAsyncCursor()
