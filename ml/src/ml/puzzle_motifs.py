"""
Rule-based tactical-motif tagging for a finished puzzle candidate — hand-
written geometric/material detectors, no ML anywhere in this file. Ported
(simplified in places, noted per-detector) directly from Lichess's own
open-source puzzle generator's tagger (tagger/cook.py in
github.com/ornicar/lichess-puzzler, see CLAUDE.md's "Lichess Puzzle
Generator" research note) after confirming this really is how the platform
this whole product measures itself against actually does it — 44 hand-
written detector functions there, zero learned models.

Deliberately not exhaustive: this covers a first, well-tested subset (mate,
fork, hangingPiece, pin, discoveredCheck/doubleCheck, sacrifice, endgame) —
enough to exercise every mapped category `PuzzleCategoryMapper` (backend/)
already understands except Skewer/KingAttack/DefensiveMove, which aren't
implemented yet. A tactical idea that doesn't match one of these tags
receives no tag at all, same closed-world limitation Lichess's own tagger
has (see the research note's limitations audit, L5) — adding a new motif
later is a new function here, not a change to the shared ones.

`tag_puzzle` takes the exact same (fen, solution) shape every consumer of a
puzzle already has (BlunderCandidate.fen/.solution, or a Lichess CSV row's
FEN/Moves) — solution[0] is the opponent's setup move that led into the
puzzle position, solution[1:] is the solver's own continuing line,
alternating solver/reply. `pov` (the solver) is `not` whoever's turn it was
at `fen`, the same convention established throughout puzzle_quality.py.
"""

import chess

from ml.puzzle_quality import material_balance, tactical_sharpness, total_material

_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}
# Fork detection only: a king can never actually be "hanging" (chess doesn't
# allow capturing it), but a check is exactly as fork-relevant as attacking
# any other undefended piece — giving it a value above every other piece
# guarantees `more_valuable` treats "this move also gives check" as a
# legitimate second target, the same way Lichess's own fork() does with its
# king_values dict.
_KING_VALUES = {**_PIECE_VALUES, chess.KING: 99}


def _walk(fen: str, solution: list[str]) -> tuple[list[tuple[chess.Board, chess.Move]], chess.Board]:
    """
    Returns (nodes, final_board) — nodes[i] is (board *before* move i, move
    i) for every move in `solution`, 0-indexed the same way solution itself
    is: index 0 is the opponent's setup move, odd indices are the solver's
    own moves, even indices >0 are the opponent's auto-played replies. Same
    indexing convention Lichess's own tagger uses for `puzzle.mainline`.
    """
    board = chess.Board(fen)
    nodes = []
    for uci in solution:
        move = chess.Move.from_uci(uci)
        nodes.append((board.copy(), move))
        board.push(move)
    return nodes, board


def _is_fork(board_before: chess.Board, move: chess.Move, pov: chess.Color) -> bool:
    """
    Simplified from Lichess's fork() — attacks 2+ opponent non-pawn pieces
    from the square just moved to, where each is either more valuable than
    the attacker or outright hanging (undefended). Doesn't replicate their
    "attacker isn't itself standing somewhere unsafe" guard.
    """
    board_after = board_before.copy()
    board_after.push(move)
    moved_type = board_after.piece_type_at(move.to_square)
    if moved_type is None or moved_type == chess.KING:
        return False

    targets = 0
    for square in board_after.attacks(move.to_square):
        piece = board_after.piece_at(square)
        if piece is None or piece.color == pov or piece.piece_type == chess.PAWN:
            continue
        more_valuable = _KING_VALUES[piece.piece_type] > _KING_VALUES[moved_type]
        hanging = not board_after.is_attacked_by(not pov, square)
        if more_valuable or hanging:
            targets += 1
    return targets > 1


