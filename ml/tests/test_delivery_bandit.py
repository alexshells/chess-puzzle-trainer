import numpy as np
import pytest

from ml.delivery_bandit import (
    ArmPosterior,
    DeliveryArm,
    build_context,
    choose_arm,
    initial_posterior,
    sample_predicted_reward,
    update_posterior,
)


def test_build_context_centers_and_scales_rating():
    assert list(build_context(1500)) == [1.0, 0.0]
    assert list(build_context(2000)) == [1.0, 1.0]
    assert list(build_context(1000)) == [1.0, -1.0]


def test_initial_posterior_has_zero_mean_and_shrinks_with_stronger_prior():
    weak = initial_posterior(dimension=2, prior_precision=1.0)
    strong = initial_posterior(dimension=2, prior_precision=4.0)

    assert list(weak.mean) == [0.0, 0.0]
    assert list(strong.mean) == [0.0, 0.0]
    # A stronger (larger) prior_precision means a narrower starting belief.
    assert np.trace(strong.covariance) < np.trace(weak.covariance)


def test_update_posterior_matches_hand_computed_closed_form():
    # 1D case, worked by hand: prior precision 1 (so A0 = [[1]]), one
    # observation context=[2], reward=3, noise_variance=1.
    # A1 = A0 + context*context^T / noise = 1 + 4/1 = 5
    # b1 = b0 + context*reward / noise = 0 + 2*3/1 = 6
    # mean = b1 / A1 = 6/5 = 1.2
    prior = initial_posterior(dimension=1, prior_precision=1.0)

    updated = update_posterior(prior, context=np.array([2.0]), reward=3.0, noise_variance=1.0)

    assert updated.precision_matrix[0, 0] == 5.0
    assert updated.weighted_reward_sum[0] == 6.0
    assert updated.mean[0] == 1.2


def test_repeated_updates_pull_the_mean_toward_the_observed_reward():
    posterior = initial_posterior(dimension=2, prior_precision=1.0)
    context = build_context(1500)  # [1.0, 0.0]

    for _ in range(50):
        posterior = update_posterior(posterior, context, reward=5.0, noise_variance=1.0)

    # After many 5-star observations at this context, the intercept weight
    # should have converged close to 5 — the model believes this arm scores
    # ~5 stars for an average-rated user.
    assert posterior.mean[0] == pytest.approx(5.0, abs=0.1)


def test_choose_arm_prefers_a_confidently_higher_mean_arm():
    rng = np.random.default_rng(0)
    context = build_context(1500)

    # Both arms are very confident (tiny covariance via a huge prior
    # precision) — one's mean is far higher, so it should win essentially
    # every time regardless of sampling noise.
    high = ArmPosterior(precision_matrix=np.eye(2) * 1000, weighted_reward_sum=np.array([4000.0, 0.0]))
    low = ArmPosterior(precision_matrix=np.eye(2) * 1000, weighted_reward_sum=np.array([1000.0, 0.0]))
    posteriors = {DeliveryArm.BEST_QUALITY: high, DeliveryArm.RANDOM_BASELINE: low}

    choices = [choose_arm(posteriors, context, rng) for _ in range(20)]

    assert all(c == DeliveryArm.BEST_QUALITY for c in choices)


def test_choose_arm_explores_an_uncertain_arm_sometimes_even_with_a_lower_mean():
    rng = np.random.default_rng(0)
    context = build_context(1500)

    # confident_low has a lower mean but is very sure of it (tiny
    # covariance); uncertain has a lower mean too but is very unsure (wide
    # covariance, from a weak prior and no pulls yet) — it should
    # occasionally sample high enough to win, demonstrating exploration
    # falls out of uncertainty rather than needing a random-epsilon rule.
    confident_low = ArmPosterior(precision_matrix=np.eye(2) * 1000, weighted_reward_sum=np.array([3000.0, 0.0]))
    uncertain = initial_posterior(dimension=2, prior_precision=0.01)
    posteriors = {DeliveryArm.CLOSEST_RATING: confident_low, DeliveryArm.FORCED_CLEAN: uncertain}

    choices = [choose_arm(posteriors, context, rng) for _ in range(200)]

    assert any(c == DeliveryArm.FORCED_CLEAN for c in choices)
    assert any(c == DeliveryArm.CLOSEST_RATING for c in choices)


def test_sample_predicted_reward_is_near_the_mean_for_a_confident_posterior():
    rng = np.random.default_rng(0)
    posterior = ArmPosterior(precision_matrix=np.eye(2) * 10_000, weighted_reward_sum=np.array([40_000.0, 0.0]))
    context = build_context(1500)

    sample = sample_predicted_reward(posterior, context, rng)

    assert sample == pytest.approx(4.0, abs=0.05)
