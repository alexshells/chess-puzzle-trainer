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


def analyse_puzzle_quality(
    fen_before_setup: str,
    setup_move_uci: str,
    engine: chess.engine.SimpleEngine,
    *,
    depth: int,
    forced_gap_cp: int,
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

    return PuzzleQualityAnalysis(
        puzzle_position_eval_cp=puzzle_position_eval_cp,
        setup_swing_cp=eval_pre - eval_puzzle_blunderer_pov,
        forced=forced,
        refutation_gap_cp=refutation_gap_cp,
        solving_pv=list(info_lines[0].get("pv", [])),
    )
