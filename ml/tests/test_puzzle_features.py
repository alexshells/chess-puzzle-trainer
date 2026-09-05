from ml.puzzle_features import build_core_feature_matrix, core_features


class FakeExample:
    def __init__(self, setup_swing_cp, forced, refutation_gap_cp):
        self.setup_swing_cp = setup_swing_cp
        self.forced = forced
        self.refutation_gap_cp = refutation_gap_cp


def test_core_features_imputes_missing_gap_and_flags_it():
    with_second_line = core_features(300, True, 150)
    assert with_second_line == [300.0, 1.0, 1.0, 150.0]

    # No second line at all — gap imputed to 0, flag set to 0, not 1.
    without_second_line = core_features(50, False, None)
    assert without_second_line == [50.0, 0.0, 0.0, 0.0]


def test_build_core_feature_matrix_stacks_examples_in_order():
    examples = [
        FakeExample(300, True, 150),
        FakeExample(50, False, None),
    ]

    X = build_core_feature_matrix(examples)

    assert X.shape == (2, 4)
    assert list(X[0]) == [300.0, 1.0, 1.0, 150.0]
    assert list(X[1]) == [50.0, 0.0, 0.0, 0.0]
