"""Half-open probes must not retain a lease without a health verdict (S2)."""
import pytest

from web_search_plus_mcp.attempt_engine_v3 import AttemptContext, AttemptEngine
from web_search_plus_mcp.contract_v3 import AttemptOutcome, Capability, CircuitState, ErrorClass
from web_search_plus_mcp.credentials import _mark_secret_scope_error
from web_search_plus_mcp.http_client import ProviderRequestError
from wsp_sdk.errors import ProviderConfigError, ProviderContractFailure
from web_search_plus_mcp.state_store_v3 import SQLiteStateStore


def _probe(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    context = AttemptContext(
        provider="brave", capability=Capability.SEARCH,
        endpoint="https://example.test/search", credential_fingerprint="test-fingerprint",
        budget_scope="request-lease", budget_window="request", budget_limit_units=5,
        daily_budget_scope="daily", daily_budget_window="2026-10-14", daily_budget_limit_units=10,
    )
    store.record_failure(context.circuit_key, ErrorClass.RATE_LIMIT, now=100, retry_after_seconds=1)
    return store, context


def _assert_committed_and_probe_available(store, context):
    for scope, window in ((context.budget_scope, context.budget_window),
                          (context.daily_budget_scope, context.daily_budget_window)):
        budget = store.get_budget(scope, window)
        assert (budget.used_units, budget.reserved_units) == (1, 0)
    original = store.get_circuit(context.circuit_key, ErrorClass.RATE_LIMIT)
    assert original.failure_count == 1
    # Never erase the previous health evidence; just return its probe lease.
    assert original.state is CircuitState.HALF_OPEN
    calls = []
    result = AttemptEngine(store, max_attempts=1).execute(
        context, lambda: calls.append(1) or {"results": []}, now=lambda: 103,
    )
    assert calls == [1]
    assert result.receipt.outcome is AttemptOutcome.SUCCESS
    assert result.receipt.circuit_state_before is CircuitState.HALF_OPEN


@pytest.mark.parametrize("error, expected", [
    (ProviderRequestError("invalid", status_code=400), ErrorClass.INVALID_REQUEST),
    (ProviderRequestError("invalid", status_code=413), ErrorClass.INVALID_REQUEST),
    (ProviderRequestError("invalid", status_code=422), ErrorClass.INVALID_REQUEST),
    (RuntimeError("internal"), ErrorClass.INTERNAL),
    (ProviderContractFailure("contract"), ErrorClass.PROVIDER_CONTRACT),
    (ProviderConfigError("config"), ErrorClass.CONFIG),
])
def test_verdictless_failure_returns_half_open_lease(tmp_path, error, expected):
    store, context = _probe(tmp_path)
    def operation():
        raise error
    result = AttemptEngine(store).execute(context, operation, now=lambda: 102)
    assert result.receipt.outcome is AttemptOutcome.FAILED
    assert result.receipt.error is not None
    assert result.receipt.error.error_class is expected
    assert len(result.receipt.tries) == 1
    _assert_committed_and_probe_available(store, context)


def test_secret_scope_failure_returns_half_open_lease_and_reraises(tmp_path):
    store, context = _probe(tmp_path)
    error = RuntimeError("unscoped credential read")
    _mark_secret_scope_error(error)
    def operation():
        raise error
    with pytest.raises(RuntimeError) as caught:
        AttemptEngine(store).execute(context, operation, now=lambda: 102)
    assert caught.value is error
    assert store.get_circuit(context.circuit_key, ErrorClass.INTERNAL).failure_count == 0
    _assert_committed_and_probe_available(store, context)


@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit, BaseException])
def test_control_flow_exception_commits_releases_and_reraises(tmp_path, exception_type):
    store, context = _probe(tmp_path)
    error = exception_type("stop")
    def operation():
        raise error
    with pytest.raises(exception_type) as caught:
        AttemptEngine(store).execute(context, operation, now=lambda: 102)
    assert caught.value is error
    assert store.get_circuit(context.circuit_key, ErrorClass.INTERNAL).failure_count == 0
    _assert_committed_and_probe_available(store, context)


def test_keyboard_interrupt_during_retry_wait_returns_lease(tmp_path):
    store, context = _probe(tmp_path)
    def operation():
        raise ProviderRequestError("upstream", status_code=503)
    def sleep(_seconds):
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        AttemptEngine(store, sleep=sleep).execute(context, operation, now=lambda: 102)
    _assert_committed_and_probe_available(store, context)
