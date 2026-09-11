"""
Puzzle-quality feature computation, shared between two callers that need the
exact same features computed the exact same way:

- game_import.py's find_blunders(), scoring candidates from a user's own
  chess.com games as it finds them.
- build_training_dataset.py, scoring a sample of already-published Lichess
  puzzles to build training data (see CLAUDE.md's Phase 2.5 note) — the
  whole point of training on that set is that a model trained on it can
  later score game_import.py's candidates, which only works if both sides
  compute features identically.

Both datasets give us the same three things for any candidate puzzle: the
position before some "setup" move, the setup move itself (the blunder that
creates the tactical opportunity), and nothing else — no engine evaluation.
Everything here is derived from just those two inputs, which is what keeps
it usable for both a live chess.com game and a static Lichess CSV row alike.
"""

from dataclasses import dataclass

import chess
import chess.engine

_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


def _material_balance(board: chess.Board, color: chess.Color) -> int:
    """Net material for `color` minus their opponent, in pawns (king excluded, standard values)."""
    balance = 0
    for piece_type, value in _PIECE_VALUES.items():
        balance += value * len(board.pieces(piece_type, color))
        balance -= value * len(board.pieces(piece_type, not color))
    return balance


def total_material(board: chess.Board) -> int:
    """
    Both sides combined, in pawns (king excluded, standard values) — used to
    tell a genuine endgame apart from a middlegame. Verified against a real
    51k-example Lichess sample: puzzles with no decisive payoff (see
    find_decisive_payoff) are markedly enriched for low total material —
    33% have <=14 vs. 8% of puzzles that do have a payoff. Inspecting actual
    examples confirmed why: a bare king-and-knight-vs-king-and-pawn study has
    almost nothing left to *capture*, so decisive_material_gain is close to
    structurally unsatisfiable there regardless of how good the puzzle is —
    the real "payoff" is technique (promoting, or catching the pawn), not a
    capture. See config.py's endgame_material_threshold and
    game_import.py's use of this for the hard-gate exemption it justifies.
    """
    return sum(
        value * len(board.pieces(piece_type, color))
        for piece_type, value in _PIECE_VALUES.items()
        for color in (chess.WHITE, chess.BLACK)
    )


@dataclass(frozen=True)
class DecisivePayoff:
    """
    Whether a solving line actually concludes somewhere concrete — a real
    complaint this exists to catch: a puzzle whose first move wins a pawn
    but whose remaining moves have "no concrete plan" isn't a satisfying
    puzzle just because the eval numbers look fine on paper.
    """

    reached: bool
    # Net material banked for the solving side at the payoff point (0 if
    # never reached).
    material_gain: int
    # 0-based index into the walked moves where the payoff was reached
    # (always an even index — solving lines start on a solver move and
    # alternate solver/reply); None if never reached.
    ply_index: int | None


def find_decisive_payoff(
    board_start: chess.Board,
    solver_color: chess.Color,
    moves: list[chess.Move],
    *,
    decisive_material_gain: int,
    max_plies: int | None = None,
) -> DecisivePayoff:
    """
    Walks `moves` (solver, reply, solver, reply, ...) from board_start and
    checks, after each solver move (even indices — an auto-played opponent
    reply at an odd index isn't something a payoff should be judged after),
    whether checkmate has been delivered or real material has actually been
    banked. Stops at the first such point rather than walking further, so a
    caller that wants "the shortest line to a real payoff" gets exactly
    that from `ply_index`. `max_plies` caps how much of `moves` gets walked
    at all (a display-length budget); omit it to consider the whole line,
    e.g. when this is a quality *feature* rather than something bounding
    what gets shown to a solver.
    """
    baseline = _material_balance(board_start, solver_color)
    board = board_start.copy()
    limit = len(moves) if max_plies is None else min(max_plies, len(moves))

    for i, move in enumerate(moves[:limit]):
        board.push(move)
        if i % 2 != 0:
            continue
        gain = _material_balance(board, solver_color) - baseline
        if board.is_checkmate() or gain >= decisive_material_gain:
            return DecisivePayoff(reached=True, material_gain=gain, ply_index=i)

    return DecisivePayoff(reached=False, material_gain=0, ply_index=None)


