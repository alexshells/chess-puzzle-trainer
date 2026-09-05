from ml.build_training_dataset import reservoir_sample


def test_reservoir_sample_returns_exactly_sample_size_from_a_longer_stream():
    rows = [{"id": i} for i in range(1000)]

    sample = reservoir_sample(iter(rows), sample_size=50, seed=42)

    assert len(sample) == 50
    # Every sampled row really came from the stream, not fabricated.
    assert all(row["id"] in range(1000) for row in sample)


def test_reservoir_sample_returns_everything_when_stream_is_shorter_than_sample_size():
    rows = [{"id": i} for i in range(5)]

    sample = reservoir_sample(iter(rows), sample_size=50, seed=42)

    assert len(sample) == 5


def test_reservoir_sample_is_deterministic_given_a_seed():
    rows = [{"id": i} for i in range(1000)]

    first = reservoir_sample(iter(rows), sample_size=20, seed=7)
    second = reservoir_sample(iter(rows), sample_size=20, seed=7)

    assert first == second
