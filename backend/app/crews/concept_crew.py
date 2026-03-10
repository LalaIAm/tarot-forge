"""Concept crew per card: Tarot Scholar → Visual Designer. Output: name, meaning, description, image_prompt."""

from crewai import Agent, Crew, Process, Task

from app.crews.outputs import CardConcept, ImagePromptOutput, MeaningDescription


def _tarot_scholar() -> Agent:
    return Agent(
        role="Tarot Scholar",
        goal="Provide accurate tarot meaning and symbolism and a short narrative description for each card that respects tradition and supports visual interpretation.",
        backstory="You are a tarot symbolism expert with deep knowledge of Rider-Waite and Thoth traditions. You distill meaning and symbolism into clear, evocative text that illustrators can use.",
        verbose=True,
    )


def _visual_designer() -> Agent:
    return Agent(
        role="Visual Designer",
        goal="Write a single image generation prompt for the card that matches the style bible and the card's meaning.",
        backstory="You are a visual designer who turns creative briefs and style guides into concrete image prompts for generative art. You ensure prompts are specific, style-consistent, and actionable.",
        verbose=True,
    )


def _meaning_task(agent: Agent) -> Task:
    return Task(
        description="""For this tarot card, provide its meaning and a short narrative description.
Card name: {card_name}
Card index (0-based): {card_index}
Style bible (for tone and symbolism alignment):
{style_bible}

Output the traditional meaning and symbolism, and a 2–3 sentence narrative description suitable for guiding an illustration.""",
        expected_output="Structured meaning and a short narrative description for the card.",
        agent=agent,
        output_pydantic=MeaningDescription,
    )


def _image_prompt_task(agent: Agent, meaning_task: Task) -> Task:
    return Task(
        description="""Using the style bible and the card's meaning/description, write a single image generation prompt for this card.
Style bible:
{style_bible}
Card name: {card_name}
Card meaning and description (from previous step): use the context from your teammate.

The prompt must be detailed enough for an image model (e.g. DALL·E, Stable Diffusion): scene, style, mood, key symbols, composition. One paragraph, no bullet lists.""",
        expected_output="A single paragraph image prompt for the card.",
        agent=agent,
        context=[meaning_task],
        output_pydantic=ImagePromptOutput,
    )


def build_concept_crew() -> Crew:
    scholar = _tarot_scholar()
    designer = _visual_designer()
    meaning_task = _meaning_task(scholar)
    image_prompt_task = _image_prompt_task(designer, meaning_task)
    return Crew(
        agents=[scholar, designer],
        tasks=[meaning_task, image_prompt_task],
        process=Process.sequential,
        verbose=True,
    )


def run_concept_crew(
    *,
    style_bible: str,
    card_name: str,
    card_index: int,
) -> CardConcept:
    """Run the concept crew for one card; return CardConcept (name, meaning, description, image_prompt)."""
    crew = build_concept_crew()
    result = crew.kickoff(
        inputs={
            "style_bible": style_bible,
            "card_name": card_name,
            "card_index": card_index,
        }
    )
    # Crew output is the last task's output (ImagePromptOutput). We need both task outputs.
    tasks_out = result.tasks_output
    if len(tasks_out) < 2:
        raise ValueError("Concept crew did not return both task outputs")
    meaning_out = tasks_out[0].pydantic
    image_out = tasks_out[1].pydantic
    if meaning_out is None or image_out is None:
        raise ValueError("Concept crew task outputs are not structured")
    return CardConcept(
        name=card_name,
        meaning=meaning_out.meaning,
        description=meaning_out.description,
        image_prompt=image_out.image_prompt,
    )
