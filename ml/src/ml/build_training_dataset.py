"""
Builds PuzzleQualityTrainingExample rows from a sample of Lichess's own
published puzzle database, scored with the same puzzle_quality.py features
game_import.py computes for our own candidates. Lichess's `Popularity`
column (aggregated +1/-1 votes from their users) is the label — the same
kind of signal as our own puzzle_feedback thumbs up/down, just already
collected at a scale ours won't reach for a long while (see CLAUDE.md's
Phase 2.5 note).

Run via `uv run python -m ml.build_training_dataset`. Downloads
lichess_db_puzzle.csv.zst into ml/var/ if it isn't already there (a ~290MB
file, gitignored — see database.lichess.org/#puzzles) and streams it through
zstandard rather than decompressing to disk first; a uniform reservoir
sample keeps this from favoring whatever happens to be early in the file.
"""

import argparse
import csv
import io
import logging
import random
from datetime import datetime, timezone
from pathlib import Path

import chess.engine
import httpx
import zstandard
from sqlalchemy import select

from ml.config import settings
from ml.db import PuzzleQualityTrainingExample, SessionLocal
from ml.puzzle_quality import analyse_puzzle_quality

logger = logging.getLogger(__name__)

_CSV_URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
_DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent.parent / "var" / "lichess_db_puzzle.csv.zst"


def download_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading %s to %s", _CSV_URL, path)
    with httpx.stream("GET", _CSV_URL, timeout=120.0, follow_redirects=True) as response:
        response.raise_for_status()
        with open(path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)


def stream_rows(csv_path: Path):
    """Yields CSV rows (as dicts) without ever holding the decompressed file in memory or on disk."""
    with open(csv_path, "rb") as compressed:
        reader = zstandard.ZstdDecompressor().stream_reader(compressed)
        text_stream = io.TextIOWrapper(reader, encoding="utf-8")
        yield from csv.DictReader(text_stream)


def reservoir_sample(rows, sample_size: int, seed: int) -> list[dict]:
    """Algorithm R — a uniform random sample of a stream of unknown length, in one pass."""
    rng = random.Random(seed)
    sample: list[dict] = []
    for i, row in enumerate(rows):
        if i < sample_size:
            sample.append(row)
        else:
            j = rng.randint(0, i)
            if j < sample_size:
                sample[j] = row
    return sample


def build_dataset(
    sample: list[dict],
    engine: chess.engine.SimpleEngine,
    *,
    depth: int,
    forced_gap_cp: int,
) -> tuple[int, int]:
    """
    Scores an already-sampled list of Lichess CSV rows (dicts keyed by the
    CSV header) and upserts them as PuzzleQualityTrainingExample rows.
    Returns (examples_added, examples_skipped).
    """
    session = SessionLocal()
    added = 0
    skipped = 0
    try:
        for row in sample:
            lichess_id = row["PuzzleId"]
            existing = session.execute(
                select(PuzzleQualityTrainingExample).where(
                    PuzzleQualityTrainingExample.source == "lichess",
                    PuzzleQualityTrainingExample.external_id == lichess_id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue

            moves = row["Moves"].split(" ")
            setup_move = moves[0]

            analysis = analyse_puzzle_quality(
                row["FEN"], setup_move, engine, depth=depth, forced_gap_cp=forced_gap_cp
            )
            if analysis is None:
                skipped += 1
                continue

            session.add(
                PuzzleQualityTrainingExample(
                    source="lichess",
                    external_id=lichess_id,
                    fen=row["FEN"],
                    setup_move=setup_move,
                    rating=int(row["Rating"]),
                    setup_swing_cp=analysis.setup_swing_cp,
                    forced=analysis.forced,
                    refutation_gap_cp=analysis.refutation_gap_cp,
                    popularity=int(row["Popularity"]),
                    nb_plays=int(row["NbPlays"]),
                    created_at=datetime.now(timezone.utc),
                )
            )
            added += 1
            if added % 50 == 0:
                session.commit()
                logger.info("  ...%d examples added so far", added)

        session.commit()
    finally:
        session.close()

    return added, skipped


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--depth", type=int, default=10, help="Lower than the live import's depth (12) — this runs Stockfish on many more positions offline, where speed matters more than the last bit of accuracy")
    parser.add_argument("--forced-gap-cp", type=int, default=settings.forced_gap_cp)
    parser.add_argument("--csv-path", type=Path, default=_DEFAULT_CSV_PATH)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if not args.csv_path.exists():
        download_csv(args.csv_path)

    logger.info("Sampling %d rows from %s...", args.sample_size, args.csv_path)
    sample = reservoir_sample(stream_rows(args.csv_path), args.sample_size, args.seed)
    logger.info("Sampled %d puzzles, scoring with Stockfish (depth=%d)...", len(sample), args.depth)

    engine = chess.engine.SimpleEngine.popen_uci(settings.stockfish_path)
    try:
        added, skipped = build_dataset(
            sample,
            engine,
            depth=args.depth,
            forced_gap_cp=args.forced_gap_cp,
        )
    finally:
        engine.quit()

    logger.info("Done — %d examples added, %d skipped (no legal moves at sampled position).", added, skipped)


if __name__ == "__main__":
    main()
