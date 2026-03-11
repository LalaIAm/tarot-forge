"""Tests for evaluator crew. Mocks vision LLM."""

from unittest.mock import patch

from crewai import Process

from app.crews.evaluator_crew import build_evaluator_crew, run_evaluator
from app.crews.outputs import ApproveReject, CardConcept


def test_build_evaluator_crew_has_one_agent_and_one_task():
    crew = build_evaluator_crew()
    assert len(crew.agents) == 1
    assert len(crew.tasks) == 1
    assert crew.process == Process.sequential
    assert crew.agents[0].multimodal is True


def test_run_evaluator_returns_approve_reject():
    concept = CardConcept(
        name="The Fool",
        meaning="New beginnings.",
        description="A traveler at a cliff.",
        image_prompt="A lone figure at a cliff.",
    )
    fake_approve = ApproveReject(decision="APPROVE", feedback=None)
    fake_result = type("CrewOutput", (), {"pydantic": fake_approve})()
    mock_crew = type("MockCrew", (), {"kickoff": lambda self, **kw: fake_result})()
    with patch("app.crews.evaluator_crew.build_evaluator_crew", return_value=mock_crew):
        result = run_evaluator(
            style_bible="# Style Bible\nDark palette.",
            concept=concept,
            image_path="/tmp/decks/d1/c1.png",
        )
    assert result.decision == "APPROVE"
    assert result.feedback is None


def test_run_evaluator_returns_reject_with_feedback():
    concept = CardConcept(name="The Fool", meaning="x", description="y", image_prompt="z")
    fake_reject = ApproveReject(decision="REJECT", feedback="Add more contrast and a cliff edge.")
    fake_result = type("CrewOutput", (), {"pydantic": fake_reject})()
    mock_crew = type("MockCrew", (), {"kickoff": lambda self, **kw: fake_result})()
    with patch("app.crews.evaluator_crew.build_evaluator_crew", return_value=mock_crew):
        result = run_evaluator(
            style_bible="# Bible",
            concept=concept,
            image_path="/tmp/card.png",
        )
    assert result.decision == "REJECT"
    assert "cliff" in result.feedback
