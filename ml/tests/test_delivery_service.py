import numpy as np

from ml.delivery_bandit import DeliveryArm
from ml.delivery_service import PoolPuzzle, select_puzzle_for_arm

RNG = np.random.default_rng(0)


def test_best_quality_picks_the_highest_scored_puzzle():
    pool = [
        PoolPuzzle(id=1, rating=1500, forced=False, setup_swing_cp=100, quality_score=0.4),
        PoolPuzzle(id=2, rating=1500, forced=False, setup_swing_cp=100, quality_score=0.9),
        PoolPuzzle(id=3, rating=1500, forced=False, setup_swing_cp=100, quality_score=None),
    ]

    chosen = select_puzzle_for_arm(DeliveryArm.BEST_QUALITY, pool, user_rating=1500, rng=RNG)

    assert chosen is not None
    assert chosen.id == 2


def test_best_quality_falls_back_to_random_when_nothing_is_scored():
    pool = [PoolPuzzle(id=1, rating=1500, forced=False, setup_swing_cp=100, quality_score=None)]

    chosen = select_puzzle_for_arm(DeliveryArm.BEST_QUALITY, pool, user_rating=1500, rng=RNG)

    assert chosen is not None
    assert chosen.id == 1


def test_closest_rating_picks_the_nearest_match():
    pool = [
        PoolPuzzle(id=1, rating=1000, forced=False, setup_swing_cp=100, quality_score=0.5),
        PoolPuzzle(id=2, rating=1550, forced=False, setup_swing_cp=100, quality_score=0.5),
        PoolPuzzle(id=3, rating=2000, forced=False, setup_swing_cp=100, quality_score=0.5),
    ]

    chosen = select_puzzle_for_arm(DeliveryArm.CLOSEST_RATING, pool, user_rating=1500, rng=RNG)

    assert chosen is not None
    assert chosen.id == 2


def test_forced_clean_only_considers_forced_puzzles():
    pool = [
        PoolPuzzle(id=1, rating=1500, forced=False, setup_swing_cp=100, quality_score=0.5),
        PoolPuzzle(id=2, rating=1500, forced=True, setup_swing_cp=100, quality_score=0.5),
    ]

    chosen = select_puzzle_for_arm(DeliveryArm.FORCED_CLEAN, pool, user_rating=1500, rng=RNG)

    assert chosen is not None
    assert chosen.id == 2


def test_forced_clean_falls_back_to_random_when_nothing_is_forced():
    pool = [PoolPuzzle(id=1, rating=1500, forced=False, setup_swing_cp=100, quality_score=0.5)]

    chosen = select_puzzle_for_arm(DeliveryArm.FORCED_CLEAN, pool, user_rating=1500, rng=RNG)

    assert chosen is not None
    assert chosen.id == 1


def test_biggest_blunder_picks_the_largest_swing():
    pool = [
        PoolPuzzle(id=1, rating=1500, forced=False, setup_swing_cp=150, quality_score=0.5),
        PoolPuzzle(id=2, rating=1500, forced=False, setup_swing_cp=900, quality_score=0.5),
    ]

    chosen = select_puzzle_for_arm(DeliveryArm.BIGGEST_BLUNDER, pool, user_rating=1500, rng=RNG)

    assert chosen is not None
    assert chosen.id == 2


def test_random_baseline_returns_something_from_the_pool():
    pool = [
        PoolPuzzle(id=1, rating=1500, forced=False, setup_swing_cp=100, quality_score=0.5),
        PoolPuzzle(id=2, rating=1600, forced=True, setup_swing_cp=200, quality_score=0.7),
    ]

    chosen = select_puzzle_for_arm(DeliveryArm.RANDOM_BASELINE, pool, user_rating=1500, rng=RNG)

    assert chosen is not None
    assert chosen.id in {1, 2}


def test_returns_none_for_an_empty_pool():
    for arm in DeliveryArm:
        assert select_puzzle_for_arm(arm, [], user_rating=1500, rng=RNG) is None
