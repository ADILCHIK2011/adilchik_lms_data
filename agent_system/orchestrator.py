"""LangGraph wiring for the 3-agent pipeline.

    ingest --(ok)--> attendance --> performance --> integration --> END
       \--(fatal)--------------------------------------------------> END

LangGraph is used here (over CrewAI) because this workflow is a deterministic
DAG with a strict data contract between steps (Agent 2 needs Agent 1's
flags; Agent 3 needs both), not a set of autonomous role-playing agents
negotiating a goal — LangGraph's explicit state machine + conditional edges
map directly onto that, and give us a free checkpoint of `PipelineState`
after every node for debugging/observability.

The only edge that can short-circuit the graph is a fatal ingestion error
(corrupt/unreadable archive, or literally no data). Everything else --
missing files, bad rows, absent contacts, unreachable cloud DB, unset
Telegram token -- is absorbed inside each agent and shows up as data on the
final state instead of stopping the run.
"""
from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from .attendance_agent import run_attendance_agent
from .ingestion import IngestionFatalError, load_data_bundle
from .integration_agent import run_integration_agent
from .models import PipelineState
from .performance_agent import run_performance_agent

logger = logging.getLogger("agent_system.orchestrator")


def node_ingest(state: PipelineState) -> dict:
    try:
        bundle = load_data_bundle(state.data_source)
    except IngestionFatalError as exc:
        logger.error("Ingestion fatal error: %s", exc)
        return {"aborted": True, "errors": state.errors + [str(exc)]}

    if bundle.quality.is_degraded:
        logger.warning(
            "Data quality degraded: %d fayl yo'q, %d qator karantinda, %d orphan FK",
            len(bundle.quality.files_missing),
            len(bundle.quality.quarantined),
            bundle.quality.orphaned_fk_count,
        )
    return {"bundle": bundle}


def node_attendance(state: PipelineState) -> dict:
    assert state.bundle is not None
    return {"attendance_out": run_attendance_agent(state.bundle)}


def node_performance(state: PipelineState) -> dict:
    assert state.bundle is not None and state.attendance_out is not None
    return {
        "performance_out": run_performance_agent(state.bundle, state.attendance_out.flagged)
    }


def node_integration(state: PipelineState) -> dict:
    assert state.bundle is not None
    assert state.attendance_out is not None and state.performance_out is not None
    return {
        "integration_out": run_integration_agent(
            state.bundle, state.attendance_out, state.performance_out, state.data_source
        )
    }


def _route_after_ingest(state: PipelineState) -> str:
    return "abort" if state.aborted else "attendance"


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("ingest", node_ingest)
    graph.add_node("attendance", node_attendance)
    graph.add_node("performance", node_performance)
    graph.add_node("integration", node_integration)

    graph.add_edge(START, "ingest")
    graph.add_conditional_edges(
        "ingest", _route_after_ingest, {"attendance": "attendance", "abort": END}
    )
    graph.add_edge("attendance", "performance")
    graph.add_edge("performance", "integration")
    graph.add_edge("integration", END)
    return graph.compile()


def run_pipeline(data_source: str) -> PipelineState:
    app = build_graph()
    final_state = app.invoke(PipelineState(data_source=data_source))
    return PipelineState.model_validate(final_state)
