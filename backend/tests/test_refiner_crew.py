"""Tests for refiner crew. Mocks LLM."""

from unittest.mock import patch

from crewai import Process

from app.crews.outputs import RefinedPrompt
from app.crews.refiner_crew import build_refiner_crew, run_refiner


def test_build_refiner_crew_has_one_agent_and_one_task():
    crew = build_refiner_crew()
    assert len(crew.agents) == 1
    assert len(crew.tasks) == 1
    assert crew.process == Process.sequential


def test_run_refiner_returns_refined_prompt():
    fake = RefinedPrompt(
        image_prompt="A lone figure at a cliff edge with stronger contrast and darker palette.",
        description="A traveler at a cliff, moody and dramatic.",
    )
    fake_result = type("CrewOutput", (), {"pydantic": fake})()
    mock_crew = type("MockCrew", (), {"kickoff": lambda self, **kw: fake_result})()
    with patch("app.crews.refiner_crew.build_refiner_crew", return_value=mock_crew):
        result = run_refiner(
            current_image_prompt="A figure at a cliff.",
            evaluator_feedback="Add more contrast and darker tones.",
            style_bible="# Style Bible\nDark palette.",
        )
    assert "contrast" in result.image_prompt or "darker" in result.image_prompt
    assert result.description is not None
