"""
Puzzle-quality classifier: predicts whether a puzzle is relatively more or
less popular than its peers, given puzzle_features.py's shared core features
plus this model's own `rating` — legitimate context here (a puzzle's
difficulty can plausibly affect how many people like it) but not something
puzzle_rating_model.py's sibling model can use, since there `rating` is the
label being predicted, not an input.

Logistic regression, not something bigger — deliberately. At this sample
size (low thousands, one bootstrap source) a small linear model is less
likely to overfit than gradient-boosted trees would be, and its
coefficients are directly readable (see main()'s printed report).

Run via `uv run python -m ml.puzzle_quality_model`.
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

from ml.db import PuzzleQualityTrainingExample
from ml.puzzle_features import CORE_FEATURE_NAMES, build_core_feature_matrix, core_features_from_analysis, load_examples
from ml.puzzle_quality import PuzzleQualityAnalysis

logger = logging.getLogger(__name__)

FEATURE_NAMES = CORE_FEATURE_NAMES + ["rating"]
# Committed, not gitignored — Railway's container filesystem is ephemeral,
# so a model living only in var/ wouldn't survive a deploy (see CLAUDE.md).
_DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "puzzle_quality_model.joblib"


def build_feature_matrix(examples: list[PuzzleQualityTrainingExample]) -> np.ndarray:
    core = build_core_feature_matrix(examples)
    rating = np.array([[ex.rating] for ex in examples], dtype=float)
    return np.hstack([core, rating])


def extract_popularity(examples: list[PuzzleQualityTrainingExample]) -> np.ndarray:
    return np.array([ex.popularity for ex in examples], dtype=float)


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


def load(path: Path) -> Pipeline:
    return joblib.load(path)


def predict(model: Pipeline, analysis: PuzzleQualityAnalysis, rating: int) -> float:
    """Returns P(relatively more popular than its peers), in [0, 1]."""
    X = np.array([core_features_from_analysis(analysis) + [float(rating)]])
    return float(model.predict_proba(X)[0, 1])


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
    popularity = extract_popularity(examples)
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
