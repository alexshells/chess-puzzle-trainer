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

import math
from dataclasses import dataclass
from typing import Callable

import chess
import chess.engine

from ml.tablebase import TablebaseVerdict

# Ported directly from Lichess's own open-source puzzle generator
# (github.com/ornicar/lichess-puzzler, generator/util.py) — see the
# "Lichess Puzzle Generator" research note (CLAUDE.md's Phase 2.5 entry,
# 2026-09-11) for the full writeup of why this matters. Raw centipawns are
# not linear in how "decided" a position feels: the gap between +200 and
# +400 is meaningful, but the gap between +2000 and +4000 (two different
# ways of saying "hopeless") is not — this sigmoid squashes any score
# (including mate_score-collapsed mate scores, which saturate to ±1.0 here
# with room to spare) into a bounded, comparable win-probability-like scale.
_WIN_CHANCES_MULTIPLIER = -0.00368208


def win_chances(cp: int) -> float:
    """A win-probability-like value in [-1, 1] — see module docstring above."""
    return 2 / (1 + math.exp(_WIN_CHANCES_MULTIPLIER * cp)) - 1


_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


def material_balance(board: chess.Board, color: chess.Color) -> int:
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
class TacticalSharpness:
    """
    Structural "is this position tactically loaded" signals, all computed
    purely from board state (no engine call). Added after comparing 51,096
    real Lichess puzzle positions against 7,500 positions randomly sampled
    from real chess.com games (uncurated, no blunder filtering at all) —
    most differences between the two groups turned out to just be game
    phase/material reduction wearing different clothes (puzzles occur
    later, with fewer pieces left), but these four survived controlling for
    total_material at every band: puzzle positions have measurably more
    available checks, more hanging pieces, more material imbalance, and
    more pins than a regular position with the *same amount of material* —
    a genuinely independent "does this look tactically loaded" signal, not
    just a proxy for "this happened later in the game".
    """

    # Legal moves from this position that give check — puzzles average
    # ~3x regular positions at the same material level (the single
    # strongest signal found, Cohen's d=0.87 unconditional).
    num_checking_moves: int
    # The side to move's own pieces that are attacked and undefended.
    num_hanging_pieces: int
    # abs(material balance) — distinct from puzzle_position_eval_cp
    # (Stockfish's full positional judgment); this is pure material count.
    material_imbalance: int
    # Total pinned pieces on the board, either color.
    num_pinned_pieces: int


