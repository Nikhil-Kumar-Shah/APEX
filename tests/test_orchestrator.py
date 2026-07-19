"""Unit tests for APEX Runtime Orchestrator and event-driven background workers."""

import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from runtime.orchestrator.task_queue import Task, TaskQueue
from runtime.orchestrator.dispatcher import EventDispatcher
from runtime.orchestrator.state_machine import RuntimeStateMachine
from runtime.orchestrator.events import RuntimeEvent
from runtime.orchestrator.orchestrator import RuntimeOrchestrator


def test_task_queue_submissions():
    """Verifies task submission and scheduling priorities."""
    tq = TaskQueue()
    task1 = Task("download_model", priority=5)
    task2 = Task("load_model", priority=1)
    
    id1 = tq.submit(task1)
    id2 = tq.submit(task2)

    assert len(tq.list_tasks()) == 2
    # Task2 has higher priority (value 1 < 5)
    next_task = tq.get_next()
    assert next_task.task_id == id2


def test_event_dispatcher():
    """Checks event publication and wildcard subscriptions."""
    dispatcher = EventDispatcher()
    calls = []

    def cb(event):
        calls.append(event)

    dispatcher.subscribe("task_started", cb)
    dispatcher.subscribe("*", cb)

    event = RuntimeEvent("task_started", {"task_id": "abc"})
    dispatcher.publish(event)

    # Should have triggered twice (direct + wildcard)
    assert len(calls) == 2
    assert calls[0].event_type == "task_started"


def test_state_machine_transitions():
    """Checks state transition rules and callbacks."""
    sm = RuntimeStateMachine("STOPPED")
    transitions = []

    def listener(old, new):
        transitions.append((old, new))

    sm.register_listener(listener)

    assert sm.current_state == "STOPPED"
    assert sm.transition_to("LOADING_MODEL")
    assert sm.current_state == "LOADING_MODEL"
    assert len(transitions) == 1
    assert transitions[0] == ("STOPPED", "LOADING_MODEL")


def test_orchestrator_initialization():
    """Tests orchestrator background workers execution."""
    model_mock = MagicMock()
    ws_mock = MagicMock()
    
    orchestrator = RuntimeOrchestrator(model_mock, ws_mock)
    
    # Submit task
    task_id = orchestrator.submit_task("download_model", {"model_id": "test-repo"})
    assert task_id is not None
    
    time.sleep(0.5)
    orchestrator.shutdown()
