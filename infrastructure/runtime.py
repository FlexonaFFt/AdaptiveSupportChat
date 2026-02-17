from typing import Optional

from application.flow_engine import FlowEngine
from infrastructure.llm_api_client import LLMApiClient
from infrastructure.rag.retriever import KnowledgeRetriever

_flow_engine: Optional[FlowEngine] = None
_llm_client: Optional[LLMApiClient] = None
_knowledge_retriever: Optional[KnowledgeRetriever] = None


def set_flow_engine(engine: FlowEngine) -> None:
    global _flow_engine
    _flow_engine = engine


def get_flow_engine() -> FlowEngine:
    if _flow_engine is None:
        raise RuntimeError("Flow engine is not initialized.")
    return _flow_engine


def set_llm_client(client: LLMApiClient) -> None:
    global _llm_client
    _llm_client = client


def get_llm_client() -> LLMApiClient:
    if _llm_client is None:
        raise RuntimeError("LLM client is not initialized.")
    return _llm_client


def set_knowledge_retriever(retriever: KnowledgeRetriever) -> None:
    global _knowledge_retriever
    _knowledge_retriever = retriever


def get_knowledge_retriever() -> KnowledgeRetriever:
    if _knowledge_retriever is None:
        raise RuntimeError("Knowledge retriever is not initialized.")
    return _knowledge_retriever
