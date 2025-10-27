
import datetime
import logging
import re
from collections.abc import AsyncGenerator
from typing import Literal

from google.adk.agents import BaseAgent, LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.planners import BuiltInPlanner
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.genai import types as genai_types
from pydantic import BaseModel, Field

from .config import config


# --- Structured Output Models ---
class SearchQuery(BaseModel):
    """Model representing a specific search query for web search."""

    search_query: str = Field(
        description="A highly specific and targeted query for web search."
    )


class Feedback(BaseModel):
    """Model for providing evaluation feedback on research quality."""

    grade: Literal["pass", "fail"] = Field(
        description="Evaluation result. 'pass' if the research is sufficient, 'fail' if it needs revision."
    )
    comment: str = Field(
        description="Detailed explanation of the evaluation, highlighting strengths and/or weaknesses of the research."
    )
    follow_up_queries: list[SearchQuery] | None = Field(
        default=None,
        description="A list of specific, targeted follow-up search queries needed to fix research gaps. This should be null or empty if the grade is 'pass'.",
    )


# --- Callbacks ---
def collect_research_sources_callback(callback_context: CallbackContext) -> None:
    """Collects and organizes web-based research sources and their supported claims from agent events."""
    session = callback_context._invocation_context.session
    url_to_short_id = callback_context.state.get("url_to_short_id", {})
    sources = callback_context.state.get("sources", {})
    id_counter = len(url_to_short_id) + 1
    for event in session.events:
        if not (event.grounding_metadata and event.grounding_metadata.grounding_chunks):
            continue
        chunks_info = {}
        for idx, chunk in enumerate(event.grounding_metadata.grounding_chunks):
            if not chunk.web:
                continue
            url = chunk.web.uri
            title = (
                chunk.web.title
                if chunk.web.title != chunk.web.domain
                else chunk.web.domain
            )
            if url not in url_to_short_id:
                short_id = f"src-{id_counter}"
                url_to_short_id[url] = short_id
                sources[short_id] = {
                    "short_id": short_id,
                    "title": title,
                    "url": url,
                    "domain": chunk.web.domain,
                    "supported_claims": [],
                }
                id_counter += 1
            chunks_info[idx] = url_to_short_id[url]
        if event.grounding_metadata.grounding_supports:
            for support in event.grounding_metadata.grounding_supports:
                confidence_scores = support.confidence_scores or []
                chunk_indices = support.grounding_chunk_indices or []
                for i, chunk_idx in enumerate(chunk_indices):
                    if chunk_idx in chunks_info:
                        short_id = chunks_info[chunk_idx]
                        confidence = (
                            confidence_scores[i] if i < len(confidence_scores) else 0.5
                        )
                        text_segment = support.segment.text if support.segment else ""
                        sources[short_id]["supported_claims"].append(
                            {
                                "text_segment": text_segment,
                                "confidence": confidence,
                            }
                        )
    callback_context.state["url_to_short_id"] = url_to_short_id
    callback_context.state["sources"] = sources


def citation_replacement_callback(
    callback_context: CallbackContext,
) -> genai_types.Content:
    """Replaces citation tags in a report with Markdown-formatted links."""
    final_report = callback_context.state.get("final_cited_report", "")
    sources = callback_context.state.get("sources", {})

    def tag_replacer(match: re.Match) -> str:
        short_id = match.group(1)
        if not (source_info := sources.get(short_id)):
            logging.warning(f"Invalid citation tag found and removed: {match.group(0)}")
            return ""
        display_text = source_info.get("title", source_info.get("domain", short_id))
        return f" [{display_text}]({source_info['url']})"

    processed_report = re.sub(
        r'<cite\s+source\s*=\s*["\']?\s*(src-\d+)\s*["\']?\s*/>',
        tag_replacer,
        final_report,
    )
    processed_report = re.sub(r"\s+([.,;:])", r"\1", processed_report)
    callback_context.state["final_report_with_citations"] = processed_report
    return genai_types.Content(parts=[genai_types.Part(text=processed_report)])


# --- Custom Agent for Loop Control ---
class EscalationChecker(BaseAgent):
    """Checks research evaluation and escalates to stop the loop if grade is 'pass'."""

    def __init__(self, name: str):
        super().__init__(name=name)

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        evaluation_result = ctx.session.state.get("research_evaluation")
        if evaluation_result and evaluation_result.get("grade") == "pass":
            logging.info(
                f"[{self.name}] Research evaluation passed. Escalating to stop loop."
            )
            yield Event(author=self.name, actions=EventActions(escalate=True))
        else:
            logging.info(
                f"[{self.name}] Research evaluation failed or not found. Loop will continue."
            )
            yield Event(author=self.name)


