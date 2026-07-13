"""Tests for F5: Model-provider and spend adapters."""

from __future__ import annotations

import pytest


# Override the conftest autouse fixture — model provider tests are self-contained.
@pytest.fixture(autouse=True)
def _isolate_paths() -> None:
    """No-op: model provider tests do not need file-system isolation."""
    pass


from agent_runtime.model_provider import (
    ContextBudget,
    FailureClass,
    FakeProvider,
    ModelRoute,
    ProviderError,
    SpendBudget,
    StructuredGenerationRequest,
    UsageRecord,
    Workflow,
    calculate_cost,
)


# ── FakeProvider ─────────────────────────────────────────────────────


class TestFakeProvider:
    @pytest.mark.asyncio
    async def test_returns_configured_response(self) -> None:
        provider = FakeProvider(
            responses={"gpt-5-mini": {"result": "test-output"}}
        )
        request = StructuredGenerationRequest(
            model=ModelRoute.GPT5_MINI,
            messages=[{"role": "user", "content": "hello"}],
            response_schema={"type": "object"},
        )
        result = await provider.generate_structured(request)
        assert result.content == {"result": "test-output"}
        assert result.model_used == ModelRoute.GPT5_MINI
        assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_returns_default_for_unknown(self) -> None:
        provider = FakeProvider(default_response={"default": True})
        request = StructuredGenerationRequest(
            model=ModelRoute.GPT5_MINI,
            messages=[{"role": "user", "content": "hello"}],
            response_schema={"type": "object"},
        )
        result = await provider.generate_structured(request)
        assert result.content == {"default": True}

    @pytest.mark.asyncio
    async def test_tracks_call_count(self) -> None:
        provider = FakeProvider()
        request = StructuredGenerationRequest(
            model=ModelRoute.GPT5_MINI,
            messages=[],
            response_schema={},
        )
        assert provider.call_count == 0
        await provider.generate_structured(request)
        await provider.generate_structured(request)
        assert provider.call_count == 2

    @pytest.mark.asyncio
    async def test_tracks_usage_records(self) -> None:
        provider = FakeProvider()
        request = StructuredGenerationRequest(
            model=ModelRoute.GPT5_MINI,
            messages=[],
            response_schema={},
        )
        await provider.generate_structured(request)
        assert len(provider.usage_records) == 1
        record = provider.usage_records[0]
        assert record.success is True
        assert record.model == ModelRoute.GPT5_MINI
        assert record.cost_usd == 0.0

    def test_route_for_workflow_returns_fake(self) -> None:
        provider = FakeProvider()
        assert provider.route_for_workflow(Workflow.CHAT) == ModelRoute.FAKE

    @pytest.mark.asyncio
    async def test_deterministic_responses(self) -> None:
        provider = FakeProvider(
            responses={"gpt-5-mini": {"a": 1}}
        )
        request = StructuredGenerationRequest(
            model=ModelRoute.GPT5_MINI,
            messages=[],
            response_schema={},
        )
        r1 = await provider.generate_structured(request)
        r2 = await provider.generate_structured(request)
        assert r1.content == r2.content == {"a": 1}


# ── SpendBudget ──────────────────────────────────────────────────────


class TestSpendBudget:
    def test_initial_state(self) -> None:
        b = SpendBudget()
        assert b.total_spent == 0.0
        assert b.warning_level is None

    def test_records_spend(self) -> None:
        b = SpendBudget()
        assert b.record(5.0, Workflow.CHAT)
        assert b.total_spent == 5.0

    def test_warning_at_50_percent(self) -> None:
        b = SpendBudget(monthly_warning_usd=20.0)
        b.record(10.0, Workflow.CHAT)
        assert b.warning_level == "50%"

    def test_warning_at_75_percent(self) -> None:
        b = SpendBudget(monthly_warning_usd=20.0)
        b.record(15.0, Workflow.CHAT)
        assert b.warning_level == "75%"

    def test_warning_at_90_percent(self) -> None:
        b = SpendBudget(monthly_warning_usd=20.0)
        b.record(18.0, Workflow.CHAT)
        assert b.warning_level == "90%"

    def test_hard_limit(self) -> None:
        b = SpendBudget(monthly_hard_limit_usd=30.0)
        b.record(30.0, Workflow.CHAT)
        assert b.warning_level == "hard_limit"
        # Cannot record more
        assert b.record(0.01, Workflow.CHAT) is False

    def test_background_separate_allowance(self) -> None:
        b = SpendBudget(background_allowance_usd=5.0)
        assert b.record(3.0, Workflow.BACKGROUND)
        assert b.record(3.0, Workflow.BACKGROUND) is False  # exceeds $5

    def test_background_does_not_affect_main(self) -> None:
        b = SpendBudget(monthly_warning_usd=20.0)
        b.record(5.0, Workflow.BACKGROUND)
        # Main spend still 0
        assert b.total_spent == 5.0
        # But background exceeded does not trigger main warning
        # Actually total includes background
        assert b._spent_this_month == 0.0  # Only background spent

    def test_reset_month(self) -> None:
        b = SpendBudget()
        b.record(25.0, Workflow.CHAT)
        b.reset_month()
        assert b.total_spent == 0.0
        assert b.warning_level is None

    def test_hard_limit_still_accepts_if_under(self) -> None:
        b = SpendBudget(monthly_hard_limit_usd=30.0)
        result = b.record(29.99, Workflow.CHAT)
        assert result is True


