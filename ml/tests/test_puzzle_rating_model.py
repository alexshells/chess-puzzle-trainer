from pathlib import Path

import numpy as np

from ml.puzzle_quality import PuzzleQualityAnalysis
from ml.puzzle_rating_model import MAX_RATING, MIN_RATING, build_feature_matrix, extract_ratings, predict, train, try_load


class FakeExample:
    def __init__(
        self,
        setup_swing_cp,
        forced,
        refutation_gap_cp,
        rating,
        puzzle_position_eval_cp=0,
        has_decisive_payoff=True,
        decisive_material_gain=0,
        num_checking_moves=0,
        num_hanging_pieces=0,
        material_imbalance=0,
        num_pinned_pieces=0,
    ):
        self.setup_swing_cp = setup_swing_cp
        self.forced = forced
        self.refutation_gap_cp = refutation_gap_cp
        self.rating = rating
        self.puzzle_position_eval_cp = puzzle_position_eval_cp
        self.has_decisive_payoff = has_decisive_payoff
        self.decisive_material_gain = decisive_material_gain
        self.num_checking_moves = num_checking_moves
        self.num_hanging_pieces = num_hanging_pieces
        self.material_imbalance = material_imbalance
        self.num_pinned_pieces = num_pinned_pieces


def test_build_feature_matrix_uses_only_core_features_no_rating():
    examples = [
        FakeExample(
            300, True, 150, rating=1800, puzzle_position_eval_cp=20, decisive_material_gain=3,
            num_checking_moves=2, num_hanging_pieces=1, material_imbalance=4, num_pinned_pieces=1,
        )
    ]

    X = build_feature_matrix(examples)

    # 11 core features — rating must NOT be one of them, it's the label here.
    assert X.shape == (1, 11)
    assert list(X[0]) == [300.0, 1.0, 1.0, 150.0, 20.0, 1.0, 3.0, 2.0, 1.0, 4.0, 1.0]


def test_extract_ratings_reads_raw_values_in_order():
    examples = [FakeExample(0, True, None, rating=1200), FakeExample(0, True, None, rating=2000)]

    assert list(extract_ratings(examples)) == [1200.0, 2000.0]


def test_train_recovers_a_clearly_correlated_signal():
    # Synthetic but not cheating: rating is a noisy linear function of
    # setup_swing_cp, so a well-behaved regressor should explain most of the
    # variance (high R^2, low error relative to the rating range).
    rng = np.random.default_rng(0)
    n = 300
    swing = rng.normal(0, 200, n)
    X = np.column_stack(
        [
            swing,
            rng.integers(0, 2, n),
            rng.integers(0, 2, n),
            rng.normal(0, 100, n),
            rng.normal(0, 100, n),
            rng.integers(0, 2, n),
            rng.normal(0, 1, n),
            rng.integers(0, 4, n),
            rng.integers(0, 3, n),
            rng.normal(0, 1, n),
            rng.integers(0, 3, n),
        ]
    )
    noise = rng.normal(0, 50, n)
    ratings = 1500 + swing * 2 + noise

    _, report = train(X, ratings, test_size=0.25, seed=0)

    assert report["r2"] > 0.8


def test_predict_returns_a_plausible_rating_using_the_trained_pipeline():
    rng = np.random.default_rng(0)
    n = 300
    swing = rng.normal(0, 200, n)
    X = np.column_stack(
        [
            swing,
            rng.integers(0, 2, n),
            rng.integers(0, 2, n),
            rng.normal(0, 100, n),
            rng.normal(0, 100, n),
            rng.integers(0, 2, n),
            rng.normal(0, 1, n),
            rng.integers(0, 4, n),
            rng.integers(0, 3, n),
            rng.normal(0, 1, n),
            rng.integers(0, 3, n),
        ]
    )
    ratings = 1500 + swing * 2 + rng.normal(0, 50, n)
    pipeline, _ = train(X, ratings, test_size=0.25, seed=0)

    analysis = PuzzleQualityAnalysis(
        puzzle_position_eval_cp=0, setup_swing_cp=0, forced=True, refutation_gap_cp=200, solving_pv=[]
    )
    predicted = predict(pipeline, analysis)

    # swing=0 should land close to the ~1500 baseline this synthetic data was built around.
    assert 1300 < predicted < 1700


def test_predict_clamps_an_out_of_range_prediction():
    # Unlike the ridge regression this model replaced, a tree-based
    # regressor's leaf predictions can't run away arbitrarily far outside
    # the training data's own rating range — extrapolation isn't really
    # the risk it used to be. The clamp is still a cheap, correct safety
    # net worth keeping regardless, so test it directly against a fake
    # model rather than relying on a real model happening to produce an
    # extreme value.
    class FakeModel:
        def __init__(self, raw_prediction):
            self._raw = raw_prediction

        def predict(self, X):
            return np.array([self._raw])

    analysis = PuzzleQualityAnalysis(
        puzzle_position_eval_cp=0, setup_swing_cp=0, forced=True, refutation_gap_cp=200, solving_pv=[]
    )

    assert predict(FakeModel(100_000), analysis) == MAX_RATING
    assert predict(FakeModel(-100_000), analysis) == MIN_RATING
    assert predict(FakeModel(1800), analysis) == 1800  # a plausible value passes through unchanged


def test_try_load_returns_none_when_no_model_file_exists(tmp_path: Path):
    assert try_load(tmp_path / "does-not-exist.joblib") is None
