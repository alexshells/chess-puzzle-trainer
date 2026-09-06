"""
find_blunders is the move-walking/threshold logic that matters here, kept
testable without a real engine — same spirit as test_weakness.py keeping
compute_theme_weaknesses testable without a real DB. The fake engine below
returns a pre-programmed eval per call rather than actually analysing the
position, so a test controls exactly which move looks like a blunder.
"""

import chess
import numpy as np

from ml.game_import import _select_games_to_process, find_blunders

TARGET = "player_one"
FORCED_GAP_CP = 100
MAX_SOLVER_MOVES = 3

# 1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 — White ("player_one") "blunders" on move 3
# per the fake engine's scripted evals below; the actual chess content only
# needs to be a legal game, not a real blunder.
GAME_PGN = """[White "player_one"]
[Black "player_two"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 *
"""

_PV_MOVE = chess.Move.from_uci("e2e4")


class FakeScore:
    def __init__(self, cp: int):
        self._cp = cp

    def pov(self, color: bool) -> "FakeScore":
        return self

    def score(self, mate_score: int | None = None) -> int:
        return self._cp


class FakeEngine:
    """
    Returns one scripted response per call, in order. A response is either a
    plain (eval_cp, pv) tuple — for a normal analyse() call (the "before the
    setup move" eval, and the "after target's actual move" eval) — or a list
    of up to two such tuples, best line first, for a multipv=2 "at the
    puzzle position" call. Each target-turn iteration makes up to three
    calls in that order: pre-setup, puzzle-position (multipv), after.
    """

    def __init__(self, responses: list):
        self._responses = responses
        self.calls = 0

    def analyse(self, board: chess.Board, limit, *, multipv: int | None = None) -> dict | list[dict]:
        response = self._responses[self.calls]
        self.calls += 1

        if multipv is not None:
            return [{"score": FakeScore(cp), "pv": pv} for cp, pv in response]

        eval_cp, pv = response
        return {"score": FakeScore(eval_cp), "pv": pv}


class FakeRatingModel:
    """Mimics the sklearn Pipeline interface puzzle_rating_model.predict() calls — model.predict(X)[0]."""

    def __init__(self, rating: float):
        self._rating = rating

    def predict(self, X) -> np.ndarray:
        return np.array([self._rating])


class FakeQualityModel:
    """Mimics the sklearn Pipeline interface puzzle_quality_model.predict() calls — model.predict_proba(X)[0, 1]."""

    def __init__(self, probability: float):
        self._probability = probability

    def predict_proba(self, X) -> np.ndarray:
        return np.array([[1 - self._probability, self._probability]])


