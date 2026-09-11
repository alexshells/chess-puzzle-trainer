from pathlib import Path

import numpy as np

from ml.puzzle_quality import PuzzleQualityAnalysis
from ml.puzzle_quality_model import (
    build_feature_matrix,
    extract_labels,
    extract_popularity,
    extract_weights,
    predict,
    train,
    try_load,
)


class FakeExample:
    def __init__(
        self,
        setup_swing_cp,
        forced,
        refutation_gap_cp,
        rating,
        popularity,
        puzzle_position_eval_cp=0,
        has_decisive_payoff=True,
        decisive_material_gain=0,
        num_checking_moves=0,
        num_hanging_pieces=0,
        material_imbalance=0,
        num_pinned_pieces=0,
        source="lichess",
    ):
        self.setup_swing_cp = setup_swing_cp
        self.forced = forced
        self.refutation_gap_cp = refutation_gap_cp
        self.rating = rating
        self.popularity = popularity
        self.puzzle_position_eval_cp = puzzle_position_eval_cp
        self.has_decisive_payoff = has_decisive_payoff
        self.decisive_material_gain = decisive_material_gain
        self.num_checking_moves = num_checking_moves
        self.num_hanging_pieces = num_hanging_pieces
        self.material_imbalance = material_imbalance
        self.num_pinned_pieces = num_pinned_pieces
        self.source = source


def test_build_feature_matrix_appends_rating_to_the_core_features():
    examples = [
        FakeExample(
            300, True, 150, 1500, popularity=40, puzzle_position_eval_cp=20, decisive_material_gain=3,
            num_checking_moves=2, num_hanging_pieces=1, material_imbalance=4, num_pinned_pieces=1,
        )
    ]

    X = build_feature_matrix(examples)

    assert X.shape == (1, 12)
    assert list(X[0]) == [300.0, 1.0, 1.0, 150.0, 20.0, 1.0, 3.0, 2.0, 1.0, 4.0, 1.0, 1500.0]


def test_extract_popularity_reads_raw_values_in_order():
    examples = [
        FakeExample(0, True, None, 1000, popularity=40),
        FakeExample(0, True, None, 1000, popularity=-10),
    ]

    assert list(extract_popularity(examples)) == [40.0, -10.0]


def test_extract_labels_uses_median_split_for_lichess_rows():
    # All popularity values here are positive (as real Lichess data almost
    # always is) — a ">0" cutoff would call every row positive. A median
    # split instead gives a real, balanced label.
    examples = [FakeExample(0, True, None, 1000, popularity=p, source="lichess") for p in [10, 20, 30, 90, 95, 99]]

    labels = extract_labels(examples)

    assert list(labels) == [0, 0, 0, 1, 1, 1]  # 30 and below <= median (60), 90+ above it


def test_extract_labels_uses_a_fixed_threshold_for_personal_rows():
    # Stars have real, fixed meaning already established elsewhere in this
    # codebase (Puzzle::$discardedAt treats 1-2 as bad, 3+ as acceptable) —
    # a personal row's label shouldn't depend on a median at all, unlike
    # Lichess popularity, which has no fixed "good" zero-point.
    examples = [FakeExample(0, True, None, 1000, popularity=stars, source="personal") for stars in [1, 2, 3, 4, 5]]

    labels = extract_labels(examples)

    assert list(labels) == [0, 0, 1, 1, 1]


def test_extract_labels_lichess_median_is_unaffected_by_personal_rows():
    # A handful of low-star personal rows mixed in shouldn't drag down the
    # median used to label the *Lichess* rows — the two sources use
    # different, independent rules.
    lichess = [FakeExample(0, True, None, 1000, popularity=p, source="lichess") for p in [10, 20, 30, 90, 95, 99]]
    personal = [FakeExample(0, True, None, 1000, popularity=1, source="personal") for _ in range(20)]

    labels = extract_labels(lichess + personal)

    assert list(labels[:6]) == [0, 0, 0, 1, 1, 1]  # same split as the lichess-only test
    assert list(labels[6:]) == [0] * 20  # all the 1-star personal rows


def test_extract_weights_is_all_ones_with_no_personal_examples():
    examples = [FakeExample(0, True, None, 1000, popularity=p, source="lichess") for p in [10, 20, 30]]

    weights = extract_weights(examples, k=100, max_weight=10.0)

    assert list(weights) == [1.0, 1.0, 1.0]


