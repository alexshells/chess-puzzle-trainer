"""
Builds PuzzleQualityTrainingExample rows (source="personal") from real
`PuzzleFeedback` votes on a user's own "My Games" puzzles — scored with the
exact same puzzle_quality.py features build_training_dataset.py computes for
a Lichess row, so puzzle_quality_model.py can train on both together (see
that model's extract_labels()/extract_weights() for how the two sources are
blended). This is the real, directly-relevant signal Lichess popularity has
always been a bootstrap proxy for (see CLAUDE.md's Phase 2.5 note) — no
crowd-of-strangers gap, since it's feedback on the exact kind of candidate
this pipeline generates.

Reads straight from the live database via db.py's external_metadata tables
(puzzle/puzzle_feedback — Doctrine-owned, ml/ only ever reads them), no CSV
involved. Volume here will be tiny compared to the Lichess sample for a
long while, so this defaults to the live-import depth (more accuracy per
position, since there's so much less of it to score) rather than
build_training_dataset.py's lower bulk-sampling depth.

Run via `uv run python -m ml.build_personal_feedback_dataset`.
"""

import argparse
import json
import logging
from datetime import datetime, timezone

import chess.engine
from sqlalchemy import select

from ml import tablebase
from ml.config import settings
from ml.db import PuzzleQualityTrainingExample, SessionLocal, puzzle_feedback_table, puzzle_table
from ml.puzzle_quality import analyse_puzzle_quality

logger = logging.getLogger(__name__)


def build_dataset(
    engine: chess.engine.SimpleEngine,
    *,
    depth: int,
    forced_win_chance_gap: float,
    decisive_material_gain: int,
) -> tuple[int, int]:
    """
    Scores every PuzzleFeedback row that isn't already represented as a
    PuzzleQualityTrainingExample and upserts it. Returns (examples_added,
    examples_skipped) — same shape as build_training_dataset.build_dataset().
    """
    session = SessionLocal()
    added = 0
    skipped = 0
    try:
        rows = session.execute(
            select(
                puzzle_feedback_table.c.stars,
                puzzle_table.c.id,
                puzzle_table.c.fen,
                puzzle_table.c.solution,
                puzzle_table.c.rating,
                puzzle_table.c.external_id,
            ).select_from(puzzle_feedback_table.join(puzzle_table, puzzle_feedback_table.c.puzzle_id == puzzle_table.c.id))
        ).all()

        for stars, puzzle_id, fen, solution_json, rating, external_id in rows:
            if external_id is None:
                # Shouldn't happen for a real personal puzzle in practice
                # (every one gets an external_id at creation — see Puzzle's
                # class doc) — skip defensively rather than fabricate a key.
                skipped += 1
                continue

            existing = session.execute(
                select(PuzzleQualityTrainingExample).where(
                    PuzzleQualityTrainingExample.source == "personal",
                    PuzzleQualityTrainingExample.external_id == external_id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                # A puzzle can be re-rated (feedback is upsert-able, "is
                # this any good" not a tally — see PuzzleFeedback's class
                # doc) — refresh the stored stars rather than skip, so a
                # changed vote actually changes what gets trained on.
                existing.popularity = stars
                added += 1
                continue

            moves = json.loads(solution_json)
            setup_move = moves[0]

            analysis = analyse_puzzle_quality(
                fen,
                setup_move,
                engine,
                depth=depth,
                forced_win_chance_gap=forced_win_chance_gap,
                decisive_material_gain=decisive_material_gain,
                # Always on here, unlike build_training_dataset.py's opt-in
                # flag — real personal-feedback volume is naturally tiny
                # (same reasoning as this module's depth default above), so
                # the tablebase's self-throttle costs seconds, not minutes.
                tablebase_prober=tablebase.probe,
            )
            if analysis is None:
                skipped += 1
                continue

            session.add(
                PuzzleQualityTrainingExample(
                    source="personal",
                    external_id=external_id,
                    fen=fen,
                    setup_move=setup_move,
                    rating=rating,
                    setup_swing_cp=analysis.setup_swing_cp,
                    forced=analysis.forced,
                    refutation_gap_cp=analysis.refutation_gap_cp,
                    puzzle_position_eval_cp=analysis.puzzle_position_eval_cp,
                    has_decisive_payoff=analysis.has_decisive_payoff,
                    decisive_material_gain=analysis.decisive_material_gain,
                    num_checking_moves=analysis.num_checking_moves,
                    num_hanging_pieces=analysis.num_hanging_pieces,
                    material_imbalance=analysis.material_imbalance,
                    num_pinned_pieces=analysis.num_pinned_pieces,
                    # Raw 1-5 stars — see extract_labels() for why this
                    # source gets a fixed >=3 threshold rather than a
                    # median split. nb_plays has no personal-feedback
                    # equivalent (no "play count" concept for a puzzle
                    # generated for, and rated by, exactly one person); 1
                    # is a harmless placeholder to satisfy the NOT NULL
                    # column, never actually read for source="personal" rows.
                    popularity=stars,
                    nb_plays=1,
                    created_at=datetime.now(timezone.utc),
                )
            )
            added += 1

        session.commit()
    finally:
        session.close()

    return added, skipped


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, default=settings.stockfish_depth)
    parser.add_argument("--forced-win-chance-gap", type=float, default=settings.forced_win_chance_gap)
    parser.add_argument("--decisive-material-gain", type=int, default=settings.decisive_material_gain)
    args = parser.parse_args()

    engine = chess.engine.SimpleEngine.popen_uci(settings.stockfish_path)
    try:
        added, skipped = build_dataset(
            engine,
            depth=args.depth,
            forced_win_chance_gap=args.forced_win_chance_gap,
            decisive_material_gain=args.decisive_material_gain,
        )
    finally:
        engine.quit()

    logger.info("Done — %d examples added/updated, %d skipped.", added, skipped)


if __name__ == "__main__":
    main()
