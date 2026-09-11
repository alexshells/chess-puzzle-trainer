"""
Puzzle-quality classifier: predicts whether a puzzle is relatively more or
less popular than its peers, given puzzle_features.py's shared core features
plus this model's own `rating` — legitimate context here (a puzzle's
difficulty can plausibly affect how many people like it) but not something
puzzle_rating_model.py's sibling model can use, since there `rating` is the
label being predicted, not an input.

Gradient-boosted trees (sklearn's HistGradientBoostingClassifier — already a
core dependency, nothing new to install), not logistic regression. Logistic
regression was the original, deliberate choice back when the training set
was a few thousand rows, reasoning that a small linear model was less likely
to overfit than trees would be. At 51k+ rows that reasoning no longer holds,
and a direct comparison (2026-09-11, same data, same split, sklearn's
*default* hyperparameters — no tuning) confirmed it: logistic regression
AUC 0.590 vs. gradient boosting AUC 0.627. The features already had more
signal in them than a linear model could extract — this was a genuine
model-capacity bottleneck, not a data or feature ceiling. See CLAUDE.md's
Phase 2.5 note for the full write-up (it also covers the *other* two
hypotheses — bigger sample, real motif detection — that this result argues
against chasing next).

Also trains on real personal-puzzle feedback now (`PuzzleFeedback.stars`,
via build_personal_feedback_dataset.py), not just Lichess popularity — see
extract_labels()/extract_weights(). Weighted, not a hard cutover: with zero
personal feedback this behaves identically to Lichess-only training; its
influence grows smoothly as real votes accumulate (config.py's
personal_feedback_k/personal_feedback_max_weight).

Run via `uv run python -m ml.puzzle_quality_model`.
"""

import argparse
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from ml.config import settings
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


def extract_labels(examples: list[PuzzleQualityTrainingExample]) -> np.ndarray:
    """
    Two different label rules by source, because the two sources answer two
    different questions. Lichess rows: a median split of `popularity` within
    the Lichess-only subset — "more/less popular than its peers", not a
    fixed ">0" cutoff (see the docstring this replaced, and train()'s note
    below for why). The median is computed over Lichess rows only, so it
    doesn't drift as personal-feedback volume changes. Personal rows (source
    == "personal"): `popularity` holds the raw 1-5 `PuzzleFeedback.stars`
    value (see build_personal_feedback_dataset.py) — stars have a real,
    fixed, human-legible meaning already established elsewhere in this
    codebase (Puzzle::$discardedAt treats 1-2 stars as "bad, don't serve
    again" and 3+ as acceptable — PuzzleFeedbackController), so a fixed
    >=3 threshold is the right rule here, not a median split.
    """
    lichess_popularity = [ex.popularity for ex in examples if ex.source == "lichess"]
    median_pop = np.median(lichess_popularity) if lichess_popularity else 0.0

    return np.array(
        [
            (1 if ex.popularity >= 3 else 0) if ex.source == "personal" else (1 if ex.popularity > median_pop else 0)
            for ex in examples
        ]
    )


def extract_weights(
    examples: list[PuzzleQualityTrainingExample],
    *,
    k: int = settings.personal_feedback_k,
    max_weight: float = settings.personal_feedback_max_weight,
) -> np.ndarray:
    """
    Every Lichess example weighs 1.0. Every personal example weighs the
    same shrinkage-curve amount — `n / (n + k)` fraction of max_weight,
    where n is the total count of personal examples in this training run —
    not weighted individually by e.g. how "confident" one particular vote
    is, just collectively by how much personal feedback exists overall.
    Same mathematical shape as GlickoRatingService's own confidence
    blending: at n=0 the term is exactly 0 (zero personal examples means
    zero influence, and this function would never even be called with any
    in that case), it crosses half of max_weight at n=k, and it approaches
    max_weight asymptotically as n grows — always leaving room to grow
    further rather than snapping to "fully trusted" at some cutoff.
    """
    n_personal = sum(1 for ex in examples if ex.source == "personal")
    personal_weight = (n_personal / (n_personal + k)) * max_weight if n_personal > 0 else 0.0

    return np.array([personal_weight if ex.source == "personal" else 1.0 for ex in examples])


