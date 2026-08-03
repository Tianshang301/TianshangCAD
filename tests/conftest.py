"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from cad_mcp_server.core.document import DocumentManager
from cad_mcp_server.core.entity import EntityManager
from cad_mcp_server.core.kernel import AnalyticKernel
from cad_mcp_server.core.scheduler import get_scheduler
from cad_mcp_server.core.session import SessionManager
from cad_mcp_server.mcp.tools.nlp import clear_chat_session
from cad_mcp_server.mcp.tools.status import _log_buffer


@pytest.fixture(autouse=True)
def _clean_sessions() -> None:
    """Reset the global session state before and after every test."""
    SessionManager().reset()
    yield
    SessionManager().reset()


@pytest.fixture(autouse=True)
def _clean_chat() -> None:
    """Reset NLP dialogue state before and after every test."""
    clear_chat_session()
    yield
    clear_chat_session()


@pytest.fixture(autouse=True)
def _clean_logs() -> None:
    """Clear the in-memory log ring buffer before and after every test."""
    _log_buffer.clear()
    yield
    _log_buffer.clear()


@pytest.fixture(autouse=True)
def _clean_scheduler() -> None:
    """Force the batch scheduler into in-memory mode for every test."""
    scheduler = get_scheduler()
    scheduler.configure(jobstore_url=None)
    yield
    scheduler.configure(jobstore_url=None)


@pytest.fixture
def kernel() -> AnalyticKernel:
    """Return a fresh analytic kernel."""
    return AnalyticKernel()


@pytest.fixture
def entity_manager() -> EntityManager:
    """Return an entity manager bound to the analytic kernel."""
    return EntityManager(kernel=AnalyticKernel())


@pytest.fixture
def document_manager() -> DocumentManager:
    """Return a document manager bound to a fresh session."""
    return DocumentManager()


@pytest.fixture
def document():
    """Create and return the current document of a fresh session."""
    manager = DocumentManager()
    manager.create("test.json", unit="mm")
    return manager.get_current()
