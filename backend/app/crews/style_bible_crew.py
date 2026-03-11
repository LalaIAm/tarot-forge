"""Style-bible crew: Style Researcher → Creative Director → Designer."""

from crewai import Agent, Crew, Process, Task

from app.crews.outputs import StyleBibleOutput


def _style_researcher() -> Agent:
    return Agent(
        role="Style Researcher",
        goal="Research the given artistic medium and related visual traditions to ground the style bible in real references and best practices.",
        backstory="You are an art historian and visual culture researcher. You find references, traditions, and technical constraints for artistic media and help creative teams stay coherent and informed.",
        verbose=True,
    )


def _creative_director() -> Agent:
    return Agent(
        role="Creative Director",
        goal="Turn the user's creative direction and research into a single, coherent creative brief that a designer can execute.",
        backstory="You are a visual design director who specializes in brand and product style guides. You synthesize research and client direction into clear, actionable creative briefs.",
        verbose=True,
    )


def _designer() -> Agent:
    return Agent(
        role="Designer",
        goal="Produce a structured style bible (palette, typography, symbolism, layout, tone) that can guide tarot card art generation.",
        backstory="You are a visual designer specializing in style guides and design systems. You turn creative briefs into concrete, sectioned style bibles suitable for illustrators and image generation.",
        verbose=True,
    )


def _research_task(agent: Agent) -> Task:
    return Task(
        description="""Research the artistic medium and visual traditions relevant to this project.
User direction: {creative_direction}
Medium: {medium}
Deck size: {deck_size} cards.
Output concise research notes: key visual references, medium-specific constraints, and traditions that match the direction.""",
        expected_output="Research notes (bullet points or short paragraphs) on the medium, references, and traditions.",
        agent=agent,
    )


def _brief_task(agent: Agent, research_task: Task) -> Task:
    return Task(
        description="""Using the research provided, write a single coherent creative brief.
The brief should capture: mood, key visual references, constraints from the medium, and clear direction for the style bible.
User direction: {creative_direction}
Medium: {medium}
{feedback_section}""",
        expected_output="A creative brief (1–2 paragraphs) that a designer can use to produce the style bible.",
        agent=agent,
        context=[research_task],
    )


def _style_bible_task(agent: Agent, brief_task: Task) -> Task:
    return Task(
        description="""Turn the creative brief into a structured style bible for a tarot deck.
Include: palette (colors and usage), typography (if any text on cards), symbolism (how to treat tarot symbols), layout (composition, borders, framing), tone (mood and consistency).
Ensure the style bible is specific enough to guide card-by-card image generation.""",
        expected_output="A structured style bible with sections: palette, typography, symbolism, layout, tone.",
        agent=agent,
        context=[brief_task],
        output_pydantic=StyleBibleOutput,
    )


def build_style_bible_crew() -> Crew:
    researcher = _style_researcher()
    director = _creative_director()
    designer = _designer()
    research_task = _research_task(researcher)
    brief_task = _brief_task(director, research_task)
    style_bible_task = _style_bible_task(designer, brief_task)
    return Crew(
        agents=[researcher, director, designer],
        tasks=[research_task, brief_task, style_bible_task],
        process=Process.sequential,
        verbose=True,
    )


def run_style_bible_crew(
    *,
    creative_direction: str,
    medium: str,
    deck_size: int = 78,
    feedback: str | None = None,
) -> StyleBibleOutput:
    """Run the style-bible crew and return the structured output."""
    crew = build_style_bible_crew()
    feedback_section = f"User feedback to incorporate: {feedback}" if feedback else ""
    result = crew.kickoff(
        inputs={
            "creative_direction": creative_direction,
            "medium": medium,
            "deck_size": deck_size,
            "feedback_section": feedback_section,
        }
    )
    if result.pydantic is None:
        raise ValueError("Crew did not return structured StyleBibleOutput")
    return result.pydantic
