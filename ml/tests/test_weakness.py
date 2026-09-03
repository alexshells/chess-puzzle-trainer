from ml.weakness import AttemptRecord, biased_themes, compute_theme_weaknesses, expected_score


def test_expected_score_is_even_at_equal_ratings():
    assert expected_score(1500, 1500) == 0.5


def test_expected_score_favors_higher_rated_player():
    # A 1700 vs a 1500-rated puzzle should be favored to solve it.
    assert expected_score(1700, 1500) > 0.5
    assert expected_score(1500, 1700) < 0.5


def test_theme_missed_more_than_expected_is_flagged():
    # User rated 1500 solving 1500-rated puzzles should succeed ~50% of the
    # time by rating alone. Missing all 10 "fork" attempts at that level is a
    # real weak spot, not noise.
    attempts = [AttemptRecord(success=False, puzzle_rating=1500, themes=["fork"]) for _ in range(10)]

    [weakness] = compute_theme_weaknesses(user_rating=1500, attempts=attempts, min_sample_size=5)

    assert weakness.theme == "fork"
    assert weakness.sample_size == 10
    assert weakness.observed_miss_rate == 1.0
    assert weakness.expected_miss_rate == 0.5
    assert weakness.miss_rate_vs_expected == 0.5


def test_theme_below_min_sample_size_is_dropped():
    attempts = [AttemptRecord(success=False, puzzle_rating=1500, themes=["fork"]) for _ in range(3)]

    weaknesses = compute_theme_weaknesses(user_rating=1500, attempts=attempts, min_sample_size=5)

    assert weaknesses == []


def test_puzzle_with_multiple_themes_counts_toward_each():
    attempts = [AttemptRecord(success=False, puzzle_rating=1500, themes=["fork", "middlegame"]) for _ in range(5)]

    weaknesses = compute_theme_weaknesses(user_rating=1500, attempts=attempts, min_sample_size=5)

    assert {w.theme for w in weaknesses} == {"fork", "middlegame"}
    assert all(w.sample_size == 5 for w in weaknesses)


def test_solving_better_than_expected_is_not_a_weakness():
    # 1500-rated user solving 1200-rated puzzles should nearly always succeed;
    # actually doing so isn't a weak spot, even at a "worse than 50%" glance.
    attempts = [AttemptRecord(success=True, puzzle_rating=1200, themes=["endgame"]) for _ in range(10)]

    weaknesses = compute_theme_weaknesses(user_rating=1500, attempts=attempts, min_sample_size=5)

    assert weaknesses[0].miss_rate_vs_expected < 0


def test_biased_themes_excludes_non_weaknesses_and_respects_limit():
    attempts = [
        *[AttemptRecord(success=False, puzzle_rating=1500, themes=["fork"]) for _ in range(10)],
        *[AttemptRecord(success=False, puzzle_rating=1500, themes=["pin"]) for _ in range(8)],
        *[AttemptRecord(success=True, puzzle_rating=1500, themes=["skewer"]) for _ in range(10)],
    ]

    weaknesses = compute_theme_weaknesses(user_rating=1500, attempts=attempts, min_sample_size=5)

    themes = biased_themes(weaknesses, limit=1)

    assert themes == ["fork"]  # worst miss rate, and "skewer" (a strength) never appears
