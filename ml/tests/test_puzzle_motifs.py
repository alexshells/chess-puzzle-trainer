import chess

from ml.puzzle_motifs import tag_puzzle

# Every fixture's `solution` starts with the opponent's setup move
# (solution[0]) — the same convention as BlunderCandidate.solution and
# find_blunders' own puzzle FEN ("fen" is the position *before* that move).
# All positions/lines were verified legal directly against a real
# chess.Board before being hardcoded here.

# Disables the endgame tag for fixtures that aren't specifically testing it —
# every fixture below has more material than this, so it never fires
# incidentally.
NO_ENDGAME = 0


def test_tags_a_fork_that_attacks_a_king_and_an_undefended_queen():
    # White knight forks Black's king (check) and queen (undefended) via
    # Nf6, then wins the queen outright with Nxd7 — the same real-world
    # scenario used throughout test_game_import.py's fork fixtures.
    fen = "4k3/p2q4/8/7N/8/8/7R/5K2 b - - 0 1"
    solution = ["a7a6", "h5f6", "e8f8", "f6d7"]

    assert tag_puzzle(fen, solution, endgame_material_threshold=NO_ENDGAME) == ["fork"]


def test_fork_needs_a_second_target_beyond_the_check_itself():
    # A check on its own, with nothing else on the board to attack, isn't a
    # fork — a fork needs two genuine targets, and a lone king attack (even
    # though it counts as one, per the fix above) is never enough by itself.
    fen = "4k3/8/8/8/8/8/8/R3K3 b - - 0 1"
    solution = ["e8d8", "a1a8"]  # Ra8+ — only the king is attacked, no second target

    assert "fork" not in tag_puzzle(fen, solution, endgame_material_threshold=NO_ENDGAME)


def test_tags_hanging_piece_when_the_first_solver_move_captures_undefended_material():
    # Black's rook on a8 is completely undefended; White's queen scoops it
    # up as the very first solving move.
    fen = "r3k3/7p/8/8/8/8/8/Q3K3 b - - 0 1"
    solution = ["h7h6", "a1a8"]

    assert tag_puzzle(fen, solution, endgame_material_threshold=NO_ENDGAME) == ["hangingPiece"]


def test_does_not_tag_hanging_piece_for_a_defended_capture():
    # Same shape, but a second black rook on b8 now defends a8 along the
    # 8th rank — capturing it isn't "scooping up a free piece".
    fen = "rr2k3/7p/8/8/8/8/8/Q3K3 b - - 0 1"
    solution = ["h7h6", "a1a8"]

    assert "hangingPiece" not in tag_puzzle(fen, solution, endgame_material_threshold=NO_ENDGAME)


def test_tags_pin_when_a_piece_is_pinned_at_the_puzzle_position():
    # White's bishop pins Black's knight to its own king along the diagonal
    # b5-c6-d7-e8 — present at the puzzle position itself (right after the
    # opponent's setup move), no solver move even needed to detect it.
    fen = "4k3/7p/2n5/1B6/8/8/8/4K3 b - - 0 1"
    solution = ["h7h6"]

    assert tag_puzzle(fen, solution, endgame_material_threshold=NO_ENDGAME) == ["pin"]


def test_tags_a_discovered_check_but_not_double_check():
    # White's rook on d1 is blocked by its own knight on d5. Moving the
    # knight away (Nb6) uncovers the rook's check on Black's king — the
    # knight itself doesn't attack d8, so this is a discovered check only.
    fen = "3k4/7p/8/3N4/8/8/8/3RK3 b - - 0 1"
    solution = ["h7h6", "d5b6"]

    assert tag_puzzle(fen, solution, endgame_material_threshold=NO_ENDGAME) == ["discoveredCheck"]


def test_tags_both_discovered_and_double_check():
    # White's knight on e5 sits on the bishop's b2-h8 diagonal. Ng6 both
    # uncovers the bishop's check on h8 *and* itself attacks h8 — a
    # discovered check that's also a double check.
    fen = "7k/p7/8/4N3/8/8/1B6/4K3 b - - 0 1"
    solution = ["a7a6", "e5g6"]

    tags = tag_puzzle(fen, solution, endgame_material_threshold=NO_ENDGAME)

    assert set(tags) == {"discoveredCheck", "doubleCheck"}


def test_tags_sacrifice_when_solver_material_drops_after_a_recapture():
    # White sacrifices its queen (Qd5, attacked by Black's knight) to open
    # a line — the drop only shows up once Black's knight actually recaptures
    # and the solver's next move is evaluated, exactly like a real "give up
    # the queen for an attack" puzzle would play out.
    fen = "4k3/7p/5n2/8/8/8/3Q4/4K3 b - - 0 1"
    solution = ["h7h6", "d2d5", "f6d5", "e1d1"]

    assert tag_puzzle(fen, solution, endgame_material_threshold=NO_ENDGAME) == ["sacrifice"]


def test_does_not_tag_sacrifice_for_an_ordinary_trade():
    # Same shape, but the solver's queen move doesn't hang anything — no
    # capture follows, so material never drops.
    fen = "4k3/7p/5n2/8/8/8/3Q4/4K3 b - - 0 1"
    solution = ["h7h6", "d2d4", "f6e4", "e1d1"]

    assert "sacrifice" not in tag_puzzle(fen, solution, endgame_material_threshold=NO_ENDGAME)


def test_tags_mate_when_the_solution_ends_in_checkmate():
    fen = "7k/1p3ppp/8/8/8/8/R7/4K3 b - - 0 1"
    solution = ["b7b6", "a2a8"]  # Ra8# — back-rank mate

    assert tag_puzzle(fen, solution, endgame_material_threshold=NO_ENDGAME) == ["mate"]


def test_tags_endgame_when_total_material_is_at_or_below_the_threshold():
    # Bare king-and-rook-vs-king — 5 points of material total, comfortably
    # under a real endgame_material_threshold like 20.
    fen = "8/8/8/8/4k3/8/4K3/R7 b - - 0 1"
    solution = ["e4d4", "a1a4"]

    assert tag_puzzle(fen, solution, endgame_material_threshold=20) == ["endgame"]


def test_does_not_tag_endgame_above_the_threshold():
    fen = "8/8/8/8/4k3/8/4K3/R7 b - - 0 1"
    solution = ["e4d4", "a1a4"]

    assert tag_puzzle(fen, solution, endgame_material_threshold=NO_ENDGAME) == []


def test_returns_no_tags_for_a_quiet_position_with_nothing_tactical_happening():
    # A perfectly ordinary opening sequence — no fork, no hanging piece, no
    # pin, no discovered check, no sacrifice, no mate, plenty of material.
    solution = ["e2e4", "e7e5", "g1f3", "b8c6"]

    assert tag_puzzle(chess.STARTING_FEN, solution, endgame_material_threshold=NO_ENDGAME) == []
