"""
find_blunders is the move-walking/threshold logic that matters here, kept
testable without a real engine — same spirit as test_weakness.py keeping
compute_theme_weaknesses testable without a real DB. The fake engine below
returns a pre-programmed eval per call rather than actually analysing the
position, so a test controls exactly which move looks like a blunder.

Eval numbers are entirely scripted (FakeScore ignores the real position),
but any move that find_blunders or puzzle_quality.find_decisive_payoff
actually *pushes* onto a board — the real game's own moves, and a
candidate's solving_pv once it's accepted — has to be a real legal move,
since both now walk a real chess.Board. Most fixtures below use one small
custom position (a white knight fork of a king+queen, from a fixed FEN)
rather than a real opening, so the "solving line" itself is a genuine,
verifiable tactic rather than a placeholder move repeated for its UCI shape
alone.

quality_model tests here cover find_blunders' own gating logic (does it
reject/accept based on a given quality_score); the model's own prediction
behavior is puzzle_quality_model.py's test file's job, not this one's — a
FakeQualityModel below returns a fixed probability by construction.
"""

import chess
import numpy as np

from ml.game_import import _select_games_to_process, find_blunders

TARGET = "player_one"
FORCED_WIN_CHANCE_GAP = 0.3
MAX_SOLVER_MOVES = 3
DECISIVE_MATERIAL_GAIN = 1
QUALITY_SCORE_THRESHOLD = 0.5
# 0 disables the endgame exemption for every test that isn't specifically
# about it — the fork/mate fixtures below (18 and 9 points of material
# respectively) would otherwise trip it, since a real config default (see
# config.py's endgame_material_threshold) is well above both.
ENDGAME_MATERIAL_THRESHOLD = 0

# 1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 — White ("player_one") "blunders" on move 3
# per the fake engine's scripted evals below; the actual chess content only
# needs to be a legal game, not a real blunder. Used only by tests that
# never reach solving_pv's legality-sensitive code path (forced=False or
# already-decided rejections happen before any candidate is built).
GAME_PGN = """[White "player_one"]
[Black "player_two"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 *
"""

_PV_MOVE = chess.Move.from_uci("e2e4")  # placeholder — legal only from the starting position; never used as a best-line pv
# Legal single-move "best lines" for GAME_PGN's two checkpoints specifically
# (after 1.e4 e5, and after 1.e4 e5 2.Nf3 Nc6) — analyse_puzzle_quality now
# always walks a candidate's best-line pv (for the decisive-payoff feature)
# regardless of what find_blunders' gates end up doing with the result, so
# even a "this gets rejected anyway" fixture needs a real legal move there.
_CP1_MOVE = chess.Move.from_uci("g1f3")  # Nf3, legal after 1.e4 e5
_CP2_MOVE = chess.Move.from_uci("f1c4")  # Bc4, legal after 1.e4 e5 2.Nf3 Nc6

# --- Knight-fork scenario ---
# White: Ke1, Nh5, Rh2. Black: Ke8, Qd7, Pa7. White's knight forks the king
# (check) and queen via Nf6; the queen is undefended, so Nxd7 next wins it
# outright. One checkpoint (before White's 2nd move): last_move = Black's a6
# (an unrelated filler move, same "narrative doesn't need to match the real
# tactic" as the original placeholder-PV tests — only legality matters).
_FORK_FEN = "4k3/p2q4/8/7N/8/8/7R/4K3 w - - 0 1"
_FORK_PGN = f"""[White "player_one"]
[Black "player_two"]
[FEN "{_FORK_FEN}"]
[SetUp "1"]

1. Kf1 a6 2. Rh4 *
"""
_FORK_MOVE = chess.Move.from_uci("h5f6")  # check, no capture — not decisive by itself
_FORK_REPLY = chess.Move.from_uci("e8f8")  # Black's only-ish reply to the check
_FORK_CAPTURE = chess.Move.from_uci("f6d7")  # Nxd7 — wins the queen, decisive
_FORK_PV = [_FORK_MOVE, _FORK_REPLY, _FORK_CAPTURE]