def test_extract_weights_grows_toward_max_as_personal_volume_grows():
    # n/(n+k) is exactly 0.5 at n=k — same shrinkage shape
    # GlickoRatingService already uses elsewhere in this codebase.
    lichess = [FakeExample(0, True, None, 1000, popularity=50, source="lichess")]
    personal_at_k = [FakeExample(0, True, None, 1000, popularity=5, source="personal") for _ in range(100)]

    weights = extract_weights(lichess + personal_at_k, k=100, max_weight=10.0)

    assert weights[0] == 1.0  # the lone lichess row, unaffected
    assert all(w == 5.0 for w in weights[1:])  # 100/(100+100) * 10.0 = 5.0


def test_extract_weights_approaches_but_never_reaches_max():
    personal = [FakeExample(0, True, None, 1000, popularity=5, source="personal") for _ in range(10_000)]

    weights = extract_weights(personal, k=100, max_weight=10.0)

    assert all(w < 10.0 for w in weights)
    assert all(w > 9.9 for w in weights)  # but very close, at this volume


def test_train_recovers_a_clearly_separable_signal():
    # Synthetic but not cheating: setup_swing_cp alone perfectly predicts
    # which side of the median split a row lands on, so a well-behaved
    # pipeline should score well above chance.
    rng = np.random.default_rng(0)
    n = 200
    swing = rng.normal(0, 1, n)
    X = np.column_stack(
        [
            swing,
            rng.integers(0, 2, n),
            rng.integers(0, 2, n),
            rng.normal(0, 1, n),
            rng.normal(0, 1, n),
            rng.integers(0, 2, n),
            rng.normal(0, 1, n),
            rng.integers(0, 4, n),
            rng.integers(0, 3, n),
            rng.normal(0, 1, n),
            rng.integers(0, 3, n),
            rng.normal(1500, 200, n),
        ]
    )
    y = (swing > np.median(swing)).astype(int)  # median(swing) ~= 0, so this tracks swing > 0

    _, report = train(X, y, test_size=0.25, seed=0)

    assert report["auc"] > 0.9


def test_train_respects_sample_weight():
    # A small, heavily-upweighted minority with the OPPOSITE label from the
    # majority should be able to shift what the model learns — proof
    # sample_weight is actually reaching .fit(), not just accepted and
    # ignored. Majority: feature > 0 predicts label 1 (100 rows). Minority:
    # feature > 0 but labeled 0, weighted 50x each (5 rows, effectively
    # 250 "votes" against the majority's 100) — heavily upweighting a
    # cleanly-contradicting minority should measurably hurt accuracy on
    # the (label-consistent) majority pattern versus leaving it unweighted.
    rng = np.random.default_rng(0)
    n_majority = 100
    feature = rng.normal(0, 1, n_majority)
    y_majority = (feature > 0).astype(int)
    filler = np.zeros((n_majority, 10))
    X_majority = np.column_stack([feature, filler])

    minority_feature = np.array([0.5, 0.6, 0.7, 0.8, 0.9])
    X_minority = np.column_stack([minority_feature, np.zeros((5, 10))])
    y_minority = np.zeros(5, dtype=int)  # contradicts the majority pattern for feature > 0

    X = np.vstack([X_majority, X_minority])
    y = np.concatenate([y_majority, y_minority])
    weights_flat = np.ones(len(y))
    weights_heavy = np.concatenate([np.ones(n_majority), np.full(5, 50.0)])

    _, report_flat = train(X, y, test_size=0.2, seed=0, sample_weight=weights_flat)
    _, report_heavy = train(X, y, test_size=0.2, seed=0, sample_weight=weights_heavy)

    assert report_heavy["auc"] != report_flat["auc"]


def test_predict_returns_a_probability_using_the_trained_pipeline():
    rng = np.random.default_rng(0)
    n = 200
    swing = rng.normal(0, 1, n)
    X = np.column_stack(
        [
            swing,
            rng.integers(0, 2, n),
            rng.integers(0, 2, n),
            rng.normal(0, 1, n),
            rng.normal(0, 1, n),
            rng.integers(0, 2, n),
            rng.normal(0, 1, n),
            rng.integers(0, 4, n),
            rng.integers(0, 3, n),
            rng.normal(0, 1, n),
            rng.integers(0, 3, n),
            rng.normal(1500, 200, n),
        ]
    )
    y = (swing > np.median(swing)).astype(int)
    pipeline, _ = train(X, y, test_size=0.25, seed=0)

    strongly_positive = PuzzleQualityAnalysis(
        puzzle_position_eval_cp=0, setup_swing_cp=5, forced=True, refutation_gap_cp=200, solving_pv=[]
    )
    probability = predict(pipeline, strongly_positive, rating=1500)

    assert 0.0 <= probability <= 1.0
    assert probability > 0.5


def test_try_load_returns_none_when_no_model_file_exists(tmp_path: Path):
    assert try_load(tmp_path / "does-not-exist.joblib") is None
