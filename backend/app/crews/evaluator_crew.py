"""Evaluator crew: single vision agent that approves or rejects a card image against style bible and concept."""

from crewai import Agent, Crew, Process, Task

from app.crews.outputs import ApproveReject, CardConcept


def _evaluator_agent() -> Agent:
    return Agent(
        role="Visual Quality Controller for Brand Consistency",
        goal="Decide whether a generated tarot card image matches the style bible and card concept; output APPROVE or REJECT with short reprompting feedback when rejecting.",
        backstory="You are a visual QA specialist who compares artwork to style guides and creative briefs. You give clear, actionable feedback for illustrators and image models.",
        verbose=True,
        multimodal=True,
    )


def _evaluation_task(agent: Agent) -> Task:
    return Task(
        description="""Evaluate the card image against the style bible and concept.

Style bible:
{style_bible}

Card concept:
- Name: {card_name}
- Meaning: {meaning}
- Description: {description}
- Image prompt used: {image_prompt}

Evaluate the image at: {image_path}
(Use the image at the path above. It is a local file path.)

Decide: does the image match the style bible and convey the card concept? If yes, output APPROVE. If no, output REJECT and provide short, specific feedback that a refiner could use to improve the image prompt (e.g. color, composition, missing symbols, tone).""",
        expected_output="APPROVE or REJECT, and if REJECT a short feedback string for reprompting.",
        agent=agent,
        output_pydantic=ApproveReject,
    )


def build_evaluator_crew() -> Crew:
    agent = _evaluator_agent()
    task = _evaluation_task(agent)
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)


def run_evaluator(
    *,
    style_bible: str,
    concept: CardConcept,
    image_path: str,
) -> ApproveReject:
    """Run the evaluator on one card image. image_path must be absolute for the agent to read it."""
    crew = build_evaluator_crew()
    result = crew.kickoff(
        inputs={
            "style_bible": style_bible,
            "card_name": concept.name,
            "meaning": concept.meaning,
            "description": concept.description,
            "image_prompt": concept.image_prompt,
            "image_path": image_path,
        }
    )
    if result.pydantic is None:
        raise ValueError("Evaluator did not return structured ApproveReject")
    return result.pydantic
