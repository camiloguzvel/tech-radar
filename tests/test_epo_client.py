import httpx
import pytest

from radar.connectors import epo_ops as ops

OK = {"ops:world-patent-data": {"ops:biblio-search": {"@total-result-count": "7"}}}


def make_client(responses: list, slept: list) -> ops.OpsClient:
    """`responses`: lista de httpx.Response o excepciones, en orden, para /rest-services."""
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/accesstoken"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": "1199"})
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return ops.OpsClient(
        "k", "s", transport=httpx.MockTransport(handler), sleep=lambda s: slept.append(s)
    )


def test_retry_after_is_milliseconds():
    assert ops.retry_after_seconds("900000") == 900.0
    assert ops.retry_after_seconds(None) is None
    assert ops.retry_after_seconds("abc") is None


def test_hourly_403_waits_retry_after_then_succeeds():
    slept: list = []
    c = make_client(
        [
            httpx.Response(
                403, headers={"retry-after": "5000", "x-rejection-reason": "IndividualQuotaPerHour"}
            ),
            httpx.Response(200, json=OK),
        ],
        slept,
    )
    assert c.count("q") == 7
    assert 6.0 in slept  # 5000 ms + 1 s de margen


def test_hourly_403_beyond_cap_fails_with_error_not_hang():
    slept: list = []
    c = make_client([httpx.Response(403, headers={"retry-after": "3600000"})], slept)
    with pytest.raises(ops.OpsError, match="excede el tope"):
        c.count("q")
    assert not any(s > ops.MAX_QUOTA_WAIT_S for s in slept)


def test_network_error_is_retried():
    slept: list = []
    c = make_client(
        [httpx.ConnectError("SSL: UNEXPECTED_EOF_WHILE_READING"), httpx.Response(200, json=OK)],
        slept,
    )
    assert c.count("q") == 7
    assert c.log[0]["status"] == "transport"


def test_weekly_rejection_raises_quota_exceeded():
    c = make_client(
        [httpx.Response(403, headers={"x-rejection-reason": "RegisteredQuotaPerWeek"})], []
    )
    with pytest.raises(ops.QuotaExceeded):
        c.count("q")


def test_pauses_before_hourly_quota_is_hit():
    slept: list = []
    c = make_client(
        [
            httpx.Response(
                200, json=OK, headers={"x-individualquotaperhour-used": str(400 * 1024**2)}
            ),
            httpx.Response(200, json=OK),
        ],
        slept,
    )
    c.count("q")
    assert ops.HOURLY_PAUSE_S not in slept
    c.count("q")  # la segunda llamada ve el contador alto y pausa antes
    assert ops.HOURLY_PAUSE_S in slept
