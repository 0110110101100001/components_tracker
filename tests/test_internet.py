import socket

import internet


def test_probe_is_none_when_nothing_answers(monkeypatch):
    # A port on this PC that nothing listens on refuses the connection at once.
    with socket.socket() as unused:
        unused.bind(("127.0.0.1", 0))
        port = unused.getsockname()[1]
    monkeypatch.setattr(internet, "PROBES", (("127.0.0.1", port),))
    assert internet.probe() is None


def test_probe_times_a_listening_port(monkeypatch):
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        monkeypatch.setattr(internet, "PROBES", (("127.0.0.1", 1), server.getsockname()))
        assert 0 <= internet.probe() < internet.PROBE_TIMEOUT * 1000


def test_state_before_any_check():
    assert internet.Internet(5, 30).state() == {
        "online": None, "latency": None, "speed": None, "stalled": False}


def run_test_returning(monkeypatch, net, result):
    def fake_speed_test():
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(internet, "speed_test", fake_speed_test)
    return net.run_test()


def test_zero_download_is_stalled_and_retried_soon(monkeypatch):
    net = internet.Internet(5, 30)
    assert run_test_returning(monkeypatch, net, (0.0, 0.0)) == internet.RETRY_SECONDS
    assert net.stalled and net.speed is None
    assert run_test_returning(monkeypatch, net, (95e6, 8e6)) == 30 * 60
    assert not net.stalled and net.speed == (95e6, 8e6)


def test_broken_connection_is_stalled_server_refusal_is_not(monkeypatch):
    net = internet.Internet(5, 30)
    assert run_test_returning(monkeypatch, net, TimeoutError()) == internet.RETRY_SECONDS
    assert net.stalled
    net.stalled = False
    refused = internet.http.client.HTTPException("/__down answered 403")
    assert run_test_returning(monkeypatch, net, refused) == 30 * 60
    assert not net.stalled