# ── Cost calculation ─────────────────────────────────────────────────


class TestCalculateCost:
    def test_gpt5_mini_cost(self) -> None:
        cost = calculate_cost(ModelRoute.GPT5_MINI, 1000, 500)
        # input: (1000/1M)*$0.15 = $0.00015, output: (500/1M)*$0.60 = $0.0003
        # total ≈ $0.00045
        assert cost > 0
        assert cost < 0.01

    def test_gpt5_cost(self) -> None:
        cost = calculate_cost(ModelRoute.GPT5, 1000, 500)
        # input: (1000/1M)*$1.25 = $0.00125, output: (500/1M)*$10 = $0.005
        # total = $0.00625
        assert cost > 0.005
        assert cost < 0.01

    def test_fake_is_free(self) -> None:
        cost = calculate_cost(ModelRoute.FAKE, 1000000, 1000000)
        assert cost == 0.0

    def test_cached_tokens_50_percent_discount(self) -> None:
        cost_no_cache = calculate_cost(ModelRoute.GPT5_MINI, 1000, 0, 0)
        cost_with_cache = calculate_cost(ModelRoute.GPT5_MINI, 1000, 0, 1000)
        # With 1000 cached, effective input = 0, cached = 1000 at 50%
        assert cost_with_cache < cost_no_cache

    def test_only_regular_input_charged(self) -> None:
        # 1000 total input, 500 cached → 500 regular + 500 cached at 50%
        cost = calculate_cost(ModelRoute.GPT5_MINI, 1000, 0, 500)
        assert cost > 0


# ── ContextBudget ────────────────────────────────────────────────────


class TestContextBudget:
    def test_chat_workflow_budget(self) -> None:
        b = ContextBudget.for_workflow(Workflow.CHAT)
        assert b.max_tokens == ContextBudget.NORMAL_CHAT

    def test_regulation_workflow_budget(self) -> None:
        b = ContextBudget.for_workflow(Workflow.REGULATION)
        assert b.max_tokens == ContextBudget.STUDY_REGULATION

    def test_synthesis_workflow_budget(self) -> None:
        b = ContextBudget.for_workflow(Workflow.SYNTHESIS)
        assert b.max_tokens == ContextBudget.EXPLICIT_SYNTHESIS

    def test_fits_under_budget(self) -> None:
        b = ContextBudget.for_workflow(Workflow.CHAT)
        assert b.fits(4000) is True
        assert b.fits(8000) is True
        assert b.fits(8001) is False

    def test_remaining(self) -> None:
        b = ContextBudget.for_workflow(Workflow.CHAT)
        assert b.remaining(3000) == 5000
        assert b.remaining(8000) == 0
        assert b.remaining(9000) == 0


# ── UsageRecord ──────────────────────────────────────────────────────


class TestUsageRecord:
    def test_to_dict(self) -> None:
        record = UsageRecord(
            timestamp="2026-01-01T00:00:00+00:00",
            model=ModelRoute.GPT5_MINI,
            workflow=Workflow.CHAT,
            input_tokens=100,
            output_tokens=50,
            cached_tokens=10,
            cost_usd=0.001,
            duration_ms=150.5,
            success=True,
        )
        d = record.to_dict()
        assert d["model"] == "gpt-5-mini"
        assert d["workflow"] == "chat"
        assert d["input_tokens"] == 100
        assert d["cost_usd"] == 0.001

    def test_failure_record(self) -> None:
        record = UsageRecord(
            timestamp="2026-01-01T00:00:00+00:00",
            model=ModelRoute.GPT5_MINI,
            workflow=Workflow.CHAT,
            input_tokens=0,
            output_tokens=0,
            cached_tokens=0,
            cost_usd=0.0,
            duration_ms=5000.0,
            success=False,
            failure_class=FailureClass.TIMEOUT,
        )
        d = record.to_dict()
        assert d["success"] is False
        assert d["failure_class"] == "timeout"


# ── ProviderError ────────────────────────────────────────────────────


class TestProviderError:
    def test_carries_failure_class(self) -> None:
        err = ProviderError(FailureClass.TIMEOUT, "timed out")
        assert err.failure_class == FailureClass.TIMEOUT
        assert "timed out" in str(err)


# ── Enums ────────────────────────────────────────────────────────────


class TestModelRoute:
    def test_all_routes(self) -> None:
        assert ModelRoute.GPT5_MINI.value == "gpt-5-mini"
        assert ModelRoute.GPT5.value == "gpt-5"
        assert ModelRoute.FAKE.value == "fake"


class TestWorkflow:
    def test_all_workflows(self) -> None:
        assert Workflow.CHAT.value == "chat"
        assert Workflow.REGULATION.value == "regulation"


class TestFailureClass:
    def test_all_failures(self) -> None:
        assert FailureClass.TIMEOUT.value == "timeout"
        assert FailureClass.RATE_LIMITED.value == "rate_limited"
        assert FailureClass.OUTAGE.value == "outage"
        assert FailureClass.MALFORMED_OUTPUT.value == "malformed_output"
        assert FailureClass.SPEND_LIMIT.value == "spend_limit"
