"""
Phase 1 of the personalization vision (see design doc §1): mine a player's
attempt history for pattern types (Lichess theme tags) where their miss rate
is worse than their overall rating predicts.

Pure, DB-free functions here so the math is unit-testable on its own —
`mine_user_weaknesses` in this module is the only piece that touches the
database, wiring these functions to a real user's attempt history.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class AttemptRecord:
    success: bool
    puzzle_rating: int
    themes: list[str]


@dataclass(frozen=True)
class ThemeWeakness:
    theme: str
    sample_size: int
    observed_miss_rate: float
    expected_miss_rate: float
    # observed - expected: positive means missing this theme more than the
    # player's overall rating predicts they should — the actual training signal.
    miss_rate_vs_expected: float


def expected_score(user_rating: float, puzzle_rating: float) -> float:
    """
    Elo-style expected win probability for `user_rating` against a puzzle
    rated `puzzle_rating`. Same logistic shape as Glicko-2's E() function;
    simplified by not weighting by rating deviation, since attempts don't
    carry a historical RD snapshot (only the player's *current* Glicko state
    is stored — see the design doc's "Not modeling yet" note). Good enough
    for a coarse expected-miss-rate baseline, not for a rating update.
    """
    return 1.0 / (1.0 + 10 ** ((puzzle_rating - user_rating) / 400.0))


def compute_theme_weaknesses(
    user_rating: float,
    attempts: list[AttemptRecord],
    min_sample_size: int,
) -> list[ThemeWeakness]:
    """
    Aggregates attempts per theme (a puzzle tagged ["fork","endgame"] counts
    toward both), then compares each theme's observed miss rate against the
    average miss rate the player's rating alone would predict for those same
    puzzles. Themes below `min_sample_size` are dropped as too noisy to act on.
    Sorted worst-first (highest miss_rate_vs_expected).
    """
    totals: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0, "misses": 0, "expected_miss_sum": 0.0})

    for attempt in attempts:
        miss_probability = 1.0 - expected_score(user_rating, attempt.puzzle_rating)
        for theme in attempt.themes:
            bucket = totals[theme]
            bucket["n"] += 1
            bucket["misses"] += 0 if attempt.success else 1
            bucket["expected_miss_sum"] += miss_probability

    weaknesses = []
    for theme, bucket in totals.items():
        n = int(bucket["n"])
        if n < min_sample_size:
            continue
        observed = bucket["misses"] / n
        expected = bucket["expected_miss_sum"] / n
        weaknesses.append(
            ThemeWeakness(
                theme=theme,
                sample_size=n,
                observed_miss_rate=observed,
                expected_miss_rate=expected,
                miss_rate_vs_expected=observed - expected,
            )
        )

    weaknesses.sort(key=lambda w: w.miss_rate_vs_expected, reverse=True)
    return weaknesses


def biased_themes(weaknesses: list[ThemeWeakness], limit: int = 3) -> list[str]:
    """Only themes actually missed *more* than expected — never bias toward a strength."""
    return [w.theme for w in weaknesses if w.miss_rate_vs_expected > 0][:limit]


def mine_user_weaknesses(session, user_id: int, min_sample_size: int) -> list[ThemeWeakness]:
    """Computes weaknesses from live attempt history and replaces this user's cached rows."""
    import json

    from sqlalchemy import select

    from ml.db import UserPatternWeakness, puzzle_attempt_table, puzzle_table, user_table

    user_row = session.execute(select(user_table.c.rating).where(user_table.c.id == user_id)).first()
    if user_row is None:
        return []
    user_rating = user_row.rating

    rows = session.execute(
        select(puzzle_attempt_table.c.success, puzzle_table.c.rating, puzzle_table.c.themes)
        .join(puzzle_table, puzzle_table.c.id == puzzle_attempt_table.c.puzzle_id)
        .where(puzzle_attempt_table.c.user_id == user_id)
    ).all()

    attempts = [
        AttemptRecord(success=row.success, puzzle_rating=row.rating, themes=json.loads(row.themes) if row.themes else [])
        for row in rows
    ]

    weaknesses = compute_theme_weaknesses(user_rating, attempts, min_sample_size)

    session.query(UserPatternWeakness).filter(UserPatternWeakness.user_id == user_id).delete()
    computed_at = datetime.now(timezone.utc)
    for weakness in weaknesses:
        session.add(
            UserPatternWeakness(
                user_id=user_id,
                theme=weakness.theme,
                miss_rate_vs_expected=weakness.miss_rate_vs_expected,
                sample_size=weakness.sample_size,
                computed_at=computed_at,
            )
        )
    session.commit()

    return weaknesses