def test_flags_a_move_that_drops_eval_past_the_threshold_and_marks_it_forced():
    # White's move 2 (Nf3): small drop, below threshold — not a blunder.
    # White's move 3 (Bxc6): puzzle-position eval drops from +15 to -300, a
    # 315cp swing, and the runner-up move (-90) trails the best move (15) by
    # 105cp — over the 100cp forced_gap_cp, so this counts as forced.
    engine = FakeEngine(
        [
            (999, [_PV_MOVE]),  # pre-setup eval before Nf3 (unused by assertions)
            [(20, [_PV_MOVE]), (18, [_PV_MOVE])],  # puzzle position before Nf3 (multipv=2)
            (10, [_PV_MOVE]),  # after Nf3
            (200, [_PV_MOVE]),  # pre-setup eval before Bxc6
            [(15, [_PV_MOVE]), (-90, [_PV_MOVE])],  # puzzle position before Bxc6 (multipv=2)
            (-300, [_PV_MOVE]),  # after Bxc6
        ]
    )

    candidates = find_blunders(
        GAME_PGN,
        TARGET,
        player_rating=1200,
        game_id="test-game",
        game_url="https://www.chess.com/game/live/12345",
        engine=engine,
        depth=1,
        blunder_threshold_cp=250,
        decided_position_cp=600,
        forced_gap_cp=FORCED_GAP_CP,
        max_solver_moves=MAX_SOLVER_MOVES,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.external_id == "chesscom:test-game:4"
    # ?move=4 matches external_id's ply (4) — verified live against a real
    # chess.com game that this deep-links to the puzzle's exact starting
    # position, not just the game (see game_import.py's game_url comment).
    assert candidate.game_url == "https://www.chess.com/game/live/12345?move=4"
    assert candidate.rating == 1200
    # solution[0] is the opponent's move (Nc6) that led into the puzzle
    # position; solution[1:] is the engine's suggested line from there.
    assert candidate.solution[0] == "b8c6"
    assert candidate.solution[1] == "e2e4"
    assert candidate.forced is True
    assert candidate.refutation_gap_cp == 105
    assert candidate.setup_swing_cp == 200 - 15


def test_marks_not_forced_when_a_second_move_wins_almost_as_well():
    # Same shape as above, but the runner-up (0) trails the best move (15)
    # by only 15cp — well under forced_gap_cp, so several moves win here and
    # it isn't a "there's exactly one right answer" puzzle.
    engine = FakeEngine(
        [
            (999, [_PV_MOVE]),  # pre-setup eval before Nf3
            [(20, [_PV_MOVE]), (18, [_PV_MOVE])],  # puzzle position before Nf3
            (10, [_PV_MOVE]),  # after Nf3
            (100, [_PV_MOVE]),  # pre-setup eval before Bxc6
            [(15, [_PV_MOVE]), (0, [_PV_MOVE])],  # puzzle position before Bxc6
            (-300, [_PV_MOVE]),  # after Bxc6
        ]
    )

    candidates = find_blunders(
        GAME_PGN,
        TARGET,
        player_rating=1200,
        game_id="test-game",
        game_url="https://www.chess.com/game/live/12345",
        engine=engine,
        depth=1,
        blunder_threshold_cp=250,
        decided_position_cp=600,
        forced_gap_cp=FORCED_GAP_CP,
        max_solver_moves=MAX_SOLVER_MOVES,
    )

    assert len(candidates) == 1
    assert candidates[0].forced is False
    assert candidates[0].refutation_gap_cp == 15
    assert candidates[0].setup_swing_cp == 100 - 15


def test_marks_forced_when_there_is_no_second_legal_reply():
    # Only one line comes back from multipv=2 (e.g. a single legal reply) —
    # trivially forced, with no gap to report.
    engine = FakeEngine(
        [
            (999, [_PV_MOVE]),  # pre-setup eval before Nf3
            [(20, [_PV_MOVE])],  # puzzle position before Nf3 — single line
            (10, [_PV_MOVE]),  # after Nf3
            (50, [_PV_MOVE]),  # pre-setup eval before Bxc6
            [(15, [_PV_MOVE])],  # puzzle position before Bxc6 — single line
            (-300, [_PV_MOVE]),  # after Bxc6
        ]
    )

    candidates = find_blunders(
        GAME_PGN,
        TARGET,
        player_rating=1200,
        game_id="test-game",
        game_url="https://www.chess.com/game/live/12345",
        engine=engine,
        depth=1,
        blunder_threshold_cp=250,
        decided_position_cp=600,
        forced_gap_cp=FORCED_GAP_CP,
        max_solver_moves=MAX_SOLVER_MOVES,
    )

    assert len(candidates) == 1
    assert candidates[0].forced is True
    assert candidates[0].refutation_gap_cp is None
    assert candidates[0].setup_swing_cp == 50 - 15


def test_truncates_the_solution_to_max_solver_moves():
    # A 7-ply PV would otherwise mean 4 solver moves — more than
    # MAX_SOLVER_MOVES (3) allows, so it should be cut to 2*3-1=5 plies,
    # ending on the solver's 3rd move rather than running further.
    long_pv = [chess.Move.from_uci(uci) for uci in ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6", "d2d3"]]
    engine = FakeEngine(
        [
            (999, [_PV_MOVE]),  # pre-setup eval before Nf3 (unused)
            [(20, [_PV_MOVE]), (18, [_PV_MOVE])],  # puzzle position before Nf3 — small swing, not a candidate
            (10, [_PV_MOVE]),  # after Nf3
            (200, [_PV_MOVE]),  # pre-setup eval before Bxc6
            [(15, long_pv), (-90, long_pv)],  # puzzle position before Bxc6 (multipv=2) — long_pv is the best line
            (-300, [_PV_MOVE]),  # after Bxc6
        ]
    )

    candidates = find_blunders(
        GAME_PGN,
        TARGET,
        player_rating=1200,
        game_id="test-game",
        game_url="https://www.chess.com/game/live/12345",
        engine=engine,
        depth=1,
        blunder_threshold_cp=250,
        decided_position_cp=600,
        forced_gap_cp=FORCED_GAP_CP,
        max_solver_moves=3,
    )

    assert len(candidates) == 1
    # solution[0] is the opponent's setup move; solution[1:] is capped at 5
    # (2*3-1) of long_pv's 7 moves — ending on a solver move (index 4 = the
    # 3rd solver move: solver, reply, solver, reply, solver).
    solution = candidates[0].solution
    assert len(solution) == 1 + 5
    assert solution[1:] == ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"]


def test_skips_blunders_in_an_already_lost_position():
    # Already down 700cp before the move — a further mistake there isn't an
    # interesting puzzle, so no candidate should be produced even though the
    # eval still drops by more than the threshold. The guard fails right
    # after the puzzle-position multipv call, so no "after" call happens for
    # that iteration (only 5 of the 6 scripted responses get consumed).
    engine = FakeEngine(
        [
            (10, [_PV_MOVE]),  # pre-setup eval, iteration 1
            [(0, [_PV_MOVE]), (-5, [_PV_MOVE])],  # puzzle position, iteration 1
            (0, [_PV_MOVE]),  # after, iteration 1 — no swing, no candidate
            (-650, [_PV_MOVE]),  # pre-setup eval, iteration 2 (unused by assertions)
            [(-700, [_PV_MOVE]), (-750, [_PV_MOVE])],  # puzzle position, iteration 2 — already lost
            (-1000, [_PV_MOVE]),  # never consumed — guard fails before this would be called
        ]
    )

    candidates = find_blunders(
        GAME_PGN,
        TARGET,
        player_rating=1200,
        game_id="test-game",
        game_url="https://www.chess.com/game/live/12345",
        engine=engine,
        depth=1,
        blunder_threshold_cp=250,
        decided_position_cp=600,
        forced_gap_cp=FORCED_GAP_CP,
        max_solver_moves=MAX_SOLVER_MOVES,
    )

    assert candidates == []


def test_uses_the_rating_model_when_given_instead_of_player_rating():
    engine = FakeEngine(
        [
            (999, [_PV_MOVE]),  # pre-setup eval before Nf3
            [(20, [_PV_MOVE]), (18, [_PV_MOVE])],  # puzzle position before Nf3
            (10, [_PV_MOVE]),  # after Nf3
            (200, [_PV_MOVE]),  # pre-setup eval before Bxc6
            [(15, [_PV_MOVE]), (-90, [_PV_MOVE])],  # puzzle position before Bxc6
            (-300, [_PV_MOVE]),  # after Bxc6
        ]
    )

    candidates = find_blunders(
        GAME_PGN,
        TARGET,
        player_rating=1200,
        game_id="test-game",
        game_url="https://www.chess.com/game/live/12345",
        engine=engine,
        depth=1,
        blunder_threshold_cp=250,
        decided_position_cp=600,
        forced_gap_cp=FORCED_GAP_CP,
        max_solver_moves=MAX_SOLVER_MOVES,
        rating_model=FakeRatingModel(1837.6),
    )

    assert len(candidates) == 1
    # Rounded model output, not player_rating (1200) — the model was provided.
    assert candidates[0].rating == 1838


def test_computes_quality_score_when_a_quality_model_is_given():
    engine = FakeEngine(
        [
            (999, [_PV_MOVE]),  # pre-setup eval before Nf3
            [(20, [_PV_MOVE]), (18, [_PV_MOVE])],  # puzzle position before Nf3
            (10, [_PV_MOVE]),  # after Nf3
            (200, [_PV_MOVE]),  # pre-setup eval before Bxc6
            [(15, [_PV_MOVE]), (-90, [_PV_MOVE])],  # puzzle position before Bxc6
            (-300, [_PV_MOVE]),  # after Bxc6
        ]
    )

    candidates = find_blunders(
        GAME_PGN,
        TARGET,
        player_rating=1200,
        game_id="test-game",
        game_url="https://www.chess.com/game/live/12345",
        engine=engine,
        depth=1,
        blunder_threshold_cp=250,
        decided_position_cp=600,
        forced_gap_cp=FORCED_GAP_CP,
        max_solver_moves=MAX_SOLVER_MOVES,
        quality_model=FakeQualityModel(0.73),
    )

    assert len(candidates) == 1
    assert candidates[0].quality_score == 0.73


def test_quality_score_is_none_when_no_quality_model_is_given():
    engine = FakeEngine(
        [
            (999, [_PV_MOVE]),
            [(20, [_PV_MOVE]), (18, [_PV_MOVE])],
            (10, [_PV_MOVE]),
            (200, [_PV_MOVE]),
            [(15, [_PV_MOVE]), (-90, [_PV_MOVE])],
            (-300, [_PV_MOVE]),
        ]
    )

    candidates = find_blunders(
        GAME_PGN,
        TARGET,
        player_rating=1200,
        game_id="test-game",
        game_url="https://www.chess.com/game/live/12345",
        engine=engine,
        depth=1,
        blunder_threshold_cp=250,
        decided_position_cp=600,
        forced_gap_cp=FORCED_GAP_CP,
        max_solver_moves=MAX_SOLVER_MOVES,
    )

    assert len(candidates) == 1
    assert candidates[0].quality_score is None


def test_ignores_games_the_target_did_not_play_in():
    engine = FakeEngine([])

    candidates = find_blunders(
        GAME_PGN,
        "someone_else",
        player_rating=1200,
        game_id="test-game",
        game_url="https://www.chess.com/game/live/12345",
        engine=engine,
        depth=1,
        blunder_threshold_cp=250,
        decided_position_cp=600,
        forced_gap_cp=FORCED_GAP_CP,
        max_solver_moves=MAX_SOLVER_MOVES,
    )

    assert candidates == []
    assert engine.calls == 0


def _game(game_id: str) -> dict:
    return {"uuid": game_id}


def test_select_games_processes_everything_when_budget_covers_it_all():
    games = [_game("a"), _game("b"), _game("c")]

    to_process, month_fully_processed = _select_games_to_process(games, already_scanned_ids=set(), remaining_budget=10)

    assert [g["uuid"] for g in to_process] == ["a", "b", "c"]
    assert month_fully_processed is True


def test_select_games_stops_at_the_budget_and_reports_incomplete():
    games = [_game("a"), _game("b"), _game("c")]

    to_process, month_fully_processed = _select_games_to_process(games, already_scanned_ids=set(), remaining_budget=2)

    # This is the exact bug this function fixes: a month cut off by the
    # budget must never be reported as fully processed, or the caller would
    # advance last_archive past it and permanently skip "c".
    assert [g["uuid"] for g in to_process] == ["a", "b"]
    assert month_fully_processed is False


def test_select_games_skips_already_scanned_ones_for_free():
    games = [_game("a"), _game("b"), _game("c")]

    # Budget of 1 would normally only allow one game — but "a" is already
    # scanned, so it doesn't consume any of the budget, and both "b" and
    # "c" fit... except "c" doesn't fit a budget of 1, so only "b" does.
    to_process, month_fully_processed = _select_games_to_process(
        games, already_scanned_ids={"a"}, remaining_budget=1
    )

    assert [g["uuid"] for g in to_process] == ["b"]
    assert month_fully_processed is False


def test_select_games_is_fully_processed_when_only_already_scanned_games_remain():
    games = [_game("a"), _game("b")]

    # Zero budget left, but everything here was already scanned in a
    # previous run — this month IS done, and last_archive should be free to
    # advance past it even though there's no budget to spare.
    to_process, month_fully_processed = _select_games_to_process(
        games, already_scanned_ids={"a", "b"}, remaining_budget=0
    )

    assert to_process == []
    assert month_fully_processed is True


def test_select_games_is_not_fully_processed_when_budget_is_zero_and_work_remains():
    games = [_game("a")]

    to_process, month_fully_processed = _select_games_to_process(games, already_scanned_ids=set(), remaining_budget=0)

    assert to_process == []
    assert month_fully_processed is False


def test_select_games_handles_an_empty_game_list():
    to_process, month_fully_processed = _select_games_to_process([], already_scanned_ids=set(), remaining_budget=10)

    assert to_process == []
    assert month_fully_processed is True