# --- AGENT DEFINITIONS ---
plan_generator = LlmAgent(
    model=config.worker_model,
    name="plan_generator",
    description="Generates or refines a strategic consulting plan focused on corporate management and marketing systems.",
    instruction=f"""
    You are ziris-x, a world-class strategic consultant specializing in corporate management and marketing systems.
    Your role is to create a high-level CONSULTING ACTION PLAN—not a summary—tailored to the user’s business challenge.

    If a plan already exists in session state, refine it based on user feedback.

    **CONSULTING PLAN(SO FAR):**
    {{ research_plan? }}

    **TASK CLASSIFICATION RULES:**
    Each bullet must start with a task-type prefix:
    - **`[ANALYSIS]`**: For diagnostic, investigative, or data-gathering tasks (e.g., "Analyze current marketing funnel inefficiencies").
    - **`[STRATEGY]`**: For synthesizing insights into actionable frameworks, recommendations, or deliverables (e.g., "Design a go-to-market strategy for Product X").

    **INITIAL OUTPUT REQUIREMENTS:**
    - Begin with exactly 5 action-oriented consulting goals.
    - All initial goals must be `[ANALYSIS]`.
    - Use strong verbs: Assess, Diagnose, Benchmark, Map, Evaluate.
    - **Proactively add implied deliverables** as `[STRATEGY][IMPLIED]` if a natural output is expected (e.g., a SWOT table, org chart, campaign roadmap).

    **REFINEMENT RULES:**
    - Mark modified tasks with `[MODIFIED]`, new ones with `[NEW]`.
    - Maintain original order; append new items unless instructed otherwise.
    - Expand beyond 5 bullets if needed to cover strategic depth.

    **SEARCH RESTRICTION:**
    Only use `google_search` if the business domain, industry, or company is ambiguous.
    Never research content—only clarify scope. You are a strategist, not a data miner.

    Current date: {datetime.datetime.now().strftime("%Y-%m-%d")}
    """,
    tools=[google_search],
)


section_planner = LlmAgent(
    model=config.worker_model,
    name="section_planner",
    description="Structures the consulting plan into a professional report outline for corporate clients.",
    instruction="""
    You are a senior management consultant at ziris-x. Create a clear, executive-ready markdown outline for a consulting report based on the approved plan.

    Ignore all tags like [ANALYSIS], [STRATEGY], etc.

    Structure the report into 4–6 logical sections covering:
    - Current state assessment
    - Key challenges & opportunities
    - Strategic recommendations
    - Implementation roadmap (if applicable)

    Do NOT include a References section. Citations will be inline.

    Use professional consulting language. Example:
    # Strategic Marketing Assessment
    Overview of current digital marketing performance, channel efficiency, and competitive positioning.
    """,
    output_key="report_sections",
)


section_researcher = LlmAgent(
    model=config.worker_model,
    name="section_researcher",
    description="Executes deep-dive research on corporate management and marketing best practices.",
    planner=BuiltInPlanner(
        thinking_config=genai_types.ThinkingConfig(include_thoughts=True)
    ),
    instruction="""
    You are ziris-x’s research engine, focused exclusively on corporate strategy, organizational design, and marketing systems.

    You will receive a plan with `[ANALYSIS]` and `[STRATEGY]` tasks.

    **Phase 1: Diagnostic Research (`[ANALYSIS]` Tasks)**
    - For each `[ANALYSIS]` goal, generate 4–5 precise search queries targeting frameworks, benchmarks, case studies, or industry standards.
    - Use `google_search` to execute all queries.
    - Summarize findings with actionable insights, citing credible sources (e.g., McKinsey, HBR, Gartner, Statista).

    **Phase 2: Strategic Synthesis (`[STRATEGY]` Tasks)**
    - Only begin after all `[ANALYSIS]` tasks are complete.
    - For each `[STRATEGY]` goal, produce the exact deliverable requested (e.g., a RACI matrix, customer journey map, marketing mix proposal).
    - Use ONLY data from Phase 1—no new searches.
    - Output must be structured, professional, and ready for C-suite review.

    Final output: All summaries + all strategic deliverables.
    """,
    tools=[google_search],
    output_key="section_research_findings",
    after_agent_callback=collect_research_sources_callback,
)

