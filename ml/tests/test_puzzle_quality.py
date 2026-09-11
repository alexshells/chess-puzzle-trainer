import chess

from ml.puzzle_quality import analyse_puzzle_quality, find_decisive_payoff, tactical_sharpness, total_material

FORCED_GAP_CP = 100
DECISIVE_MATERIAL_GAIN = 1

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
        FEN_BEFORE_SETUP,
        SETUP_MOVE,
        engine,
        depth=1,
        forced_gap_cp=FORCED_GAP_CP,
        decisive_material_gain=DECISIVE_MATERIAL_GAIN,
    )

    assert analysis is not None
    assert analysis.puzzle_position_eval_cp == 15
    assert analysis.setup_swing_cp == 40 - 15
    assert analysis.refutation_gap_cp == 105
    assert analysis.forced is True
    assert analysis.solving_pv == [_PV_MOVE]
    # e7e5 (the scripted "best line") doesn't capture anything — no payoff.
    assert analysis.has_decisive_payoff is False
    assert analysis.decisive_material_gain == 0


def test_not_forced_when_runner_up_is_close():
    engine = FakeEngine(
        [
            (40, [_PV_MOVE]),
            [(15, [_PV_MOVE]), (0, [_PV_MOVE])],  # gap of 15 — under forced_gap_cp
        ]
    )

    analysis = analyse_puzzle_quality(
        FEN_BEFORE_SETUP,
        SETUP_MOVE,
        engine,
        depth=1,
        forced_gap_cp=FORCED_GAP_CP,
        decisive_material_gain=DECISIVE_MATERIAL_GAIN,
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
        FEN_BEFORE_SETUP,
        SETUP_MOVE,
        engine,
        depth=1,
        forced_gap_cp=FORCED_GAP_CP,
        decisive_material_gain=DECISIVE_MATERIAL_GAIN,
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
        checkmate_fen,
        "f1g2",
        engine,
        depth=1,
        forced_gap_cp=FORCED_GAP_CP,
        decisive_material_gain=DECISIVE_MATERIAL_GAIN,
    )

    assert analysis is None
    assert engine.calls == 0


def test_computes_a_decisive_payoff_when_the_best_line_actually_wins_material():
    # A queen-and-mate-material blunder scenario: White (solver) forks
    # Black's king and queen with Nf6+, then wins the queen with Nxd7.
    engine = FakeEngine(
        [
            (999, [_PV_MOVE]),  # pre-setup eval (unused by this test)
            [
                (
                    15,
                    [chess.Move.from_uci("h5f6"), chess.Move.from_uci("e8f8"), chess.Move.from_uci("f6d7")],
                )
            ],
        ]
    )

    analysis = analyse_puzzle_quality(
        "4k3/p2q4/8/7N/8/8/7R/5K2 b - - 1 1",
        "a7a6",
        engine,
        depth=1,
        forced_gap_cp=FORCED_GAP_CP,
        decisive_material_gain=DECISIVE_MATERIAL_GAIN,
    )

    assert analysis is not None
    assert analysis.has_decisive_payoff is True
    assert analysis.decisive_material_gain == 9  # the queen, net of nothing lost


# --- find_decisive_payoff (moved here from game_import.py once it became a
# shared feature used by both training and inference — see puzzle_quality.py) ---

_FORK_FEN = "4k3/3q4/p7/7N/8/8/7R/5K2 w - - 0 2"
_FORK_MOVES = [chess.Move.from_uci("h5f6"), chess.Move.from_uci("e8f8"), chess.Move.from_uci("f6d7")]
_QUIET_MOVES = [
    chess.Move.from_uci("h5g3"),
    chess.Move.from_uci("a6a5"),
    chess.Move.from_uci("g3h5"),
    chess.Move.from_uci("a5a4"),
    chess.Move.from_uci("h5g3"),
]
_MATE_FEN = "7k/5ppp/1p6/8/8/8/R7/5K2 w - - 0 2"
_MATE_MOVES = [chess.Move.from_uci("a2a8")]


