"""
Shared feature-vector construction — the one place that turns a
PuzzleQualityAnalysis (or a stored PuzzleQualityTrainingExample) into
numbers, so every model built on top (puzzle_quality_model.py,
puzzle_rating_model.py, and whatever comes after) trains on identically
computed features. A change to how a signal is encoded — a new one added,
a different way of handling a missing value — only has to happen here.

This module deliberately knows nothing about labels or models. Each model
module owns its own label extraction and any feature it adds on top of this
shared "core" (see puzzle_quality_model.py's added `rating` feature, which
is legitimate context for predicting popularity but would be circular for
predicting rating itself — that asymmetry is exactly why label-specific
extras live in the model modules, not here).
"""

import numpy as np
from sqlalchemy import select

from ml.db import PuzzleQualityTrainingExample, SessionLocal
from ml.puzzle_quality import PuzzleQualityAnalysis

CORE_FEATURE_NAMES = [
    "setup_swing_cp",
    "forced",
    "has_second_line",
    "refutation_gap_cp",
    "puzzle_position_eval_cp",
    "has_decisive_payoff",
    "decisive_material_gain",
    "num_checking_moves",
    "num_hanging_pieces",
    "material_imbalance",
    "num_pinned_pieces",
]


def core_features(
    setup_swing_cp: float,
    forced: bool,
    refutation_gap_cp: float | None,
    puzzle_position_eval_cp: float,
    has_decisive_payoff: bool,
    decisive_material_gain: float,
    num_checking_moves: float,
    num_hanging_pieces: float,
    material_imbalance: float,
    num_pinned_pieces: float,
) -> list[float]:
    """
    refutation_gap_cp is None when there was no second legal reply to compare
    against (trivially forced) — imputed to 0 with a separate has_second_line
    flag rather than dropped, so "no runner-up at all" stays distinguishable
    from "runner-up was exactly as good". puzzle_position_eval_cp lets a
    model learn its own "how decided is too decided" boundary instead of a
    hand-picked cp cutoff; has_decisive_payoff/decisive_material_gain do the
    same for "does the solving line actually go anywhere concrete" — see
    puzzle_quality.py's find_decisive_payoff. The last four (see
    puzzle_quality.tactical_sharpness) came out of comparing real Lichess
    puzzle positions against positions randomly sampled from real chess.com
    games: they're the ones that kept discriminating even after controlling
    for total_material, i.e. not just proxies for "this happened later in
    a more simplified game" the way most raw position stats turned out to be.
    """
    has_second_line = refutation_gap_cp is not None
    return [
        float(setup_swing_cp),
        1.0 if forced else 0.0,
        1.0 if has_second_line else 0.0,
        float(refutation_gap_cp) if has_second_line else 0.0,
        float(puzzle_position_eval_cp),
        1.0 if has_decisive_payoff else 0.0,
        float(decisive_material_gain),
        float(num_checking_moves),
        float(num_hanging_pieces),
        float(material_imbalance),
        float(num_pinned_pieces),
    ]


def core_features_from_analysis(analysis: PuzzleQualityAnalysis) -> list[float]:
    """Inference-time path — a live analyse_puzzle_quality() result, no DB row involved."""
    return core_features(
        analysis.setup_swing_cp,
        analysis.forced,
        analysis.refutation_gap_cp,
        analysis.puzzle_position_eval_cp,
        analysis.has_decisive_payoff,
        analysis.decisive_material_gain,
        analysis.num_checking_moves,
        analysis.num_hanging_pieces,
        analysis.material_imbalance,
        analysis.num_pinned_pieces,
    )


def core_features_from_example(example: PuzzleQualityTrainingExample) -> list[float]:
    """Training-time path — a persisted example (see build_training_dataset.py)."""
    return core_features(
        example.setup_swing_cp,
        example.forced,
        example.refutation_gap_cp,
        example.puzzle_position_eval_cp,
        example.has_decisive_payoff,
        example.decisive_material_gain,
        example.num_checking_moves,
        example.num_hanging_pieces,
        example.material_imbalance,
        example.num_pinned_pieces,
    )


def build_core_feature_matrix(examples: list[PuzzleQualityTrainingExample]) -> np.ndarray:
    return np.array([core_features_from_example(ex) for ex in examples], dtype=float)


def load_examples() -> list[PuzzleQualityTrainingExample]:
    session = SessionLocal()
    try:
        return list(session.execute(select(PuzzleQualityTrainingExample)).scalars().all())
    finally:
        session.close()