research_evaluator = LlmAgent(
    model=config.critic_model,
    name="research_evaluator",
    description="Evaluates the strategic depth and practical relevance of consulting research.",
    instruction=f"""
    You are ziris-x’s quality assurance lead. Evaluate the consulting research for strategic rigor, practical applicability, and alignment with modern management/marketing principles.

    **Focus Areas:**
    - Depth of diagnostic insight
    - Relevance to real-world business operations
    - Use of authoritative, up-to-date sources
    - Clarity and actionability of recommendations

    **Do NOT question the business premise.** Assume the client’s context is valid.

    If gaps exist (e.g., missing competitor analysis, superficial org assessment), grade "fail", explain why, and provide 5–7 targeted follow-up queries.

    If the analysis is comprehensive and strategic, grade "pass".

    Current date: {datetime.datetime.now().strftime("%Y-%m-%d")}
    Respond with a raw JSON object matching the 'Feedback' schema.
    """,
    output_schema=Feedback,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
    output_key="research_evaluation",
)

enhanced_search_executor = LlmAgent(
    model=config.worker_model,
    name="enhanced_search_executor",
    description="Refines consulting research based on evaluator feedback.",
    planner=BuiltInPlanner(
        thinking_config=genai_types.ThinkingConfig(include_thoughts=True)
    ),
    instruction="""
    You are ziris-x’s refinement specialist. The initial research was deemed insufficient.

    Steps:
    1. Review the 'research_evaluation' feedback.
    2. Execute every query in 'follow_up_queries' using `google_search`.
    3. Integrate new insights with existing findings to produce a comprehensive, boardroom-ready analysis.
    4. Output the complete, improved research set.
    """,
    tools=[google_search],
    output_key="section_research_findings",
    after_agent_callback=collect_research_sources_callback,
)

report_composer = LlmAgent(
    model=config.critic_model,
    name="report_composer_with_citations",
    include_contents="none",
    description="Composes a final executive consulting report with inline citations.",
    instruction="""
    You are the lead consultant at ziris-x. Transform the research and outline into a polished, persuasive executive report.

    ---
    ### INPUTS
    *   Consulting Plan: `{research_plan}`
    *   Findings & Deliverables: `{section_research_findings}`
    *   Sources: `{sources}`
    *   Report Outline: `{report_sections}`

    ---
    ### CITATION FORMAT
    Insert inline citations using: `<cite source="src-ID_NUMBER" />`

    ---
    ### OUTPUT RULES
    - Follow the outline exactly.
    - Write in clear, confident, boardroom-appropriate language.
    - Every strategic claim must be backed by a citation.
    - No standalone references section.
    """,
    output_key="final_cited_report",
    after_agent_callback=citation_replacement_callback,
)

research_pipeline = SequentialAgent(
    name="research_pipeline",
    description="Executes ziris-x’s end-to-end consulting workflow: analysis → strategy → executive report.",
    sub_agents=[
        section_planner,
        section_researcher,
        LoopAgent(
            name="iterative_refinement_loop",
            max_iterations=config.max_search_iterations,
            sub_agents=[
                research_evaluator,
                EscalationChecker(name="escalation_checker"),
                enhanced_search_executor,
            ],
        ),
        report_composer,
    ],
)

interactive_planner_agent = LlmAgent(
    name="ziris-x",
    model=config.worker_model,
    description="ziris-x: Your AI strategic consultant for corporate management and marketing systems.",
    instruction=f"""
    You are ziris-x — a premier AI consultant specializing in corporate strategy, organizational effectiveness, and integrated marketing systems.

    **Your mission:** Convert every user request into a tailored consulting engagement.

    **Workflow:**
    1. **Diagnose**: Use `plan_generator` to propose a strategic action plan.
    2. **Align**: Refine the plan with user input until approved.
    3. **Deliver**: Upon explicit approval (e.g., “Proceed” or “Run the analysis”), delegate to `research_pipeline`.

    **Rules:**
    - Never answer directly. Always initiate a consulting plan.
    - Frame everything through the lens of management best practices or marketing excellence.
    - Speak with authority, clarity, and strategic foresight.

    Current date: {datetime.datetime.now().strftime("%Y-%m-%d")}
    """,
    sub_agents=[research_pipeline],
    tools=[AgentTool(plan_generator)],
    output_key="research_plan",
)

root_agent = interactive_planner_agent
