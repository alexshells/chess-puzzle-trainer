from pathlib import Path

import numpy as np

from ml.puzzle_quality import PuzzleQualityAnalysis
from ml.puzzle_quality_model import build_feature_matrix, extract_popularity, predict, train, try_load


class FakeExample:
    def __init__(self, setup_swing_cp, forced, refutation_gap_cp, rating, popularity):
        self.setup_swing_cp = setup_swing_cp
        self.forced = forced
        self.refutation_gap_cp = refutation_gap_cp
        self.rating = rating
        self.popularity = popularity


def test_build_feature_matrix_appends_rating_to_the_core_features():
    examples = [FakeExample(300, True, 150, 1500, popularity=40)]

    X = build_feature_matrix(examples)

    assert X.shape == (1, 5)
    assert list(X[0]) == [300.0, 1.0, 1.0, 150.0, 1500.0]


def test_extract_popularity_reads_raw_values_in_order():
    examples = [
        FakeExample(0, True, None, 1000, popularity=40),
        FakeExample(0, True, None, 1000, popularity=-10),
    ]

    assert list(extract_popularity(examples)) == [40.0, -10.0]


def test_train_labels_on_a_median_split_not_a_fixed_zero_cutoff():
    # All popularity values here are positive (as real Lichess data almost
    # always is — see train()'s docstring) — a ">0" cutoff would call every
    # row positive. A median split instead gives a real, balanced label.
    examples = [FakeExample(0, True, None, 1000, popularity=p) for p in [10, 20, 30, 90, 95, 99]]
    X = build_feature_matrix(examples)
    popularity = extract_popularity(examples)

    _, report = train(X, popularity, test_size=0.5, seed=0)

    assert report["positive_rate"] == 0.5


def test_train_recovers_a_clearly_separable_signal():
    # Synthetic but not cheating: setup_swing_cp alone perfectly predicts
    # which side of the median split a row lands on, so a well-behaved
    # pipeline should score well above chance.
    rng = np.random.default_rng(0)
    n = 200
    swing = rng.normal(0, 1, n)
    X = np.column_stack(
        [swing, rng.integers(0, 2, n), rng.integers(0, 2, n), rng.normal(0, 1, n), rng.normal(1500, 200, n)]
    )
    popularity = swing  # median(popularity) ~= 0, so the split tracks swing > 0

    _, report = train(X, popularity, test_size=0.25, seed=0)

    assert report["auc"] > 0.9


def test_predict_returns_a_probability_using_the_trained_pipeline():
    rng = np.random.default_rng(0)
    n = 200
    swing = rng.normal(0, 1, n)
    X = np.column_stack(
        [swing, rng.integers(0, 2, n), rng.integers(0, 2, n), rng.normal(0, 1, n), rng.normal(1500, 200, n)]
    )
    popularity = swing
    pipeline, _ = train(X, popularity, test_size=0.25, seed=0)

    strongly_positive = PuzzleQualityAnalysis(
        puzzle_position_eval_cp=0, setup_swing_cp=5, forced=True, refutation_gap_cp=200, solving_pv=[]
    )
    probability = predict(pipeline, strongly_positive, rating=1500)

    assert 0.0 <= probability <= 1.0
    assert probability > 0.5


def test_try_load_returns_none_when_no_model_file_exists(tmp_path: Path):
    assert try_load(tmp_path / "does-not-exist.joblib") is None
