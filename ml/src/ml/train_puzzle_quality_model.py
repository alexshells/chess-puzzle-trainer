"""
Trains a first-pass puzzle-quality classifier on PuzzleQualityTrainingExample
rows (see build_training_dataset.py) — label = whether Lichess's own users
voted a puzzle net-positive (Popularity > 0), features = the same
puzzle_quality.py signals game_import.py computes for its own candidates.

Logistic regression, not a bigger model — deliberately. At this sample size
(low thousands, one bootstrap source) a small linear model is less likely to
overfit than something like gradient-boosted trees, and its coefficients are
directly readable (see the printed report), which matters when this is the
first pass, not the last, of this model. Swapping in something larger later
is a one-line change once there's more data (in particular, our own
puzzle_feedback votes) to justify it.

Run via `uv run python -m ml.train_puzzle_quality_model`.
"""

import argparse
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select

from ml.db import PuzzleQualityTrainingExample, SessionLocal

logger = logging.getLogger(__name__)

FEATURE_NAMES = ["setup_swing_cp", "forced", "has_second_line", "refutation_gap_cp", "rating"]
_DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "var" / "puzzle_quality_model.joblib"


def load_examples() -> list[PuzzleQualityTrainingExample]:
    session = SessionLocal()
    try:
        return list(session.execute(select(PuzzleQualityTrainingExample)).scalars().all())
    finally:
        session.close()


def to_feature_matrix(examples: list[PuzzleQualityTrainingExample]) -> tuple[np.ndarray, np.ndarray]:
    """
    Returns (X, popularity) — raw Popularity, not yet a binary label (see
    train() for why: it needs the whole sample's distribution first).
    refutation_gap_cp is null when there was no second legal reply to compare
    against (trivially forced) — imputed to 0 with a separate has_second_line
    flag rather than dropped, so "no runner-up at all" stays distinguishable
    from "runner-up was exactly as good".
    """
    rows = []
    popularity = []
    for ex in examples:
        has_second_line = ex.refutation_gap_cp is not None
        rows.append(
            [
                ex.setup_swing_cp,
                1.0 if ex.forced else 0.0,
                1.0 if has_second_line else 0.0,
                ex.refutation_gap_cp if has_second_line else 0.0,
                ex.rating,
            ]
        )
        popularity.append(ex.popularity)

    return np.array(rows, dtype=float), np.array(popularity, dtype=float)


def train(X: np.ndarray, popularity: np.ndarray, *, test_size: float, seed: int) -> tuple[Pipeline, dict]:
    """
    Labels on a median split of `popularity` within this sample, not a fixed
    "> 0" cutoff. Lichess's puzzles are already curated/published, so almost
    all of them sit well above zero (measured: 99.6% of a 5.6k sample had
    Popularity > 0) — an absolute-zero threshold gives a label with almost no
    negative class at all, which is a degenerate classification problem, not
    a real one. "Relatively more/less popular than its peers in this sample"
    is the honest question this dataset can actually answer.
    """
    y = (popularity > np.median(popularity)).astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y
    )

    pipeline = Pipeline(
        [
            ("scale", StandardScaler()),
            ("classify", LogisticRegression(max_iter=1000)),
        ]
    )
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    report = {
        "n_train": len(X_train),
        "n_test": len(X_test),
        "positive_rate": float(y.mean()),
        "auc": roc_auc_score(y_test, y_proba),
        "classification_report": classification_report(y_test, y_pred),
        "coefficients": dict(zip(FEATURE_NAMES, pipeline.named_steps["classify"].coef_[0].tolist())),
    }
    return pipeline, report


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

    X, popularity = to_feature_matrix(examples)
    pipeline, report = train(X, popularity, test_size=args.test_size, seed=args.seed)

    logger.info("n_train=%d n_test=%d positive_rate=%.3f", report["n_train"], report["n_test"], report["positive_rate"])
    logger.info("AUC: %.3f", report["auc"])
    logger.info("\n%s", report["classification_report"])
    logger.info("Coefficients (standardized features): %s", report["coefficients"])

    args.model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, args.model_path)
    logger.info("Saved model to %s", args.model_path)


if __name__ == "__main__":
    main()
