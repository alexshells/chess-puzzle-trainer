import numpy as np

from ml.train_puzzle_quality_model import to_feature_matrix, train


class FakeExample:
    def __init__(self, setup_swing_cp, forced, refutation_gap_cp, rating, popularity):
        self.setup_swing_cp = setup_swing_cp
        self.forced = forced
        self.refutation_gap_cp = refutation_gap_cp
        self.rating = rating
        self.popularity = popularity


def test_to_feature_matrix_imputes_missing_gap_and_flags_it():
    examples = [
        FakeExample(300, True, 150, 1500, popularity=40),
        FakeExample(50, False, None, 900, popularity=-10),
    ]

    X, popularity = to_feature_matrix(examples)

    assert X.shape == (2, 5)
    # Row 0: swing, forced=1, has_second_line=1, gap=150, rating
    assert list(X[0]) == [300.0, 1.0, 1.0, 150.0, 1500.0]
    # Row 1: no second line at all — gap imputed to 0, flag set to 0, not 1
    assert list(X[1]) == [50.0, 0.0, 0.0, 0.0, 900.0]
    assert list(popularity) == [40.0, -10.0]


def test_train_labels_on_a_median_split_not_a_fixed_zero_cutoff():
    # All popularity values here are positive (as real Lichess data almost
    # always is — see train()'s docstring) — a ">0" cutoff would call every
    # row positive. A median split instead gives a real, balanced label.
    examples = [
        FakeExample(0, True, None, 1000, popularity=p) for p in [10, 20, 30, 90, 95, 99]
    ]
    X, popularity = to_feature_matrix(examples)

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
