"""
Two separate MetaData objects, deliberately not combined — see CLAUDE.md's
ml/ section and the design doc's "ownership boundary" callout:

- `external_metadata` describes tables backend/ owns (Doctrine is the source
  of truth for their shape). ml/ only ever reads them. Never pass this to
  Alembic — ml/ must never generate a migration that touches backend/'s schema.
- `Base.metadata` (below) is ml/'s own — currently just `user_pattern_weakness`.
  This is the only metadata Alembic autogenerates against.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ml.config import settings

engine = create_engine(settings.resolved_database_url)
SessionLocal = sessionmaker(bind=engine)

external_metadata = MetaData()

user_table = Table(
    "user",
    external_metadata,
    Column("id", Integer, primary_key=True),
    Column("rating", Integer, nullable=False),
)

puzzle_table = Table(
    "puzzle",
    external_metadata,
    Column("id", Integer, primary_key=True),
    Column("rating", Integer, nullable=False),
    # JSON-encoded array of Lichess theme tags, e.g. ["fork","middlegame"].
    # Stored as JSON text regardless of engine (SQLite CLOB / MySQL JSON) —
    # Doctrine's #[ORM\Column] on an `array`-typed property maps to JSON.
    Column("themes", Text, nullable=True),
)

puzzle_attempt_table = Table(
    "puzzle_attempt",
    external_metadata,
    Column("id", Integer, primary_key=True),
    Column("success", Boolean, nullable=False),
    Column("user_id", Integer, ForeignKey("user.id"), nullable=False),
    Column("puzzle_id", Integer, ForeignKey("puzzle.id"), nullable=False),
)


class Base(DeclarativeBase):
    pass


class UserPatternWeakness(Base):
    """
    ml/-owned — no Doctrine entity or backend/ migration ever mentions this
    table. `PuzzleSelectionService` never queries it directly either; it goes
    through ml/'s recommendation endpoint, per the architecture boundary in
    the design doc.
    """

    __tablename__ = "user_pattern_weakness"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    theme = Column(String(64), nullable=False)
    miss_rate_vs_expected = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)
    computed_at = Column(DateTime, nullable=False)
