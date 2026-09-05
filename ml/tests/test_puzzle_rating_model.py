import numpy as np

from ml.puzzle_quality import PuzzleQualityAnalysis
from ml.puzzle_rating_model import build_feature_matrix, extract_ratings, predict, train


class FakeExample:
    def __init__(self, setup_swing_cp, forced, refutation_gap_cp, rating):
        self.setup_swing_cp = setup_swing_cp
        self.forced = forced
        self.refutation_gap_cp = refutation_gap_cp
        self.rating = rating


def test_build_feature_matrix_uses_only_core_features_no_rating():
    examples = [FakeExample(300, True, 150, rating=1800)]

    X = build_feature_matrix(examples)

    # 4 core features — rating must NOT be one of them, it's the label here.
    assert X.shape == (1, 4)
    assert list(X[0]) == [300.0, 1.0, 1.0, 150.0]


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
    X = np.column_stack([swing, rng.integers(0, 2, n), rng.integers(0, 2, n), rng.normal(0, 100, n)])
    noise = rng.normal(0, 50, n)
    ratings = 1500 + swing * 2 + noise

    _, report = train(X, ratings, test_size=0.25, seed=0)

    assert report["r2"] > 0.8


def test_predict_returns_a_plausible_rating_using_the_trained_pipeline():
    rng = np.random.default_rng(0)
    n = 300
    swing = rng.normal(0, 200, n)
    X = np.column_stack([swing, rng.integers(0, 2, n), rng.integers(0, 2, n), rng.normal(0, 100, n)])
    ratings = 1500 + swing * 2 + rng.normal(0, 50, n)
    pipeline, _ = train(X, ratings, test_size=0.25, seed=0)

    analysis = PuzzleQualityAnalysis(
        puzzle_position_eval_cp=0, setup_swing_cp=0, forced=True, refutation_gap_cp=200, solving_pv=[]
    )
    predicted = predict(pipeline, analysis)

    # swing=0 should land close to the ~1500 baseline this synthetic data was built around.
    assert 1300 < predicted < 1700
