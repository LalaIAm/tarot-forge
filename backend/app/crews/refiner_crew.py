"""Refiner crew: single agent that updates image prompt using evaluator feedback and style bible."""

from crewai import Agent, Crew, Process, Task

from app.crews.outputs import RefinedPrompt


def _refiner_agent() -> Agent:
    return Agent(
        role="Prompt Refinement Specialist",
        goal="Update image generation prompts using evaluator feedback and the style bible so the next image better matches the desired style and concept.",
        backstory="You are an expert at translating visual feedback into concrete prompt changes for image models. You preserve the card concept while addressing specific issues.",
        verbose=True,
    )


def _refine_task(agent: Agent) -> Task:
    return Task(
        description="""Update the image prompt using the evaluator's feedback and the style bible.

Style bible:
{style_bible}

Current image prompt that was rejected:
{current_image_prompt}

Evaluator feedback (why it was rejected):
{evaluator_feedback}

Produce an updated image prompt that addresses the feedback while staying true to the style bible. Optionally suggest an updated short description if the narrative should shift.""",
        expected_output="Updated image_prompt and optional description.",
        agent=agent,
        output_pydantic=RefinedPrompt,
    )


def build_refiner_crew() -> Crew:
    agent = _refiner_agent()
    task = _refine_task(agent)
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)


def run_refiner(
    *,
    current_image_prompt: str,
    evaluator_feedback: str,
    style_bible: str,
) -> RefinedPrompt:
    """Run the refiner to get an updated image prompt from evaluator feedback."""
    crew = build_refiner_crew()
    result = crew.kickoff(
        inputs={
            "style_bible": style_bible,
            "current_image_prompt": current_image_prompt,
            "evaluator_feedback": evaluator_feedback,
        }
    )
    if result.pydantic is None:
        raise ValueError("Refiner did not return structured RefinedPrompt")
    return result.pydantic