def tactical_sharpness(board: chess.Board) -> TacticalSharpness:
    stm = board.turn
    opp = not stm

    own_pieces = [sq for pt in _PIECE_VALUES for sq in board.pieces(pt, stm)]
    num_hanging = sum(
        1 for sq in own_pieces if board.is_attacked_by(opp, sq) and not board.is_attacked_by(stm, sq)
    )

    num_checking_moves = 0
    for move in board.legal_moves:
        board.push(move)
        if board.is_check():
            num_checking_moves += 1
        board.pop()

    num_pinned = sum(
        1 for sq in chess.SQUARES if (piece := board.piece_at(sq)) and board.is_pinned(piece.color, sq)
    )

    return TacticalSharpness(
        num_checking_moves=num_checking_moves,
        num_hanging_pieces=num_hanging,
        material_imbalance=abs(material_balance(board, stm)),
        num_pinned_pieces=num_pinned,
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
    baseline = material_balance(board_start, solver_color)
    board = board_start.copy()
    limit = len(moves) if max_plies is None else min(max_plies, len(moves))

    for i, move in enumerate(moves[:limit]):
        board.push(move)
        if i % 2 != 0:
            continue
        gain = material_balance(board, solver_color) - baseline
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
    # roughly-equal options (False) — decided in win-probability space (see
    # win_chances above), not from refutation_gap_cp's raw cp margin
    # directly. Why: under mate_score=100_000 collapsing, a real mate beats
    # a merely-strong second-best move (say +450cp, already a clearly won
    # position for practical purposes) by a huge raw cp margin — trivially
    # "forced" under a flat cp threshold despite both moves being
    # practically equivalent (this is the same "many roads lead to Rome"
    # failure mode game_import.py's decided-position check exists to catch
    # on the blunder-swing side; forced had the identical blind spot on the
    # refutation side, just never diagnosed until reading Lichess's own
    # generator). Verified against the real 51k-row Lichess sample
    # (2026-09-11): re-deriving forced from win_chances at a 0.3 gap
    # reclassifies 7.8% of previously-forced rows as not-forced — all cases
    # where the runner-up move was itself already practically decisive.
    # Overridden by an exact tablebase verdict when one is available and the
    # puzzle position is simplified enough (<=7 pieces) — see
    # tablebase.probe and analyse_puzzle_quality's tablebase_prober param.
    forced: bool
    # cp margin between the best move and the runner-up at the puzzle
    # position, per multipv=2. None when there was no second legal reply to
    # compare against (trivially forced in that case). Stored as raw cp —
    # still a model feature (see puzzle_features.py) — even though `forced`
    # itself is no longer derived from this directly (see forced's own note).
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
    # Structural "how tactically loaded is this" signals — see
    # TacticalSharpness/tactical_sharpness above. Also defaulted for the
    # same test-fixture-churn reason as the two fields above.
    num_checking_moves: int = 0
    num_hanging_pieces: int = 0
    material_imbalance: int = 0
    num_pinned_pieces: int = 0


def analyse_puzzle_quality(
    fen_before_setup: str,
    setup_move_uci: str,
    engine: chess.engine.SimpleEngine,
    *,
    depth: int,
    forced_win_chance_gap: float,
    decisive_material_gain: int,
    tablebase_prober: Callable[[chess.Board], TablebaseVerdict | None] | None = None,
) -> PuzzleQualityAnalysis | None:
    """
    Returns None if either the pre-setup or post-setup position has no legal
    moves (mate/stalemate edge cases) — not enough there to score.

    tablebase_prober, if given, is called on the puzzle position (i.e.
    tablebase.probe, or a fake in tests) to get an exact win/draw/loss
    verdict for simplified (<=7-piece) endgames — see tablebase.py. Its
    only_winning_move result overrides the win_chances-based `forced`
    determination when a verdict comes back; defaults to None (no probe at
    all) so this stays network-free and deterministic in tests unless a
    caller opts in — same "explicit opt-in, graceful no-op by default"
    shape as rating_model/quality_model elsewhere in this pipeline.
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
    # otherwise it's forced only if the win-probability gap clears the
    # threshold — see PuzzleQualityAnalysis.forced's docstring above for why
    # this is win_chances space, not the raw refutation_gap_cp margin.
    forced = (
        second_eval is None
        or win_chances(puzzle_position_eval_cp) - win_chances(second_eval) >= forced_win_chance_gap
    )

    if tablebase_prober is not None:
        tb_verdict = tablebase_prober(board_puzzle)
        if tb_verdict is not None:
            # Exact, not merely engine-probable — see module docstring on
            # tablebase.py for why this is strictly more trustworthy than
            # the win_chances-based judgment above when it applies.
            forced = tb_verdict.only_winning_move

    solving_pv = list(info_lines[0].get("pv", []))
    payoff = find_decisive_payoff(
        board_puzzle, solver_color, solving_pv, decisive_material_gain=decisive_material_gain
    )
    sharpness = tactical_sharpness(board_puzzle)

    return PuzzleQualityAnalysis(
        puzzle_position_eval_cp=puzzle_position_eval_cp,
        setup_swing_cp=eval_pre - eval_puzzle_blunderer_pov,
        forced=forced,
        refutation_gap_cp=refutation_gap_cp,
        solving_pv=solving_pv,
        has_decisive_payoff=payoff.reached,
        decisive_material_gain=payoff.material_gain,
        num_checking_moves=sharpness.num_checking_moves,
        num_hanging_pieces=sharpness.num_hanging_pieces,
        material_imbalance=sharpness.material_imbalance,
        num_pinned_pieces=sharpness.num_pinned_pieces,
    )
