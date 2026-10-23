import pytest

from app.services.gemini_key_pool import GeminiAllKeysExhaustedError, GeminiKeyPool, KeyStatus


class FakeAPIError(Exception):
    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__(f"fake gemini error code={code}")


def make_pool(
    keys: list[str] = None, cooldown_seconds: int = 60, server_error_cooldown_seconds: int = 15
) -> GeminiKeyPool:
    keys = keys or ["key-0", "key-1", "key-2"]
    # Fake client is just the key string itself — enough to identify which key served a call.
    return GeminiKeyPool(
        keys=keys,
        cooldown_seconds=cooldown_seconds,
        server_error_cooldown_seconds=server_error_cooldown_seconds,
        client_factory=lambda api_key: api_key,
    )


async def test_round_robin_distributes_across_keys():
    pool = make_pool()

    async def op(client: str) -> str:
        return client

    used = [await pool.execute(op) for _ in range(4)]

    # 3 keys, round robin wraps: 0, 1, 2, 0
    assert used == ["key-0", "key-1", "key-2", "key-0"]


async def test_failover_on_429_cools_down_key_and_retries_next():
    pool = make_pool()

    async def op(client: str) -> str:
        if client == "key-0":
            raise FakeAPIError(429)
        return client

    result = await pool.execute(op)

    assert result == "key-1"  # key-0 failed, pool moved on without the caller seeing it

    health = await pool.health()
    assert health[0].status == KeyStatus.cooling
    assert health[0].cooldown_remaining_seconds > 0
    assert health[1].status == KeyStatus.healthy


async def test_401_disables_key_permanently():
    pool = make_pool(cooldown_seconds=0)  # cooldown=0 so we can prove disabled != recovered

    async def op(client: str) -> str:
        if client == "key-0":
            raise FakeAPIError(401)
        return client

    await pool.execute(op)

    health = await pool.health()
    assert health[0].status == KeyStatus.disabled

    # Even on a later call that would start back at key-0, it must stay skipped.
    async def op_identity(client: str) -> str:
        return client

    result = await pool.execute(op_identity)
    assert result != "key-0"


async def test_all_keys_exhausted_raises_friendly_error_type():
    pool = make_pool(keys=["key-0", "key-1"])

    async def always_rate_limited(client: str) -> str:
        raise FakeAPIError(429)

    with pytest.raises(GeminiAllKeysExhaustedError):
        await pool.execute(always_rate_limited)

    health = await pool.health()
    assert all(entry.status == KeyStatus.cooling for entry in health)


async def test_non_quota_error_propagates_without_consuming_pool_state():
    pool = make_pool()

    async def op(client: str) -> str:
        raise RuntimeError("something unrelated broke")

    with pytest.raises(RuntimeError):
        await pool.execute(op)

    health = await pool.health()
    assert all(entry.status == KeyStatus.healthy for entry in health)


async def test_cooldown_on_one_model_does_not_affect_another_model():
    pool = make_pool(keys=["key-0", "key-1"])

    async def rate_limited_on_primary_only(client: str) -> str:
        raise FakeAPIError(429)

    with pytest.raises(GeminiAllKeysExhaustedError):
        await pool.execute(rate_limited_on_primary_only, model="primary")

    primary_health = await pool.health("primary")
    assert all(entry.status == KeyStatus.cooling for entry in primary_health)

    # Same keys, different model bucket — nothing cooling here yet.
    fallback_health = await pool.health("fallback")
    assert all(entry.status == KeyStatus.healthy for entry in fallback_health)

    async def op(client: str) -> str:
        return client

    result = await pool.execute(op, model="fallback")
    assert result in ("key-0", "key-1")


async def test_execute_with_fallback_retries_every_key_on_fallback_model():
    pool = make_pool(keys=["key-0", "key-1"])
    calls: list[tuple[str, str]] = []

    async def op(client: str, model: str) -> str:
        calls.append((client, model))
        if model == "primary":
            raise FakeAPIError(429)
        return f"{client}-via-{model}"

    result = await pool.execute_with_fallback(op, primary_model="primary", fallback_model="fallback")

    assert result.endswith("-via-fallback")
    # Both keys should have been tried on the primary model before falling back.
    assert {c for c, m in calls if m == "primary"} == {"key-0", "key-1"}

    primary_health = await pool.health("primary")
    assert all(entry.status == KeyStatus.cooling for entry in primary_health)


async def test_execute_with_fallback_raises_when_both_models_exhausted():
    pool = make_pool(keys=["key-0", "key-1"])

    async def always_rate_limited(client: str, model: str) -> str:
        raise FakeAPIError(429)

    with pytest.raises(GeminiAllKeysExhaustedError):
        await pool.execute_with_fallback(always_rate_limited, primary_model="primary", fallback_model="fallback")


async def test_failover_on_503_cools_down_key_and_retries_next():
    pool = make_pool()

    async def op(client: str) -> str:
        if client == "key-0":
            raise FakeAPIError(503)
        return client

    result = await pool.execute(op)

    assert result == "key-1"
    health = await pool.health()
    assert health[0].status == KeyStatus.cooling
    assert health[0].cooldown_remaining_seconds > 0


async def test_failover_on_504_cools_down_key_and_retries_next():
    pool = make_pool()

    async def op(client: str) -> str:
        if client == "key-0":
            raise FakeAPIError(504)
        return client

    result = await pool.execute(op)

    assert result == "key-1"
    health = await pool.health()
    assert health[0].status == KeyStatus.cooling


async def test_failover_on_timeout_cools_down_key_and_retries_next():
    pool = make_pool()

    async def op(client: str) -> str:
        if client == "key-0":
            raise TimeoutError("call timed out")
        return client

    result = await pool.execute(op)

    assert result == "key-1"
    health = await pool.health()
    assert health[0].status == KeyStatus.cooling
    assert health[0].cooldown_remaining_seconds > 0


async def test_server_error_cooldown_is_independent_of_quota_cooldown():
    # Quota cooldown set very long, server-error cooldown set very short —
    # proves a 503 uses the short one, not the 429 one.
    pool = make_pool(cooldown_seconds=600, server_error_cooldown_seconds=1)

    async def op(client: str) -> str:
        if client == "key-0":
            raise FakeAPIError(503)
        return client

    await pool.execute(op)

    health = await pool.health()
    assert health[0].cooldown_remaining_seconds <= 1


async def test_all_keys_exhausted_on_5xx_raises_friendly_error():
    pool = make_pool(keys=["key-0", "key-1"])

    async def always_unavailable(client: str) -> str:
        raise FakeAPIError(503)

    with pytest.raises(GeminiAllKeysExhaustedError):
        await pool.execute(always_unavailable)

    health = await pool.health()
    assert all(entry.status == KeyStatus.cooling for entry in health)


async def test_all_keys_exhausted_on_timeout_raises_friendly_error():
    pool = make_pool(keys=["key-0", "key-1"])

    async def always_times_out(client: str) -> str:
        raise TimeoutError("call timed out")

    with pytest.raises(GeminiAllKeysExhaustedError):
        await pool.execute(always_times_out)

    health = await pool.health()
    assert all(entry.status == KeyStatus.cooling for entry in health)


async def test_400_bad_request_still_propagates_immediately():
    # A real 4xx (bug in our own request) fails identically on every key —
    # must NOT be treated as transient, or we'd burn the whole pool retrying
    # something that can never succeed.
    pool = make_pool()

    async def op(client: str) -> str:
        raise FakeAPIError(400)

    with pytest.raises(FakeAPIError):
        await pool.execute(op)

    health = await pool.health()
    assert all(entry.status == KeyStatus.healthy for entry in health)