def train(
    X: np.ndarray, y: np.ndarray, *, test_size: float, seed: int, sample_weight: np.ndarray | None = None
) -> tuple[Pipeline, dict]:
    """
    Takes already-binarized labels (see extract_labels()) and optional
    per-row weights (see extract_weights()) rather than doing either
    itself — both now depend on a row's `source`, which this function has
    no reason to know about; it just fits whatever it's handed.
    """
    weights = sample_weight if sample_weight is not None else np.ones(len(y))

    X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(
        X, y, weights, test_size=test_size, random_state=seed, stratify=y
    )

    pipeline = Pipeline([("classify", HistGradientBoostingClassifier(random_state=seed))])
    pipeline.fit(X_train, y_train, classify__sample_weight=w_train)

    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    # HistGradientBoostingClassifier has no .coef_ (it's not linear) and no
    # .feature_importances_ either (unlike sklearn's older GradientBoosting-
    # Classifier) — permutation importance (how much shuffling one column
    # hurts held-out AUC) is the standard substitute, and arguably more
    # honest than a linear coefficient anyway, since it's measured on the
    # actual held-out behavior rather than read off the fitted parameters.
    importance = permutation_importance(
        pipeline, X_test, y_test, n_repeats=10, random_state=seed, scoring="roc_auc"
    )

    report = {
        "n_train": len(X_train),
        "n_test": len(X_test),
        "positive_rate": float(y.mean()),
        "auc": roc_auc_score(y_test, y_proba, sample_weight=w_test),
        "classification_report": classification_report(y_test, y_pred, sample_weight=w_test),
        "permutation_importance": dict(zip(FEATURE_NAMES, importance.importances_mean.tolist())),
    }
    return pipeline, report


def load(path: Path = _DEFAULT_MODEL_PATH) -> Pipeline:
    return joblib.load(path)


def try_load(path: Path = _DEFAULT_MODEL_PATH) -> Pipeline | None:
    """
    Like load(), but returns None instead of raising when no trained model
    exists at this path — the caller's signal to skip quality scoring
    (see game_import.py) rather than a live-import-breaking crash.
    """
    if not path.exists():
        return None
    return load(path)


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
    n_personal = sum(1 for ex in examples if ex.source == "personal")
    logger.info("Loaded %d training examples (%d personal, %d lichess)", len(examples), n_personal, len(examples) - n_personal)
    if len(examples) < 50:
        logger.warning("Very few examples — treat any metrics below as a pipeline smoke test, not a real result.")

    X = build_feature_matrix(examples)
    y = extract_labels(examples)
    weights = extract_weights(examples)
    if n_personal > 0:
        confidence = n_personal / (n_personal + settings.personal_feedback_k)
        logger.info(
            "Personal feedback confidence: %.3f (n=%d, k=%d) -> per-example weight %.2f (vs. 1.0 for a Lichess row)",
            confidence, n_personal, settings.personal_feedback_k, confidence * settings.personal_feedback_max_weight,
        )

    pipeline, report = train(X, y, test_size=args.test_size, seed=args.seed, sample_weight=weights)

    logger.info("n_train=%d n_test=%d positive_rate=%.3f", report["n_train"], report["n_test"], report["positive_rate"])
    logger.info("AUC: %.3f", report["auc"])
    logger.info("\n%s", report["classification_report"])
    logger.info("Permutation importance (mean AUC drop when shuffled): %s", report["permutation_importance"])

    args.model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, args.model_path)
    logger.info("Saved model to %s", args.model_path)


if __name__ == "__main__":
    main()
