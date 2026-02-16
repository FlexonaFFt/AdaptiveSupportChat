from .flow.engine import FlowEngine
from typing import Optional

_flow_engine: Optional[FlowEngine] = None


def set_flow_engine(engine: FlowEngine) -> None:
    global _flow_engine
    _flow_engine = engine


def get_flow_engine() -> FlowEngine:
    if _flow_engine is None:
        raise RuntimeError("Flow engine is not initialized.")
    return _flow_engine
