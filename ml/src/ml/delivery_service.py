"""
Impure wiring around delivery_bandit.py's pure Thompson Sampling core —
same split as game_import.py's find_blunders (pure) vs run_import (impure).
Reads a user's personal puzzle pool and current rating from backend's
tables (external_metadata — read-only, see db.py's ownership-boundary
docstring), runs the bandit to pick an arm and a puzzle from that pool, and
records the decision (BanditPull) so a later star rating can be attributed
back to it and used to update that arm's belief.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ml.config import settings
from ml.db import BanditArmState, BanditPull, SessionLocal, puzzle_table, user_table
from ml.delivery_bandit import (
    ArmPosterior,
    DeliveryArm,
    build_context,
    choose_arm,
    initial_posterior,
    update_posterior,
)


@dataclass(frozen=True)
class PoolPuzzle:
    id: int
    rating: int
    forced: bool | None
    setup_swing_cp: int | None
    quality_score: float | None


def select_puzzle_for_arm(
    arm: DeliveryArm, pool: list[PoolPuzzle], user_rating: float, rng: np.random.Generator
) -> PoolPuzzle | None:
    """
    Pure puzzle-selection rule for one arm, given an already-fetched pool.
    Falls back to a uniform-random pick within the pool whenever an arm's
    preferred signal is missing on every candidate (e.g. nothing has a
    quality_score yet) — every arm should still manage to serve *something*
    if the user has any puzzles at all, rather than returning nothing.
    """
    if not pool:
        return None

    if arm is DeliveryArm.BEST_QUALITY:
        scored = [p for p in pool if p.quality_score is not None]
        if scored:
            return max(scored, key=lambda p: p.quality_score)
    elif arm is DeliveryArm.CLOSEST_RATING:
        return min(pool, key=lambda p: abs(p.rating - user_rating))
    elif arm is DeliveryArm.FORCED_CLEAN:
        forced = [p for p in pool if p.forced]
        if forced:
            return _random_choice(forced, rng)
    elif arm is DeliveryArm.BIGGEST_BLUNDER:
        swung = [p for p in pool if p.setup_swing_cp is not None]
        if swung:
            return max(swung, key=lambda p: p.setup_swing_cp)

    return _random_choice(pool, rng)


def _random_choice(pool: list[PoolPuzzle], rng: np.random.Generator) -> PoolPuzzle:
    return pool[int(rng.integers(len(pool)))]


def _load_pool(session: Session, user_id: int) -> list[PoolPuzzle]:
    rows = session.execute(
        select(
            puzzle_table.c.id,
            puzzle_table.c.rating,
            puzzle_table.c.forced,
            puzzle_table.c.setup_swing_cp,
            puzzle_table.c.quality_score,
        ).where(puzzle_table.c.owner_id == user_id)
    ).all()
    return [PoolPuzzle(*row) for row in rows]


def _load_user_rating(session: Session, user_id: int) -> float:
    row = session.execute(select(user_table.c.rating).where(user_table.c.id == user_id)).one()
    return float(row[0])


def _load_posterior(session: Session, arm: DeliveryArm) -> ArmPosterior:
    row = session.execute(select(BanditArmState).where(BanditArmState.arm == arm.value)).scalar_one_or_none()
    if row is None:
        return initial_posterior(prior_precision=settings.bandit_prior_precision)
    return ArmPosterior(
        precision_matrix=np.array(json.loads(row.precision_matrix)),
        weighted_reward_sum=np.array(json.loads(row.weighted_reward_sum)),
    )


def _save_posterior(session: Session, arm: DeliveryArm, posterior: ArmPosterior, pull_count_delta: int) -> None:
    row = session.execute(select(BanditArmState).where(BanditArmState.arm == arm.value)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row is None:
        session.add(
            BanditArmState(
                arm=arm.value,
                precision_matrix=json.dumps(posterior.precision_matrix.tolist()),
                weighted_reward_sum=json.dumps(posterior.weighted_reward_sum.tolist()),
                pull_count=pull_count_delta,
                updated_at=now,
            )
        )
    else:
        row.precision_matrix = json.dumps(posterior.precision_matrix.tolist())
        row.weighted_reward_sum = json.dumps(posterior.weighted_reward_sum.tolist())
        row.pull_count += pull_count_delta
        row.updated_at = now


def choose_puzzle_for_user(
    user_id: int, session: Session | None = None, rng: np.random.Generator | None = None
) -> int | None:
    """
    Runs one Thompson Sampling draw for this user's next "My Games" puzzle:
    picks an arm, applies that arm's selection rule to the user's own
    puzzle pool, and records a BanditPull so a later reward (see
    apply_reward) can be attributed back to this exact decision. Returns
    the chosen Puzzle id, or None if the user has no personal puzzles yet.
    """
    owns_session = session is None
    session = session or SessionLocal()
    rng = rng if rng is not None else np.random.default_rng()
    try:
        pool = _load_pool(session, user_id)
        if not pool:
            return None

        user_rating = _load_user_rating(session, user_id)
        context = build_context(user_rating)

        posteriors = {arm: _load_posterior(session, arm) for arm in DeliveryArm}
        chosen_arm = choose_arm(posteriors, context, rng)

        puzzle = select_puzzle_for_arm(chosen_arm, pool, user_rating, rng)
        assert puzzle is not None  # pool is non-empty; every arm falls back to a random pick

        session.add(
            BanditPull(
                user_id=user_id,
                puzzle_id=puzzle.id,
                arm=chosen_arm.value,
                context=json.dumps(context.tolist()),
                reward=None,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
        return puzzle.id
    finally:
        if owns_session:
            session.close()


def apply_reward(user_id: int, puzzle_id: int, stars: int, session: Session | None = None) -> bool:
    """
    Attributes a star rating back to the most recent not-yet-rewarded pull
    of this (user, puzzle), and updates that arm's posterior. Returns False
    if no matching pending pull is found (e.g. feedback on a puzzle that
    predates the bandit, or a duplicate reward call) — the caller should
    treat that as "nothing to update", not an error.
    """
    owns_session = session is None
    session = session or SessionLocal()
    try:
        pull = (
            session.execute(
                select(BanditPull)
                .where(BanditPull.user_id == user_id, BanditPull.puzzle_id == puzzle_id, BanditPull.reward.is_(None))
                .order_by(BanditPull.created_at.desc())
            )
            .scalars()
            .first()
        )
        if pull is None:
            return False

        pull.reward = float(stars)
        pull.rewarded_at = datetime.now(timezone.utc)

        arm = DeliveryArm(pull.arm)
        context = np.array(json.loads(pull.context))
        posterior = _load_posterior(session, arm)
        updated = update_posterior(posterior, context, float(stars), settings.bandit_noise_variance)
        _save_posterior(session, arm, updated, pull_count_delta=1)

        session.commit()
        return True
    finally:
        if owns_session:
            session.close()
