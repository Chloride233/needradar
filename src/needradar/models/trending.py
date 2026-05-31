import enum

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from needradar.models.base import Base, TimestampMixin


class TrendingSince(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class TrendingProject(TimestampMixin, Base):
    __tablename__ = "trending_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(50), default="", index=True)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    period_stars: Mapped[int] = mapped_column(Integer, default=0)
    since: Mapped[str] = mapped_column(String(20), index=True)
    contributors: Mapped[str] = mapped_column(Text, default="")  # comma-separated logins
    tags: Mapped[str] = mapped_column(Text, default="")  # comma-separated auto-generated tags
    snapshot_date: Mapped[str] = mapped_column(String(20), index=True)  # YYYY-MM-DD
    is_analyzed: Mapped[bool] = mapped_column(Boolean, default=False)
