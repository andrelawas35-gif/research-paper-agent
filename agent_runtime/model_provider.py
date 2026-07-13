"""Model-provider and spend adapters — F5 from implementation-plan-regulation-pkm.md.

ADR 0122: GPT Models Use Policy-Gated Routing.
ADR 0124: Model Spend Is Bounded and Attributed.
ADR 0125: Context Budgets Are Task-Specific.

Provides:
- Provider interface for structured generation
- Timeout, usage accounting, route selection, failure classification
- GPT-5 mini as default; GPT-5 for policy-gated workflows
- Fake provider for deterministic tests
- Spend tracking with monthly budget enforcement
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


# ── Types ────────────────────────────────────────────────────────────


class ModelRoute(str, Enum):
    """Available model routes. Kept out of domain modules."""
    GPT5_MINI = "gpt-5-mini"
    GPT5 = "gpt-5"
    FAKE = "fake"


class Workflow(str, Enum):
    """Workflow categories for spend attribution."""
    CHAT = "chat"
    RETRIEVAL = "retrieval"
    STUDY = "study"
    REGULATION = "regulation"
    VALUES = "values"
    BACKGROUND = "background"
    SYNTHESIS = "synthesis"


class FailureClass(str, Enum):
    """Typed failure reasons for model invocations."""
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    OUTAGE = "outage"
    MALFORMED_OUTPUT = "malformed_output"
    SPEND_LIMIT = "spend_limit"
    INVALID_SCHEMA = "invalid_schema"
    UNKNOWN = "unknown"


# ── Usage record ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class UsageRecord:
    """Immutable record of a single model invocation."""
    timestamp: str
    model: ModelRoute
    workflow: Workflow
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    duration_ms: float
    success: bool
    failure_class: Optional[FailureClass] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "model": self.model.value,
            "workflow": self.workflow.value,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_tokens": self.cached_tokens,
            "cost_usd": self.cost_usd,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "failure_class": self.failure_class.value if self.failure_class else None,
        }


# ── Spend budget ─────────────────────────────────────────────────────


@dataclass
class SpendBudget:
    """Monthly spend budget with hard and warning limits.

    Per ADR 0124: $20 warning, $30 hard limit, $5 background allowance.
    """

    monthly_warning_usd: float = 20.0
    monthly_hard_limit_usd: float = 30.0
    background_allowance_usd: float = 5.0

    _spent_this_month: float = field(default=0.0, init=False)
    _background_spent: float = field(default=0.0, init=False)

    def record(self, cost_usd: float, workflow: Workflow) -> bool:
        """Record spend. Returns False if hard limit exceeded.

        Background spend is tracked separately.
        """
        if workflow == Workflow.BACKGROUND:
            self._background_spent += cost_usd
            if self._background_spent > self.background_allowance_usd:
                return False
        else:
            self._spent_this_month += cost_usd

        total = self._spent_this_month + self._background_spent
        return total <= self.monthly_hard_limit_usd

    @property
    def total_spent(self) -> float:
        return self._spent_this_month + self._background_spent

    @property
    def warning_level(self) -> Optional[str]:
        """Return warning level: None, '50%', '75%', '90%', or 'hard_limit'."""
        ratio = self.total_spent / self.monthly_warning_usd
        if self.total_spent >= self.monthly_hard_limit_usd:
            return "hard_limit"
        if ratio >= 0.90:
            return "90%"
        if ratio >= 0.75:
            return "75%"
        if ratio >= 0.50:
            return "50%"
        return None

    def reset_month(self) -> None:
        self._spent_this_month = 0.0
        self._background_spent = 0.0


# ── Pricing ──────────────────────────────────────────────────────────


# Per-1M-token pricing (USD). Keep in config, not hardcoded in domain logic.
PRICING: dict[ModelRoute, tuple[float, float]] = {
    ModelRoute.GPT5_MINI: (0.15, 0.60),   # input, output per 1M tokens
    ModelRoute.GPT5: (1.25, 10.00),
    ModelRoute.FAKE: (0.0, 0.0),
}


def calculate_cost(
    model: ModelRoute,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Calculate cost in USD for a model invocation."""
    input_price, output_price = PRICING.get(model, (0.0, 0.0))
    # Cached input tokens at 50% discount
    cached_cost = (cached_tokens / 1_000_000) * (input_price * 0.5)
    regular_input = max(0, input_tokens - cached_tokens)
    input_cost = (regular_input / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    return round(cached_cost + input_cost + output_cost, 6)


# ── Provider interface ───────────────────────────────────────────────


class ProviderError(Exception):
    """Base error for provider failures."""
    def __init__(self, failure_class: FailureClass, message: str):
        super().__init__(message)
        self.failure_class = failure_class


@dataclass
class StructuredGenerationRequest:
    """Request for structured model output."""
    model: ModelRoute
    messages: List[dict[str, Any]]
    response_schema: dict[str, Any]  # JSON Schema for output
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout_seconds: float = 30.0


@dataclass
class StructuredGenerationResult:
    """Result of a structured model generation."""
    content: dict[str, Any]
    usage: UsageRecord
    model_used: ModelRoute
    finish_reason: str


class ModelProvider(ABC):
    """Abstract interface for model providers.

    Domain modules depend on this interface, not on specific model IDs
    or provider implementations.
    """

    @abstractmethod
    async def generate_structured(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResult:
        """Generate structured output from the model."""
        ...

    @abstractmethod
    def route_for_workflow(self, workflow: Workflow) -> ModelRoute:
        """Return the appropriate model route for a workflow."""
        ...


# ── Fake provider (deterministic, for tests) ─────────────────────────


@dataclass
class FakeProvider(ModelProvider):
    """Deterministic fake provider for testing.

    Returns pre-configured responses or empty outputs.
    """

    responses: Dict[str, dict[str, Any]] = field(default_factory=dict)
    default_response: dict[str, Any] = field(default_factory=dict)
    _call_count: int = field(default=0, init=False)
    _usage: List[UsageRecord] = field(default_factory=list, init=False)

    async def generate_structured(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResult:
        self._call_count += 1
        start = time.monotonic()

        # Check spend limit
        key = f"{request.model.value}:{self._call_count}"
        response_content = self.responses.get(
            key, self.responses.get(request.model.value, self.default_response)
        )

        duration = (time.monotonic() - start) * 1000
        usage = UsageRecord(
            timestamp=_now_iso(),
            model=request.model,
            workflow=Workflow.CHAT,
            input_tokens=100,
            output_tokens=50,
            cached_tokens=0,
            cost_usd=0.0,
            duration_ms=duration,
            success=True,
        )
        self._usage.append(usage)

        return StructuredGenerationResult(
            content=response_content,
            usage=usage,
            model_used=request.model,
            finish_reason="stop",
        )

    def route_for_workflow(self, workflow: Workflow) -> ModelRoute:
        return ModelRoute.FAKE

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def usage_records(self) -> List[UsageRecord]:
        return list(self._usage)


# ── OpenAI-compatible provider ───────────────────────────────────────


@dataclass
class OpenAIProvider(ModelProvider):
    """OpenAI-compatible provider (GPT-5 mini, GPT-5).

    Uses the openai Python client. Model IDs are config-driven,
    not hardcoded in domain modules.
    """

    api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    base_url: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL")
    )
    budget: SpendBudget = field(default_factory=SpendBudget)
    gpt5_mini_id: str = field(
        default_factory=lambda: os.getenv("OPENAI_GPT5_MINI_MODEL", "gpt-5-mini")
    )
    gpt5_id: str = field(
        default_factory=lambda: os.getenv("OPENAI_GPT5_MODEL", "gpt-5")
    )

    _client: Any = field(init=False, default=None)
    _usage: List[UsageRecord] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if not self.api_key:
            # Model access is optional in production. A missing credential is
            # represented as an unavailable provider so Regulation can use its
            # deterministic degradation path instead of failing startup.
            self._client = None
            return
        try:
            from openai import AsyncOpenAI
            kwargs: dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = AsyncOpenAI(**kwargs)
        except ImportError:
            self._client = None

    async def generate_structured(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResult:
        if self._client is None:
            raise ProviderError(
                FailureClass.OUTAGE,
                "OpenAI client not available (openai package not installed)"
            )

        # Spend check
        estimated_cost = calculate_cost(request.model, 2000, 500)
        if self.budget.warning_level == "hard_limit":
            raise ProviderError(
                FailureClass.SPEND_LIMIT,
                f"Monthly hard limit (${self.budget.monthly_hard_limit_usd}) reached"
            )

        model_id = self._resolve_model_id(request.model)
        start = time.monotonic()

        try:
            response = await self._client.chat.completions.create(
                model=model_id,
                messages=request.messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_response",
                        "schema": request.response_schema,
                        "strict": True,
                    },
                },
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                timeout=request.timeout_seconds,
            )
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            failure = self._classify_error(exc)
            usage = UsageRecord(
                timestamp=_now_iso(),
                model=request.model,
                workflow=Workflow.CHAT,
                input_tokens=0,
                output_tokens=0,
                cached_tokens=0,
                cost_usd=0.0,
                duration_ms=duration,
                success=False,
                failure_class=failure,
            )
            self._usage.append(usage)
            raise ProviderError(failure, str(exc)) from exc

        duration = (time.monotonic() - start) * 1000
        completion = response.choices[0]
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        cached_tokens = getattr(
            response.usage, "prompt_tokens_details", None
        )
        cached = cached_tokens.cached_tokens if cached_tokens else 0

        cost = calculate_cost(request.model, input_tokens, output_tokens, cached)
        self.budget.record(cost, Workflow.CHAT)

        usage = UsageRecord(
            timestamp=_now_iso(),
            model=request.model,
            workflow=Workflow.CHAT,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached,
            cost_usd=cost,
            duration_ms=duration,
            success=True,
        )
        self._usage.append(usage)

        # Parse JSON response
        import json
        try:
            content = json.loads(completion.message.content or "{}")
        except json.JSONDecodeError:
            failure = FailureClass.MALFORMED_OUTPUT
            usage_fail = UsageRecord(
                timestamp=_now_iso(),
                model=request.model,
                workflow=Workflow.CHAT,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached,
                cost_usd=cost,
                duration_ms=duration,
                success=False,
                failure_class=failure,
            )
            self._usage.append(usage_fail)
            raise ProviderError(failure, "Model returned invalid JSON")

        return StructuredGenerationResult(
            content=content,
            usage=usage,
            model_used=request.model,
            finish_reason=completion.finish_reason or "stop",
        )

    def route_for_workflow(self, workflow: Workflow) -> ModelRoute:
        """Route selection by workflow.

        GPT-5 mini is the default daily driver.
        GPT-5 is policy-gated for explicit deep analysis and high-impact
        workflows. Distress and conversation length are NOT escalation
        signals (ADR 0123).
        """
        # GPT-5 gated workflows
        gpt5_workflows = {
            Workflow.SYNTHESIS,
        }
        if workflow in gpt5_workflows:
            return ModelRoute.GPT5
        return ModelRoute.GPT5_MINI

    def _resolve_model_id(self, route: ModelRoute) -> str:
        if route == ModelRoute.GPT5_MINI:
            return self.gpt5_mini_id
        if route == ModelRoute.GPT5:
            return self.gpt5_id
        raise ProviderError(
            FailureClass.UNKNOWN,
            f"Unknown model route: {route}"
        )

    def _classify_error(self, exc: Exception) -> FailureClass:
        msg = str(exc).lower()
        if "timeout" in msg:
            return FailureClass.TIMEOUT
        if "rate limit" in msg or "429" in msg:
            return FailureClass.RATE_LIMITED
        if "connection" in msg or "unreachable" in msg:
            return FailureClass.OUTAGE
        return FailureClass.UNKNOWN

    @property
    def usage_records(self) -> List[UsageRecord]:
        return list(self._usage)


# ── Context budget ───────────────────────────────────────────────────


@dataclass
class ContextBudget:
    """Task-specific context budget (ADR 0125).

    Limits tokens sent to the model by task type.
    """

    max_tokens: int
    workflow: Workflow

    # Budget presets (in tokens)
    QUICK_CAPTURE = 4000
    NORMAL_CHAT = 8000
    STUDY_REGULATION = 16000
    EXPLICIT_SYNTHESIS = 32000

    @classmethod
    def for_workflow(cls, workflow: Workflow) -> ContextBudget:
        if workflow in (Workflow.CHAT, Workflow.BACKGROUND):
            return cls(max_tokens=cls.NORMAL_CHAT, workflow=workflow)
        if workflow in (Workflow.REGULATION, Workflow.STUDY, Workflow.VALUES):
            return cls(max_tokens=cls.STUDY_REGULATION, workflow=workflow)
        if workflow == Workflow.SYNTHESIS:
            return cls(max_tokens=cls.EXPLICIT_SYNTHESIS, workflow=workflow)
        return cls(max_tokens=cls.QUICK_CAPTURE, workflow=workflow)

    def fits(self, token_count: int) -> bool:
        return token_count <= self.max_tokens

    def remaining(self, used: int) -> int:
        return max(0, self.max_tokens - used)


# ── Helpers ──────────────────────────────────────────────────────────


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
