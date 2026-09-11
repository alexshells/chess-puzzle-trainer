"""
Puzzle-rating regressor: predicts a Lichess-style difficulty rating directly
from puzzle_features.py's shared core features — no player-rating proxy, and
no crowd-solve convergence either. Lichess's own puzzle ratings are Glicko
ratings earned from thousands of real solve attempts across many
different-strength solvers (the same mechanism backend/'s GlickoRatingService
already implements for us) — that only works because a Lichess puzzle gets
shown to thousands of strangers. A "My Games" puzzle is generated for exactly
one person and will likely be solved once, maybe never again — there's no
crowd to converge a rating from, so it has to be predicted up front instead.
This model is trained on Lichess's own puzzles (whose Rating column *is*
that crowd-converged value) to learn what position features predict it.

Gradient-boosted trees (sklearn's HistGradientBoostingRegressor), not ridge
regression. Ridge was the original, deliberate choice back when the training
set was a few thousand rows — same small-sample-overfitting reasoning as the
sibling quality classifier. At 51k+ rows that reasoning no longer holds, and
a direct comparison (2026-09-11, same data/split, sklearn's *default*
hyperparameters) confirmed it: ridge R^2 0.350 vs. gradient boosting R^2
0.470 (MAE 358.7 -> 318.5) — a bigger jump than the quality classifier got
from the same swap. See CLAUDE.md's Phase 2.5 note.

Deliberately *not* extended with personal-feedback weighting the way the
quality classifier was — `PuzzleFeedback.stars` measures "was this puzzle
enjoyable", not "was this puzzle's difficulty rating accurate". There's no
crowd-converged ground-truth rating for a personal puzzle to train toward;
a 5-star vote doesn't tell us whether the predicted rating was right. This
model stays Lichess-only.

Run via `uv run python -m ml.puzzle_rating_model`.
"""

import argparse
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from ml.db import PuzzleQualityTrainingExample
from ml.puzzle_features import CORE_FEATURE_NAMES, build_core_feature_matrix, core_features_from_analysis, load_examples
from ml.puzzle_quality import PuzzleQualityAnalysis

logger = logging.getLogger(__name__)

FEATURE_NAMES = CORE_FEATURE_NAMES
# Committed, not gitignored — Railway's container filesystem is ephemeral,
# so a model living only in var/ wouldn't survive a deploy (see CLAUDE.md).
_DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "puzzle_rating_model.joblib"

# Lichess's real puzzle ratings run roughly in this range — Ridge regression
# is unconstrained and can extrapolate a wild value for an input far outside
# the training distribution, so predictions are clamped to something a human
# would recognize as a plausible puzzle rating rather than e.g. a negative
# number or something so large it can only be a bug. Kept for the gradient-
# boosting model too even though trees can't extrapolate the same
# pathological way linear regression can — still a cheap, correct safety net
# against a genuinely out-of-distribution input.
MIN_RATING = 400
MAX_RATING = 3000


def build_feature_matrix(examples: list[PuzzleQualityTrainingExample]) -> np.ndarray:
    return build_core_feature_matrix(examples)


def extract_ratings(examples: list[PuzzleQualityTrainingExample]) -> np.ndarray:
    return np.array([ex.rating for ex in examples], dtype=float)


def train(X: np.ndarray, ratings: np.ndarray, *, test_size: float, seed: int) -> tuple[Pipeline, dict]:
    X_train, X_test, y_train, y_test = train_test_split(X, ratings, test_size=test_size, random_state=seed)

    pipeline = Pipeline([("regress", HistGradientBoostingRegressor(random_state=seed))])
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)

    # See the sibling quality classifier's train() for why permutation
    # importance replaces coefficients here — HistGradientBoostingRegressor
    # has neither .coef_ nor .feature_importances_.
    importance = permutation_importance(pipeline, X_test, y_test, n_repeats=10, random_state=seed, scoring="r2")

    report = {
        "n_train": len(X_train),
        "n_test": len(X_test),
        "mean_rating": float(ratings.mean()),
        "mae": mean_absolute_error(y_test, y_pred),
        "rmse": root_mean_squared_error(y_test, y_pred),
        "r2": r2_score(y_test, y_pred),
        "permutation_importance": dict(zip(FEATURE_NAMES, importance.importances_mean.tolist())),
    }
    return pipeline, report


def load(path: Path = _DEFAULT_MODEL_PATH) -> Pipeline:
    return joblib.load(path)


def try_load(path: Path = _DEFAULT_MODEL_PATH) -> Pipeline | None:
    """
    Like load(), but returns None instead of raising when no trained model
    exists at this path — the caller's signal to fall back to a simpler
    heuristic (see game_import.py) rather than a live-import-breaking crash.
    """
    if not path.exists():
        return None
    return load(path)


def predict(model: Pipeline, analysis: PuzzleQualityAnalysis) -> float:
    """Returns a predicted Lichess-style rating for this puzzle position, clamped to [MIN_RATING, MAX_RATING]."""
    X = np.array([core_features_from_analysis(analysis)])
    raw = float(model.predict(X)[0])
    return max(MIN_RATING, min(MAX_RATING, raw))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--model-path", type=Path, default=_DEFAULT_MODEL_PATH)
    args = parser.parse_args()

    examples = load_examples()
    logger.info("Loaded %d training examples", len(examples))
    if len(examples) < 50:
        logger.warning("Very few examples — treat any metrics below as a pipeline smoke test, not a real result.")

    X = build_feature_matrix(examples)
    ratings = extract_ratings(examples)
    pipeline, report = train(X, ratings, test_size=args.test_size, seed=args.seed)

    logger.info("n_train=%d n_test=%d mean_rating=%.0f", report["n_train"], report["n_test"], report["mean_rating"])
    logger.info("MAE: %.1f  RMSE: %.1f  R^2: %.3f", report["mae"], report["rmse"], report["r2"])
    logger.info("Permutation importance (mean R^2 drop when shuffled): %s", report["permutation_importance"])

    args.model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, args.model_path)
    logger.info("Saved model to %s", args.model_path)


if __name__ == "__main__":
    main()
