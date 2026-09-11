from ml.puzzle_features import build_core_feature_matrix, core_features


class FakeExample:
    def __init__(
        self,
        setup_swing_cp,
        forced,
        refutation_gap_cp,
        puzzle_position_eval_cp,
        has_decisive_payoff,
        decisive_material_gain,
        num_checking_moves,
        num_hanging_pieces,
        material_imbalance,
        num_pinned_pieces,
    ):
        self.setup_swing_cp = setup_swing_cp
        self.forced = forced
        self.refutation_gap_cp = refutation_gap_cp
        self.puzzle_position_eval_cp = puzzle_position_eval_cp
        self.has_decisive_payoff = has_decisive_payoff
        self.decisive_material_gain = decisive_material_gain
        self.num_checking_moves = num_checking_moves
        self.num_hanging_pieces = num_hanging_pieces
        self.material_imbalance = material_imbalance
        self.num_pinned_pieces = num_pinned_pieces


def test_core_features_imputes_missing_gap_and_flags_it():
    with_second_line = core_features(300, True, 150, 20, True, 3, 2, 1, 4, 1)
    assert with_second_line == [300.0, 1.0, 1.0, 150.0, 20.0, 1.0, 3.0, 2.0, 1.0, 4.0, 1.0]

    # No second line at all — gap imputed to 0, flag set to 0, not 1.
    without_second_line = core_features(50, False, None, -400, False, 0, 0, 0, 0, 0)
    assert without_second_line == [50.0, 0.0, 0.0, 0.0, -400.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_build_core_feature_matrix_stacks_examples_in_order():
    examples = [
        FakeExample(300, True, 150, 20, True, 3, 2, 1, 4, 1),
        FakeExample(50, False, None, -400, False, 0, 0, 0, 0, 0),
    ]

    X = build_core_feature_matrix(examples)

    assert X.shape == (2, 11)
    assert list(X[0]) == [300.0, 1.0, 1.0, 150.0, 20.0, 1.0, 3.0, 2.0, 1.0, 4.0, 1.0]
    assert list(X[1]) == [50.0, 0.0, 0.0, 0.0, -400.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