def test_find_decisive_payoff_reaches_material_gain_at_the_second_solver_move():
    board = chess.Board(_FORK_FEN)

    payoff = find_decisive_payoff(board, chess.WHITE, _FORK_MOVES, decisive_material_gain=DECISIVE_MATERIAL_GAIN)

    assert payoff.reached is True
    assert payoff.material_gain == 9
    assert payoff.ply_index == 2  # Nf6 (check only), Kf8 (reply), Nxd7 (the payoff)


def test_find_decisive_payoff_reaches_checkmate_immediately():
    board = chess.Board(_MATE_FEN)

    payoff = find_decisive_payoff(board, chess.WHITE, _MATE_MOVES, decisive_material_gain=DECISIVE_MATERIAL_GAIN)

    assert payoff.reached is True
    assert payoff.ply_index == 0


def test_find_decisive_payoff_never_reached_for_a_quiet_shuffle():
    board = chess.Board(_FORK_FEN)

    payoff = find_decisive_payoff(board, chess.WHITE, _QUIET_MOVES, decisive_material_gain=DECISIVE_MATERIAL_GAIN)

    assert payoff.reached is False
    assert payoff.material_gain == 0
    assert payoff.ply_index is None


def test_find_decisive_payoff_respects_max_plies():
    board = chess.Board(_FORK_FEN)

    # The real payoff is at ply_index=2, but a budget of 1 only allows the
    # check itself — not enough to see the queen actually get won.
    payoff = find_decisive_payoff(
        board, chess.WHITE, _FORK_MOVES, decisive_material_gain=DECISIVE_MATERIAL_GAIN, max_plies=1
    )

    assert payoff.reached is False


def test_find_decisive_payoff_only_checks_after_solver_moves():
    # A capture by the opponent (an odd index — an auto-played reply) must
    # never itself trigger a payoff, even though it changes the material
    # balance — here it makes things *worse* for the solver, but the point
    # is the parity check, not the sign.
    board = chess.Board("4k3/8/8/3p4/8/8/8/3QK3 w - - 0 1")  # White Qd1/Ke1, Black Ke8/pawn d5
    moves = [chess.Move.from_uci("d1d5"), chess.Move.from_uci("e8f8")]  # Qxd5 (payoff), then a quiet king move

    payoff = find_decisive_payoff(board, chess.WHITE, moves, decisive_material_gain=DECISIVE_MATERIAL_GAIN)

    assert payoff.reached is True
    assert payoff.ply_index == 0  # found right after Qxd5, not walked further


def test_total_material_sums_both_sides_excluding_kings():
    # White: rook(5) + knight(3) = 8. Black: queen(9) + pawn(1) = 10. 18 total.
    board = chess.Board(_FORK_FEN)

    assert total_material(board) == 18


def test_total_material_is_low_for_a_bare_endgame():
    # White: king + knight(3) only. Black: king + pawn(1) only. 4 total —
    # a real king-and-knight-vs-king-and-pawn study, the exact shape a real
    # 51k-row Lichess sample showed has almost nothing left to capture.
    board = chess.Board("8/8/8/6N1/5k1p/2K5/8/8 w - - 3 67")

    assert total_material(board) == 4


def test_tactical_sharpness_counts_checking_moves():
    # A real opening position (Italian-ish, White to move) — Bxf7+ is the
    # only legal move that gives check; White's own e4 pawn is undefended
    # and attacked by Black's knight on c6, i.e. hanging (num_hanging
    # counts the side-to-move's own pieces, not the opponent's).
    board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")

    result = tactical_sharpness(board)

    assert result.num_checking_moves == 1  # Bxf7+
    assert result.num_hanging_pieces == 1  # the e4 pawn


def test_tactical_sharpness_counts_pin_hanging_piece_and_imbalance():
    # White: bishop(3) + pawn(1) = 4. Black: knight(3). Imbalance = 1.
    # Black's knight on c6 is pinned to its king on e8 by the bishop on
    # b5, along the same diagonal, and is also hanging (undefended, under
    # attack, and — being pinned — literally cannot move to safety).
    board = chess.Board("4k3/8/2n5/1B6/8/8/4P3/4K3 b - - 0 1")

    result = tactical_sharpness(board)

    assert result.num_pinned_pieces == 1
    assert result.num_hanging_pieces == 1
    assert result.material_imbalance == 1
