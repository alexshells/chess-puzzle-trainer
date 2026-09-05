"""
Contextual Thompson Sampling over a fixed set of delivery "arms" — each arm
is a puzzle-*selection policy* (see DeliveryArm), not an individual puzzle.
A given personal puzzle only ever gets served to its one owner, essentially
once — there's no repeated-pull history to learn at the level of a single
puzzle the way classic bandit algorithms assume. Policies get pulled
constantly across every delivery for every user, which is what Thompson
Sampling actually needs in order to converge on anything.

Bayesian linear regression per arm: reward = w . context + noise. Each arm's
belief about w is a multivariate Normal, fully described by two sufficient
statistics — precision_matrix (A) and weighted_reward_sum (b). The posterior
mean is solve(A, b); the posterior covariance is inv(A). Nothing else is
stored anywhere this state persists (see db.py's BanditArmState) — no
separate "confidence" number, no magic constants, just these two arrays, on
purpose: the point is being able to load them straight into numpy/pandas
later and plot how each arm's estimate evolved, not decode an opaque blob.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np


class DeliveryArm(str, Enum):
    """
    Each value names a puzzle-selection policy, not an individual puzzle —
    see this module's docstring. RANDOM_BASELINE exists specifically so
    there's a "do nothing clever" control to compare the others against —
    without it there'd be no way to tell whether the bandit's favorite
    policy is actually earning its keep or whether users just rate personal
    puzzles a certain way regardless of how they're picked.
    """

    BEST_QUALITY = "best_quality"
    CLOSEST_RATING = "closest_rating"
    FORCED_CLEAN = "forced_clean"
    BIGGEST_BLUNDER = "biggest_blunder"
    RANDOM_BASELINE = "random_baseline"


# [intercept, scaled_rating] — see build_context().
CONTEXT_DIMENSION = 2


def build_context(user_rating: float) -> np.ndarray:
    """
    Rating is rescaled around a 1500 baseline onto a roughly [-2, 2] range —
    a fixed, simple transform, not a learned one — so the regression's
    weights stay on a comparable, interpretable scale instead of the raw
    ~400-3000 rating swamping the intercept term.
    """
    scaled_rating = (user_rating - 1500) / 500
    return np.array([1.0, scaled_rating])


@dataclass(frozen=True)
class ArmPosterior:
    """
    The complete belief state for one arm — nothing else exists. mean/
    covariance are derived properties, not stored fields, so they can never
    drift out of sync with the sufficient statistics that actually define
    them.
    """

    precision_matrix: np.ndarray  # (d, d)
    weighted_reward_sum: np.ndarray  # (d,)

    @property
    def mean(self) -> np.ndarray:
        return np.linalg.solve(self.precision_matrix, self.weighted_reward_sum)

    @property
    def covariance(self) -> np.ndarray:
        return np.linalg.inv(self.precision_matrix)


def initial_posterior(dimension: int = CONTEXT_DIMENSION, prior_precision: float = 1.0) -> ArmPosterior:
    """
    A weak prior centered on zero weights ("I have no idea yet, guess the
    middle of the reward scale"). prior_precision is the regularization
    strength — a *smaller* value means a wider, weaker starting belief.
    """
    return ArmPosterior(
        precision_matrix=np.eye(dimension) * prior_precision,
        weighted_reward_sum=np.zeros(dimension),
    )


def sample_predicted_reward(posterior: ArmPosterior, context: np.ndarray, rng: np.random.Generator) -> float:
    """One Thompson Sampling draw: sample a weight vector from this arm's current belief, predict this context's reward with it."""
    sampled_weights = rng.multivariate_normal(posterior.mean, posterior.covariance)
    return float(sampled_weights @ context)


def choose_arm(
    posteriors: dict[DeliveryArm, ArmPosterior], context: np.ndarray, rng: np.random.Generator
) -> DeliveryArm:
    """The whole algorithm: sample a predicted reward per arm, pick the arm with the highest *sample* — not the highest mean."""
    sampled = {arm: sample_predicted_reward(post, context, rng) for arm, post in posteriors.items()}
    return max(sampled, key=sampled.get)


def update_posterior(posterior: ArmPosterior, context: np.ndarray, reward: float, noise_variance: float) -> ArmPosterior:
    """
    Closed-form Bayesian linear regression update — the conjugate-prior
    property that makes this tractable with no numerical fitting step.
    noise_variance is the assumed variance of the reward around w . context,
    a fixed configured value (see config.py) rather than something learned
    per arm — that would need real machinery (Normal-Inverse-Gamma) for a
    benefit not worth it at this data scale yet.
    """
    new_precision = posterior.precision_matrix + np.outer(context, context) / noise_variance
    new_weighted_sum = posterior.weighted_reward_sum + context * reward / noise_variance
    return ArmPosterior(new_precision, new_weighted_sum)
