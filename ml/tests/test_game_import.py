"""
find_blunders is the move-walking/threshold logic that matters here, kept
testable without a real engine — same spirit as test_weakness.py keeping
compute_theme_weaknesses testable without a real DB. The fake engine below
returns a pre-programmed eval per call rather than actually analysing the
position, so a test controls exactly which move looks like a blunder.
"""

import chess

from ml.game_import import find_blunders

TARGET = "player_one"

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
    """Returns one scripted (eval_cp, pv) response per call, in order."""

    def __init__(self, responses: list[tuple[int, list[chess.Move]]]):
        self._responses = responses
        self.calls = 0

    def analyse(self, board: chess.Board, limit) -> dict:
        eval_cp, pv = self._responses[self.calls]
        self.calls += 1
        return {"score": FakeScore(eval_cp), "pv": pv}


def test_flags_a_move_that_drops_eval_past_the_threshold():
    # White's move 2 (Nf3): small drop, below threshold — not a blunder.
    # White's move 3 (Bxc6): eval drops from +15 to -300, a 315cp swing.
    engine = FakeEngine(
        [
            (20, [_PV_MOVE]),  # before Nf3
            (10, [_PV_MOVE]),  # after Nf3
            (15, [_PV_MOVE]),  # before Bxc6
            (-300, [_PV_MOVE]),  # after Bxc6
        ]
    )

    candidates = find_blunders(
        GAME_PGN,
        TARGET,
        player_rating=1200,
        game_id="test-game",
        engine=engine,
        depth=1,
        blunder_threshold_cp=250,
        decided_position_cp=600,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.external_id == "chesscom:test-game:4"
    assert candidate.rating == 1200
    # solution[0] is the opponent's move (Nc6) that led into the puzzle
    # position; solution[1:] is the engine's suggested line from there.
    assert candidate.solution[0] == "b8c6"
    assert candidate.solution[1] == "e2e4"


def test_skips_blunders_in_an_already_lost_position():
    # Already down 700cp before the move — a further mistake there isn't an
    # interesting puzzle, so no candidate should be produced even though the
    # eval still drops by more than the threshold.
    engine = FakeEngine(
        [
            (0, [_PV_MOVE]),
            (0, [_PV_MOVE]),
            (-700, [_PV_MOVE]),
            (-1000, [_PV_MOVE]),
        ]
    )

    candidates = find_blunders(
        GAME_PGN,
        TARGET,
        player_rating=1200,
        game_id="test-game",
        engine=engine,
        depth=1,
        blunder_threshold_cp=250,
        decided_position_cp=600,
    )

    assert candidates == []


def test_ignores_games_the_target_did_not_play_in():
    engine = FakeEngine([])

    candidates = find_blunders(
        GAME_PGN,
        "someone_else",
        player_rating=1200,
        game_id="test-game",
        engine=engine,
        depth=1,
        blunder_threshold_cp=250,
        decided_position_cp=600,
    )

    assert candidates == []
    assert engine.calls == 0
