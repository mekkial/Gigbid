"""Observability (R8/E3): OpenTelemetry -> Arize Phoenix. One `gigbid.trace_id` flows UI request -> API span -> graph node spans
-> LLM spans (tokens) -> MCP tool spans -> audit log. Off unless PHOENIX_COLLECTOR_ENDPOINT is set; tracing calls are no-ops otherwise."""
from __future__ import annotations

import contextlib
import os

from opentelemetry import trace

_ENABLED = False


def setup(project: str = "gigbid") -> bool:
    global _ENABLED
    ep = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT")
    if not ep or _ENABLED:
        return _ENABLED
    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from openinference.instrumentation.openai import OpenAIInstrumentor
        from phoenix.otel import register

        tp = register(project_name=project, endpoint=ep.rstrip("/") + "/v1/traces", auto_instrument=False, batch=True)
        OpenAIInstrumentor().instrument(tracer_provider=tp)
        LangChainInstrumentor().instrument(tracer_provider=tp)
        _ENABLED = True
    except Exception as e:  # noqa: BLE001 - tracing must never break the product
        print("tracing disabled:", e)
    return _ENABLED


tracer = trace.get_tracer("gigbid")


@contextlib.contextmanager
def span(name: str, **attrs):
    """Span with gigbid.* attributes (trace id, user hash, node, tokens, cost). No-op tracer when tracing is off."""
    with tracer.start_as_current_span(name) as s:
        for k, v in attrs.items():
            if v is not None:
                s.set_attribute(k if "." in k else f"gigbid.{k}", v)
        yield s
