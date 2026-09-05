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

Ridge regression (L2-regularized linear regression), not something bigger —
same reasoning as the sibling puzzle_quality_model.py: small sample, one
bootstrap source, a linear model's coefficients stay directly readable.

Deliberately excludes `rating` from its own features for the obvious
reason — it's the label here, unlike in puzzle_quality_model.py where it's
legitimate context for a *different* target (popularity).

Run via `uv run python -m ml.puzzle_rating_model`.
"""

import argparse
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.db import PuzzleQualityTrainingExample
from ml.puzzle_features import CORE_FEATURE_NAMES, build_core_feature_matrix, core_features_from_analysis, load_examples
from ml.puzzle_quality import PuzzleQualityAnalysis

logger = logging.getLogger(__name__)

FEATURE_NAMES = CORE_FEATURE_NAMES
_DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "var" / "puzzle_rating_model.joblib"


def build_feature_matrix(examples: list[PuzzleQualityTrainingExample]) -> np.ndarray:
    return build_core_feature_matrix(examples)


def extract_ratings(examples: list[PuzzleQualityTrainingExample]) -> np.ndarray:
    return np.array([ex.rating for ex in examples], dtype=float)


def train(X: np.ndarray, ratings: np.ndarray, *, test_size: float, seed: int) -> tuple[Pipeline, dict]:
    X_train, X_test, y_train, y_test = train_test_split(X, ratings, test_size=test_size, random_state=seed)

    pipeline = Pipeline(
        [
            ("scale", StandardScaler()),
            ("regress", Ridge()),
        ]
    )
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)

    report = {
        "n_train": len(X_train),
        "n_test": len(X_test),
        "mean_rating": float(ratings.mean()),
        "mae": mean_absolute_error(y_test, y_pred),
        "rmse": root_mean_squared_error(y_test, y_pred),
        "r2": r2_score(y_test, y_pred),
        "coefficients": dict(zip(FEATURE_NAMES, pipeline.named_steps["regress"].coef_.tolist())),
    }
    return pipeline, report


def load(path: Path) -> Pipeline:
    return joblib.load(path)


def predict(model: Pipeline, analysis: PuzzleQualityAnalysis) -> float:
    """Returns a predicted Lichess-style rating for this puzzle position."""
    X = np.array([core_features_from_analysis(analysis)])
    return float(model.predict(X)[0])


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
    logger.info("Coefficients (standardized features): %s", report["coefficients"])

    args.model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, args.model_path)
    logger.info("Saved model to %s", args.model_path)


if __name__ == "__main__":
    main()