@dataclass(frozen=True)
class PuzzleQualityAnalysis:
    # Solver's POV, at the position right after the setup move — the eval
    # the solver is trying to preserve/convert by finding the right move.
    puzzle_position_eval_cp: int
    # How much the position dropped, from the *blundering* side's own POV,
    # purely as a result of playing the setup move — independent of what
    # anyone did afterwards. A big drop here is a bigger, more obvious
    # blunder having created the opportunity in the first place.
    setup_swing_cp: int
    # Whether the solving side has one clearly-best move (True) or several
    # roughly-equal options (False) — see refutation_gap_cp.
    forced: bool
    # cp margin between the best move and the runner-up at the puzzle
    # position, per multipv=2. None when there was no second legal reply to
    # compare against (trivially forced in that case).
    refutation_gap_cp: int | None
    # Engine's suggested line from the puzzle position — solution[1:] for
    # whichever caller is building a playable puzzle out of this.
    solving_pv: list[chess.Move]
    # Does solving_pv itself actually go anywhere concrete — mate, or real
    # material banked — within decisive_material_gain's bar? See
    # find_decisive_payoff. Computed over the *whole* solving_pv, not
    # truncated to any particular display-length budget — this is a quality
    # signal, not a "how much to show a solver" decision (that truncation
    # is game_import.py's own concern, using the same find_decisive_payoff
    # bounded by its own max_solver_moves). Defaulted (unlike the fields
    # above) purely so existing test fixtures that build a PuzzleQualityAnalysis
    # by hand for unrelated assertions don't all need updating — the one
    # production call site (below) always sets both explicitly regardless.
    has_decisive_payoff: bool = False
    decisive_material_gain: int = 0


def analyse_puzzle_quality(
    fen_before_setup: str,
    setup_move_uci: str,
    engine: chess.engine.SimpleEngine,
    *,
    depth: int,
    forced_gap_cp: int,
    decisive_material_gain: int,
) -> PuzzleQualityAnalysis | None:
    """
    Returns None if either the pre-setup or post-setup position has no legal
    moves (mate/stalemate edge cases) — not enough there to score.
    """
    limit = chess.engine.Limit(depth=depth)

    board_before = chess.Board(fen_before_setup)
    if board_before.is_game_over():
        return None
    blunderer_color = board_before.turn
    solver_color = not blunderer_color

    info_pre = engine.analyse(board_before, limit)
    eval_pre = info_pre["score"].pov(blunderer_color).score(mate_score=100_000)

    board_puzzle = board_before.copy()
    board_puzzle.push(chess.Move.from_uci(setup_move_uci))
    if board_puzzle.is_game_over():
        return None

    # multipv=2 so we can tell a forced/unique refutation from a position
    # where several moves win about equally well.
    info_lines = engine.analyse(board_puzzle, limit, multipv=2)
    if isinstance(info_lines, dict):
        info_lines = [info_lines]

    eval_puzzle_blunderer_pov = info_lines[0]["score"].pov(blunderer_color).score(mate_score=100_000)
    puzzle_position_eval_cp = info_lines[0]["score"].pov(solver_color).score(mate_score=100_000)
    if eval_pre is None or eval_puzzle_blunderer_pov is None or puzzle_position_eval_cp is None:
        return None

    second_eval = (
        info_lines[1]["score"].pov(solver_color).score(mate_score=100_000) if len(info_lines) > 1 else None
    )
    refutation_gap_cp = None if second_eval is None else puzzle_position_eval_cp - second_eval
    # No second legal reply to compare against is trivially forced;
    # otherwise it's forced only if the gap clears the threshold.
    forced = refutation_gap_cp is None or refutation_gap_cp >= forced_gap_cp

    solving_pv = list(info_lines[0].get("pv", []))
    payoff = find_decisive_payoff(
        board_puzzle, solver_color, solving_pv, decisive_material_gain=decisive_material_gain
    )

    return PuzzleQualityAnalysis(
        puzzle_position_eval_cp=puzzle_position_eval_cp,
        setup_swing_cp=eval_pre - eval_puzzle_blunderer_pov,
        forced=forced,
        refutation_gap_cp=refutation_gap_cp,
        solving_pv=solving_pv,
        has_decisive_payoff=payoff.reached,
        decisive_material_gain=payoff.material_gain,
    )