# A quiet shuffle from the exact same checkpoint that never captures
# anything or gives mate — used to test that a candidate with no concrete
# payoff anywhere in its solving line gets rejected outright.
_QUIET_PV = [
    chess.Move.from_uci("h5g3"),
    chess.Move.from_uci("a6a5"),
    chess.Move.from_uci("g3h5"),
    chess.Move.from_uci("a5a4"),
    chess.Move.from_uci("h5g3"),
]

# --- Back-rank mate scenario ---
# White: Ke1, Ra2. Black: Kh8, Pb7/Pf7/Pg7/Ph7 (boxed in). Ra8 is mate — the
# whole 8th rank (including g8, Black king's only nominal escape) is covered
# by the rook, and f7/g7/h7 block every other square.
_MATE_FEN = "7k/1p3ppp/8/8/8/8/R7/4K3 w - - 0 1"
_MATE_PGN = f"""[White "player_one"]
[Black "player_two"]
[FEN "{_MATE_FEN}"]
[SetUp "1"]

1. Kf1 b6 2. Ra3 *
"""
_MATE_MOVE = chess.Move.from_uci("a2a8")


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


def _find_fork_blunders(engine: FakeEngine, **overrides):
    kwargs = dict(
        pgn_text=_FORK_PGN,
        target_username=TARGET,
        player_rating=1200,
        game_id="test-game",
        game_url="https://www.chess.com/game/live/12345",
        engine=engine,
        depth=1,
        win_chance_swing_threshold=0.6,
        decided_position_cp=600,
        forced_win_chance_gap=FORCED_WIN_CHANCE_GAP,
        max_solver_moves=MAX_SOLVER_MOVES,
        decisive_material_gain=DECISIVE_MATERIAL_GAIN,
        quality_score_threshold=QUALITY_SCORE_THRESHOLD,
        endgame_material_threshold=ENDGAME_MATERIAL_THRESHOLD,
    )
    kwargs.update(overrides)
    return find_blunders(**kwargs)


def test_flags_a_move_that_drops_eval_past_the_threshold_and_marks_it_forced():
    # Puzzle-position eval drops from +15 (best line: the fork) to -400 (what
    # White actually played, Rh4) — a win_chances swing of ~0.65, over
    # win_chance_swing_threshold (0.6). The runner-up move (-200) trails the
    # best move (15) by a win_chances gap of ~0.38 — over
    # forced_win_chance_gap (0.3), so this counts as forced.
    engine = FakeEngine(
        [
            (200, [_PV_MOVE]),  # pre-setup eval before Rh4 (unused by assertions)
            [(15, _FORK_PV), (-200, [_PV_MOVE])],  # puzzle position (multipv=2) — best line is the fork
            (-400, [_PV_MOVE]),  # after Rh4 (the actual blunder)
        ]
    )

    candidates = _find_fork_blunders(engine)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.external_id == "chesscom:test-game:2"
    assert candidate.game_url == "https://www.chess.com/game/live/12345?move=2"
    assert candidate.rating == 1200
    # solution[0] is the opponent's move (a6) that led into the puzzle
    # position; solution[1:] is the engine's suggested line from there —
    # the fork, its reply, and the capture that actually wins the queen.
    assert candidate.solution == ["a7a6", "h5f6", "e8f8", "f6d7"]
    assert candidate.forced is True
    assert candidate.refutation_gap_cp == 215
    assert candidate.setup_swing_cp == 200 - 15