def _is_hanging_capture(board_before: chess.Board, move: chess.Move) -> bool:
    """
    Did this move capture a non-pawn piece that was undefended at the time —
    "the solver just scooped up a free piece." Simplified from Lichess's
    hanging_piece(), which additionally excludes a capture that was itself
    just a fair recapture; this version doesn't distinguish that case.
    """
    captured = board_before.piece_at(move.to_square)
    if captured is None or captured.piece_type == chess.PAWN:
        return False
    return not board_before.is_attacked_by(captured.color, move.to_square)


def _check_kind(board_before: chess.Board, move: chess.Move) -> tuple[bool, bool]:
    """
    Returns (discovered, double) for the check (if any) this move delivers.
    `discovered` is True whenever a checking piece other than the one that
    just moved is present — true both for a "pure" discovered check (the
    moved piece itself doesn't check) and for a discovered check that also
    happens to double-check (the moved piece checks too, on top of the
    piece it uncovered).
    """
    board_after = board_before.copy()
    board_after.push(move)
    checkers = board_after.checkers()
    if not checkers:
        return False, False
    discovered = any(square != move.to_square for square in checkers)
    double = len(checkers) > 1
    return discovered, double


def _is_sacrifice(puzzle_position: chess.Board, nodes: list[tuple[chess.Board, chess.Move]]) -> bool:
    """
    Does the solver's own material total, relative to the puzzle's starting
    position (right after the opponent's setup move — what the solver
    actually inherits), ever drop by 2 or more at any point along the
    solving line (excluding a promotion, which changes material without
    "giving something up") — ported directly from Lichess's sacrifice().

    `nodes` is the *full* walk (opponent's setup move at index 0, then
    alternating solver/reply) — walked sequentially so every push() stays
    legal, but only checked after the solver's own moves (odd indices).
    """
    if not nodes:
        return False
    pov = puzzle_position.turn
    baseline = material_balance(puzzle_position, pov)
    board = nodes[0][0].copy()
    for i, (_, move) in enumerate(nodes):
        board.push(move)
        if i % 2 == 0:  # even indices: the opponent's setup move (0) and replies (2, 4, ...)
            continue
        if move.promotion:
            continue
        if material_balance(board, pov) - baseline <= -2:
            return True
    return False


def tag_puzzle(fen: str, solution: list[str], *, endgame_material_threshold: int) -> list[str]:
    """
    Returns Lichess-style raw theme tags (a subset — see module docstring)
    for a finished puzzle candidate. Safe to call on any (fen, solution)
    that's already known to be a *valid* puzzle (find_blunders' own gates
    already ran) — this doesn't re-verify forced/decisive-payoff/etc., it
    only describes what's tactically present.
    """
    nodes, final_board = _walk(fen, solution)
    pov = not chess.Board(fen).turn
    solver_nodes = nodes[1::2]  # solution[0] is the opponent's setup move, not a solver move

    tags: list[str] = []

    if final_board.is_checkmate():
        tags.append("mate")

    if any(_is_fork(board_before, move, pov) for board_before, move in solver_nodes):
        tags.append("fork")

    if solver_nodes and _is_hanging_capture(*solver_nodes[0]):
        tags.append("hangingPiece")

    puzzle_position = nodes[0][0].copy()
    puzzle_position.push(nodes[0][1])
    # Simplified from Lichess's pin_prevents_attack/pin_prevents_escape (does
    # a pin specifically enable *this* tactic) — this just asks whether any
    # piece on the board is pinned at all, reusing tactical_sharpness's own
    # pin count (puzzle_quality.py) rather than re-deriving it.
    if tactical_sharpness(puzzle_position).num_pinned_pieces > 0:
        tags.append("pin")

    discovered = any(_check_kind(board_before, move)[0] for board_before, move in solver_nodes)
    double = any(_check_kind(board_before, move)[1] for board_before, move in solver_nodes)
    if discovered:
        tags.append("discoveredCheck")
    if double:
        tags.append("doubleCheck")

    if _is_sacrifice(puzzle_position, nodes):
        tags.append("sacrifice")

    if total_material(puzzle_position) <= endgame_material_threshold:
        tags.append("endgame")

    return tags
