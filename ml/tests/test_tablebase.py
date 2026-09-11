import chess
import httpx
import pytest

from ml import tablebase

# White: Kc3, Ng5, Rh2. Black: Ke8, Qd7, Pa7. 6 pieces total — eligible.
_ELIGIBLE_FEN = "4k3/p2q4/8/6N1/8/2K5/7R/8 w - - 0 1"
# A full starting position — 32 pieces, nowhere close to eligible.
_INELIGIBLE_FEN = chess.STARTING_FEN


def _fake_response(body: dict) -> httpx.Response:
    # raise_for_status() requires a request to be attached even on success —
    # a real httpx.get() call always has one; our fake doesn't unless we set
    # it explicitly.
    return httpx.Response(200, json=body, request=httpx.Request("GET", tablebase._TABLEBASE_URL))


@pytest.fixture(autouse=True)
def _reset_throttle_state():
    """The self-throttle tracks its last-request time as a module global —
    reset it so one test's timing never leaks into the next."""
    tablebase._last_request_at = None
    yield
    tablebase._last_request_at = None


def test_is_tablebase_eligible_counts_all_pieces_on_board():
    assert tablebase.is_tablebase_eligible(chess.Board(_ELIGIBLE_FEN)) is True
    assert tablebase.is_tablebase_eligible(chess.Board(_INELIGIBLE_FEN)) is False


def test_probe_skips_the_network_entirely_when_ineligible(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("probe() should never call the network for an ineligible position")

    monkeypatch.setattr(tablebase.httpx, "get", _fail_if_called)

    assert tablebase.probe(chess.Board(_INELIGIBLE_FEN)) is None


def test_probe_reports_a_unique_winning_move(monkeypatch):
    # category "win" for the side to move, and the runner-up move leads to a
    # "loss" for the opponent (i.e. also winning for us) is what would make
    # it NOT unique — here the runner-up is merely a "draw", so only the top
    # move actually wins.
    body = {
        "category": "win",
        "moves": [
            {"uci": "g5f7", "category": "loss"},
            {"uci": "h2h8", "category": "draw"},
        ],
    }
    monkeypatch.setattr(tablebase.httpx, "get", lambda *a, **kw: _fake_response(body))

    verdict = tablebase.probe(chess.Board(_ELIGIBLE_FEN))

    assert verdict == tablebase.TablebaseVerdict(winning=True, only_winning_move=True)


def test_probe_reports_several_winning_moves_as_not_unique(monkeypatch):
    body = {
        "category": "win",
        "moves": [
            {"uci": "g5f7", "category": "loss"},
            {"uci": "h2h8", "category": "loss"},  # a second move that also wins
        ],
    }
    monkeypatch.setattr(tablebase.httpx, "get", lambda *a, **kw: _fake_response(body))

    verdict = tablebase.probe(chess.Board(_ELIGIBLE_FEN))

    assert verdict == tablebase.TablebaseVerdict(winning=True, only_winning_move=False)


def test_probe_reports_a_non_winning_position(monkeypatch):
    body = {"category": "draw", "moves": [{"uci": "g5f7", "category": "draw"}]}
    monkeypatch.setattr(tablebase.httpx, "get", lambda *a, **kw: _fake_response(body))

    verdict = tablebase.probe(chess.Board(_ELIGIBLE_FEN))

    assert verdict == tablebase.TablebaseVerdict(winning=False, only_winning_move=False)


def test_probe_returns_none_when_there_are_no_legal_moves(monkeypatch):
    body = {"category": "win", "moves": []}
    monkeypatch.setattr(tablebase.httpx, "get", lambda *a, **kw: _fake_response(body))

    assert tablebase.probe(chess.Board(_ELIGIBLE_FEN)) is None


def test_probe_returns_none_on_a_network_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(tablebase.httpx, "get", _raise)

    assert tablebase.probe(chess.Board(_ELIGIBLE_FEN)) is None


def test_probe_throttles_a_second_call_within_the_minimum_gap(monkeypatch):
    body = {"category": "win", "moves": [{"uci": "g5f7", "category": "loss"}]}
    monkeypatch.setattr(tablebase.httpx, "get", lambda *a, **kw: _fake_response(body))

    # Consumed in order: call 1's post-request timestamp (100.0), call 2's
    # pre-request elapsed-time check (100.1 -> 0.1s since the last request),
    # call 2's post-request timestamp (100.6, value itself unused below).
    fake_clock = iter([100.0, 100.1, 100.6])
    monkeypatch.setattr(tablebase.time, "monotonic", lambda: next(fake_clock))
    sleep_calls: list[float] = []
    monkeypatch.setattr(tablebase.time, "sleep", sleep_calls.append)

    tablebase.probe(chess.Board(_ELIGIBLE_FEN))
    tablebase.probe(chess.Board(_ELIGIBLE_FEN))

    # 0.55s minimum gap, only 0.1s elapsed since the first request -> should
    # have slept for roughly the remainder.
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == pytest.approx(0.45, abs=1e-9)