def test_rejects_a_candidate_that_is_still_completely_winning_afterward():
    # The puzzle position already has a forced mate available (99997 ~
    # mate in 3). White's actual move (Rh4) "only" leaves them up massive
    # material (700), not mate — a raw swing of 99297 (trivially over the
    # *old* flat blunder_threshold_cp), and the mate line beat the next-best
    # non-mating line by a raw 99397cp (trivially "forced" under the old
    # flat threshold too) — but practically nothing changed: White was
    # completely winning before this move and completely winning after it.
    # In win_chances space both effects vanish on their own: the swing is
    # only ~0.14 (nowhere near win_chance_swing_threshold, 0.6) since mate
    # and "merely" +700 both round to "totally winning" — no separate
    # decided-position gate needed, this is the real fix for the original
    # complaint: "you're completely winning no matter what the move is."
    engine = FakeEngine(
        [
            (99999, [_PV_MOVE]),  # pre-setup eval (unused)
            [(99997, _FORK_PV), (600, [_PV_MOVE])],  # puzzle position — mate available
            (700, [_PV_MOVE]),  # after Rh4 — still crushing, just not mate
        ]
    )

    candidates = _find_fork_blunders(engine)

    assert candidates == []


def test_rejects_a_candidate_when_a_second_move_wins_almost_as_well():
    # Same shape as the forced case above, but the runner-up (0) trails the
    # best move (15) by a win_chances gap of only ~0.03 — well under
    # forced_win_chance_gap (0.3), so several moves win here (the "many
    # roads lead to Rome" case, e.g. a drawn-out K+R-vs-K mate where several
    # moves all win, just at different speeds). Not a fair puzzle to grade
    # against one "correct" answer, so it should be rejected outright — even
    # though the win_chances swing on its own clears win_chance_swing_threshold
    # (15 -> -400 is a ~0.65 swing). Never reaches find_blunders' own
    # decisive-payoff gate (rejected on forced first), but
    # analyse_puzzle_quality always walks the best-line pv regardless — see
    # _CP1_MOVE/_CP2_MOVE.
    engine = FakeEngine(
        [
            (999, [_PV_MOVE]),  # pre-setup eval before Nf3
            [(20, [_CP1_MOVE]), (18, [_PV_MOVE])],  # puzzle position before Nf3
            (10, [_PV_MOVE]),  # after Nf3
            (100, [_PV_MOVE]),  # pre-setup eval before Bxc6
            [(15, [_CP2_MOVE]), (0, [_PV_MOVE])],  # puzzle position before Bxc6 — not forced
            (-400, [_PV_MOVE]),  # after Bxc6 — still evaluated, forced is checked last
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
        win_chance_swing_threshold=0.6,
        decided_position_cp=600,
        forced_win_chance_gap=FORCED_WIN_CHANCE_GAP,
        max_solver_moves=MAX_SOLVER_MOVES,
        decisive_material_gain=DECISIVE_MATERIAL_GAIN,
        quality_score_threshold=QUALITY_SCORE_THRESHOLD,
        endgame_material_threshold=ENDGAME_MATERIAL_THRESHOLD,
    )

    assert candidates == []
    assert engine.calls == 6


def test_marks_forced_when_there_is_no_second_legal_reply():
    # Only one line comes back from multipv=2 (e.g. a single legal reply) —
    # trivially forced, with no gap to report.
    engine = FakeEngine(
        [
            (50, [_PV_MOVE]),  # pre-setup eval before Rh4
            [(15, _FORK_PV)],  # puzzle position — single line
            (-400, [_PV_MOVE]),  # after Rh4
        ]
    )

    candidates = _find_fork_blunders(engine)

    assert len(candidates) == 1
    assert candidates[0].forced is True
    assert candidates[0].refutation_gap_cp is None
    assert candidates[0].setup_swing_cp == 50 - 15
    assert candidates[0].solution == ["a7a6", "h5f6", "e8f8", "f6d7"]


def test_cuts_the_solution_short_once_a_decisive_payoff_is_reached():
    # The engine's own line runs two moves past the queen capture (padding
    # that doesn't add anything a solver can verify) — max_solver_moves=3
    # would allow all 5 plies, but the solution should stop right after
    # Nxd7 wins the queen, not pad out to the full budget.
    long_pv = _FORK_PV + [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")]
    engine = FakeEngine(
        [
            (200, [_PV_MOVE]),
            [(15, long_pv), (-200, [_PV_MOVE])],
            (-400, [_PV_MOVE]),
        ]
    )

    candidates = _find_fork_blunders(engine)

    assert len(candidates) == 1
    assert candidates[0].solution == ["a7a6", "h5f6", "e8f8", "f6d7"]


def test_rejects_a_candidate_when_the_solving_line_never_reaches_a_concrete_payoff():
    # Same forced/blunder shape as the flagging test above, but the "best
    # line" is a quiet shuffle that never captures anything or gives mate —
    # winning the eval argument on paper isn't the same as a puzzle with an
    # actual, checkable payoff (the real complaint this fixes: a puzzle
    # whose first move wins a pawn but whose remaining moves have "no
    # concrete plan"). Should be rejected outright.
    engine = FakeEngine(
        [
            (200, [_PV_MOVE]),
            [(15, _QUIET_PV), (-200, [_PV_MOVE])],
            (-400, [_PV_MOVE]),
        ]
    )

    candidates = _find_fork_blunders(engine)

    assert candidates == []


def test_accepts_an_endgame_candidate_with_no_payoff_if_forced():
    # Identical shape to the rejection test above — same quiet, no-capture
    # line — but this time the puzzle position is treated as a genuine
    # endgame (the fork fixture's 18 points of total material is at or
    # below a real endgame_material_threshold like 20). There's often
    # almost nothing left to capture in a real endgame study, so `forced`
    # (already guaranteed true here) is accepted on its own — see
    # config.py's endgame_material_threshold and the real 51k-row Lichess
    # analysis behind it.
    engine = FakeEngine(
        [
            (200, [_PV_MOVE]),
            [(15, _QUIET_PV), (-200, [_PV_MOVE])],
            (-400, [_PV_MOVE]),
        ]
    )

    candidates = _find_fork_blunders(engine, endgame_material_threshold=20)

    assert len(candidates) == 1
    # No payoff to truncate at — shows the full solver-move budget instead.
    assert candidates[0].solution == ["a7a6"] + [m.uci() for m in _QUIET_PV]


def test_solution_ends_the_moment_checkmate_is_delivered():
    # White's actual move (Ra3) misses a back-rank mate (Ra8#) that was
    # sitting right there — about as decisive a payoff as a puzzle gets, and
    # it should end the solution immediately (one solver move), not require
    # anything further.
    engine = FakeEngine(
        [
            (999, [_PV_MOVE]),  # pre-setup eval before Ra3 (unused)
            [(99_997, [_MATE_MOVE])],  # puzzle position — single line, mate
            (100, [_PV_MOVE]),  # after Ra3 (the actual blunder)
        ]
    )

    candidates = find_blunders(
        _MATE_PGN,
        TARGET,
        player_rating=1200,
        game_id="mate-game",
        game_url="https://www.chess.com/game/live/99999",
        engine=engine,
        depth=1,
        win_chance_swing_threshold=0.6,
        decided_position_cp=600,
        forced_win_chance_gap=FORCED_WIN_CHANCE_GAP,
        max_solver_moves=MAX_SOLVER_MOVES,
        decisive_material_gain=DECISIVE_MATERIAL_GAIN,
        quality_score_threshold=QUALITY_SCORE_THRESHOLD,
        endgame_material_threshold=ENDGAME_MATERIAL_THRESHOLD,
    )

    assert len(candidates) == 1
    assert candidates[0].solution == ["b7b6", "a2a8"]


def test_skips_blunders_in_an_already_lost_position():
    # Already down 700cp before the move — a further mistake there isn't an
    # interesting puzzle, so no candidate should be produced even though the
    # eval still drops by more than the threshold. The guard fails right
    # after the puzzle-position multipv call, so no "after" call happens for
    # that iteration (only 5 of the 6 scripted responses get consumed).
    # Rejected before find_blunders' own decisive-payoff gate is reached, but
    # analyse_puzzle_quality always walks the best-line pv regardless of that
    # later rejection — see _CP1_MOVE/_CP2_MOVE.
    engine = FakeEngine(
        [
            (10, [_PV_MOVE]),  # pre-setup eval, iteration 1
            [(0, [_CP1_MOVE]), (-5, [_PV_MOVE])],  # puzzle position, iteration 1
            (0, [_PV_MOVE]),  # after, iteration 1 — no swing, no candidate
            (-650, [_PV_MOVE]),  # pre-setup eval, iteration 2 (unused by assertions)
            [(-700, [_CP2_MOVE]), (-750, [_PV_MOVE])],  # puzzle position, iteration 2 — already lost
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
        win_chance_swing_threshold=0.6,
        decided_position_cp=600,
        forced_win_chance_gap=FORCED_WIN_CHANCE_GAP,
        max_solver_moves=MAX_SOLVER_MOVES,
        decisive_material_gain=DECISIVE_MATERIAL_GAIN,
        quality_score_threshold=QUALITY_SCORE_THRESHOLD,
        endgame_material_threshold=ENDGAME_MATERIAL_THRESHOLD,
    )

    assert candidates == []


def test_uses_the_rating_model_when_given_instead_of_player_rating():
    engine = FakeEngine(
        [
            (200, [_PV_MOVE]),
            [(15, _FORK_PV), (-200, [_PV_MOVE])],
            (-400, [_PV_MOVE]),
        ]
    )

    candidates = _find_fork_blunders(engine, rating_model=FakeRatingModel(1837.6))

    assert len(candidates) == 1
    # Rounded model output, not player_rating (1200) — the model was provided.
    assert candidates[0].rating == 1838


def test_computes_quality_score_when_a_quality_model_is_given():
    engine = FakeEngine(
        [
            (200, [_PV_MOVE]),
            [(15, _FORK_PV), (-200, [_PV_MOVE])],
            (-400, [_PV_MOVE]),
        ]
    )

    candidates = _find_fork_blunders(engine, quality_model=FakeQualityModel(0.73))

    assert len(candidates) == 1
    assert candidates[0].quality_score == 0.73


def test_quality_score_is_none_when_no_quality_model_is_given():
    engine = FakeEngine(
        [
            (200, [_PV_MOVE]),
            [(15, _FORK_PV), (-200, [_PV_MOVE])],
            (-400, [_PV_MOVE]),
        ]
    )

    candidates = _find_fork_blunders(engine)

    assert len(candidates) == 1
    assert candidates[0].quality_score is None


def test_rejects_a_candidate_the_quality_model_scores_below_threshold():
    # Same forced/blunder/payoff shape as the flagging test — everything
    # else about this candidate is fine — but the quality model itself
    # predicts it's below-median (0.2 < the 0.5 threshold). This is the
    # real "is this a good puzzle" judgment replacing what used to be a
    # hand-picked cp/pawn cutoff alone.
    engine = FakeEngine(
        [
            (200, [_PV_MOVE]),
            [(15, _FORK_PV), (-200, [_PV_MOVE])],
            (-400, [_PV_MOVE]),
        ]
    )

    candidates = _find_fork_blunders(engine, quality_model=FakeQualityModel(0.2))

    assert candidates == []


def test_accepts_a_candidate_exactly_at_the_quality_threshold():
    engine = FakeEngine(
        [
            (200, [_PV_MOVE]),
            [(15, _FORK_PV), (-200, [_PV_MOVE])],
            (-400, [_PV_MOVE]),
        ]
    )

    candidates = _find_fork_blunders(engine, quality_model=FakeQualityModel(QUALITY_SCORE_THRESHOLD))

    assert len(candidates) == 1
    assert candidates[0].quality_score == QUALITY_SCORE_THRESHOLD


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
        win_chance_swing_threshold=0.6,
        decided_position_cp=600,
        forced_win_chance_gap=FORCED_WIN_CHANCE_GAP,
        max_solver_moves=MAX_SOLVER_MOVES,
        decisive_material_gain=DECISIVE_MATERIAL_GAIN,
        quality_score_threshold=QUALITY_SCORE_THRESHOLD,
        endgame_material_threshold=ENDGAME_MATERIAL_THRESHOLD,
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
