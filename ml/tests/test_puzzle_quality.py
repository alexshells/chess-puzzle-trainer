import chess

from ml.puzzle_quality import analyse_puzzle_quality

FORCED_GAP_CP = 100

# Any legal position works — analyse_puzzle_quality doesn't inspect the
# actual chess content, only the scripted engine responses below.
FEN_BEFORE_SETUP = chess.STARTING_FEN
SETUP_MOVE = "e2e4"

_PV_MOVE = chess.Move.from_uci("e7e5")


class FakeScore:
    def __init__(self, cp: int):
        self._cp = cp

    def pov(self, color: bool) -> "FakeScore":
        return self

    def score(self, mate_score: int | None = None) -> int:
        return self._cp


class FakeEngine:
    """One scripted response per call: a plain (eval_cp, pv) tuple for a
    normal analyse() call, or a list of such tuples for a multipv call."""

    def __init__(self, responses: list):
        self._responses = responses
        self.calls = 0

    def analyse(self, board: chess.Board, limit, *, multipv: int | None = None):
        response = self._responses[self.calls]
        self.calls += 1

        if multipv is not None:
            return [{"score": FakeScore(cp), "pv": pv} for cp, pv in response]

        eval_cp, pv = response
        return {"score": FakeScore(eval_cp), "pv": pv}


def test_computes_setup_swing_and_forced_refutation():
    engine = FakeEngine(
        [
            (40, [_PV_MOVE]),  # eval before the setup move, blunderer's POV
            [(15, [_PV_MOVE]), (-90, [_PV_MOVE])],  # at the puzzle position, multipv=2
        ]
    )

    analysis = analyse_puzzle_quality(
        FEN_BEFORE_SETUP, SETUP_MOVE, engine, depth=1, forced_gap_cp=FORCED_GAP_CP
    )

    assert analysis is not None
    assert analysis.puzzle_position_eval_cp == 15
    assert analysis.setup_swing_cp == 40 - 15
    assert analysis.refutation_gap_cp == 105
    assert analysis.forced is True
    assert analysis.solving_pv == [_PV_MOVE]


def test_not_forced_when_runner_up_is_close():
    engine = FakeEngine(
        [
            (40, [_PV_MOVE]),
            [(15, [_PV_MOVE]), (0, [_PV_MOVE])],  # gap of 15 — under forced_gap_cp
        ]
    )

    analysis = analyse_puzzle_quality(
        FEN_BEFORE_SETUP, SETUP_MOVE, engine, depth=1, forced_gap_cp=FORCED_GAP_CP
    )

    assert analysis is not None
    assert analysis.refutation_gap_cp == 15
    assert analysis.forced is False


def test_forced_when_no_second_legal_reply():
    engine = FakeEngine(
        [
            (40, [_PV_MOVE]),
            [(15, [_PV_MOVE])],  # only one line comes back
        ]
    )

    analysis = analyse_puzzle_quality(
        FEN_BEFORE_SETUP, SETUP_MOVE, engine, depth=1, forced_gap_cp=FORCED_GAP_CP
    )

    assert analysis is not None
    assert analysis.refutation_gap_cp is None
    assert analysis.forced is True


def test_returns_none_when_setup_position_has_no_legal_moves():
    # Fool's mate position — black is already checkmated, no setup move to
    # evaluate from here.
    checkmate_fen = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
    engine = FakeEngine([])

    analysis = analyse_puzzle_quality(
        checkmate_fen, "f1g2", engine, depth=1, forced_gap_cp=FORCED_GAP_CP
    )

    assert analysis is None
    assert engine.calls == 0
