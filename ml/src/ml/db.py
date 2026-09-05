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
    UniqueConstraint,
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

# Thumbs up/down on "My Games" puzzles (backend's PuzzleFeedback entity) — the
# label a future puzzle-quality model trains against, joined to this table's
# PersonalPuzzleCandidate rows via puzzle.external_id (see that model's
# docstring). Doctrine-owned like the tables above; ml/ only ever reads it.
puzzle_feedback_table = Table(
    "puzzle_feedback",
    external_metadata,
    Column("id", Integer, primary_key=True),
    Column("thumbs_up", Boolean, nullable=False),
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


class GameImportProgress(Base):
    """
    One row per user — tracks where a "My Games" chess.com import scan has
    gotten to, so a second `start` call resumes instead of re-scanning from
    scratch (see game_import.py). ml/-owned, same boundary as above: backend
    never queries this directly, only through ml/'s HTTP endpoints.
    """

    __tablename__ = "game_import_progress"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    chess_com_username = Column(String(255), nullable=False)
    status = Column(String(16), nullable=False, default="idle")
    games_processed = Column(Integer, nullable=False, default=0)
    puzzles_found = Column(Integer, nullable=False, default=0)
    # e.g. "2026/08" — the oldest archive month scanned so far, so a resumed
    # run continues further back rather than re-scanning recent months.
    last_archive = Column(String(16), nullable=True)
    error_message = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False)


class PersonalPuzzleCandidate(Base):
    """
    A blunder-derived puzzle found by a "My Games" scan, waiting for
    backend/ to pick it up and persist it as a real `Puzzle` row (ml/ never
    writes to `puzzle` itself — see this module's docstring). `delivered`
    flips true once a status poll has returned it; backend's own dedup by
    `external_id` is the final safety net against double-inserting on
    at-least-once delivery.
    """

    __tablename__ = "personal_puzzle_candidate"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    fen = Column(String(100), nullable=False)
    # JSON-encoded array of UCI moves, same shape/convention as Puzzle.solution.
    solution = Column(Text, nullable=False)
    rating = Column(Integer, nullable=False)
    # e.g. "chesscom:{game_id}:{ply}" — backend's dedup key. Also the join key
    # a future puzzle-quality model uses to line these features up with the
    # thumbs up/down label sitting in backend's puzzle_feedback table (see
    # CLAUDE.md's Phase 2.5 note) — read via db.py's external_metadata, same
    # as puzzle/puzzle_attempt already are.
    external_id = Column(String(255), nullable=False, unique=True)
    # Puzzle-quality signals from puzzle_quality.py's analysis, not (yet)
    # used to filter candidates. Nullable because candidates found before
    # these columns existed have no value to backfill.
    forced = Column(Boolean, nullable=True)
    refutation_gap_cp = Column(Integer, nullable=True)
    setup_swing_cp = Column(Integer, nullable=True)
    delivered = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False)


class PuzzleQualityTrainingExample(Base):
    """
    A sampled, already-published Lichess puzzle scored with the same
    puzzle_quality.py features as our own PersonalPuzzleCandidate rows, paired
    with Lichess's own crowd-sourced quality signal (Popularity/NbPlays from
    the raw CSV — see build_training_dataset.py) as the label. Bootstraps a
    puzzle-quality model off a much larger, already-collected vote history
    than our own thumbs up/down feedback could produce for a long while;
    `source`/`external_id` leave room for a later batch of examples derived
    from our own puzzle_feedback votes to live in this same table.
    """

    __tablename__ = "puzzle_quality_training_example"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_quality_example_source_external_id"),)

    id = Column(Integer, primary_key=True)
    # "lichess" for now; a future "personal" batch (sourced from our own
    # puzzle_feedback table) would use this same table with a different value.
    source = Column(String(16), nullable=False)
    # The Lichess PuzzleId for a "lichess"-sourced row — this table's own
    # dedup key (alongside `source`), not a join key into our `puzzle` table
    # (most sampled rows were never imported into it).
    external_id = Column(String(255), nullable=False)
    fen = Column(String(100), nullable=False)
    setup_move = Column(String(8), nullable=False)
    rating = Column(Integer, nullable=False)
    setup_swing_cp = Column(Integer, nullable=False)
    forced = Column(Boolean, nullable=False)
    refutation_gap_cp = Column(Integer, nullable=True)
    # Raw label source: Lichess's aggregated (+1/-1) vote score, roughly
    # -100..100, and the play count behind it — kept raw rather than
    # pre-binarized so the training script can choose its own label
    # threshold (or use nb_plays as a confidence weight) without a re-scan.
    popularity = Column(Integer, nullable=False)
    nb_plays = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)
