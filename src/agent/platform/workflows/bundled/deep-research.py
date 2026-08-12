# ruff: noqa: F821 - Workflow runtime injects the orchestration primitives.

meta = {
    "name": "deep-research",
    "description": "Research a question broadly, verify the evidence, and synthesize it",
    "whenToUse": "Use when the user explicitly asks for deep, multi-agent research",
    "phases": [
        {"title": "Research", "detail": "independent evidence-gathering lenses"},
        {"title": "Synthesize", "detail": "reconcile and verify the findings"},
    ],
}


async def main():
    topic = str(args or "the user's research question")
    phase("Research")
    findings = await parallel(
        [
            lambda: agent(
                f"Research primary and official sources for: {topic}",
                label="primary-sources",
                phase="Research",
            ),
            lambda: agent(
                f"Find independent evidence and counterarguments for: {topic}",
                label="independent-evidence",
                phase="Research",
            ),
            lambda: agent(
                f"Audit likely omissions, uncertainty, and stale claims for: {topic}",
                label="completeness-critic",
                phase="Research",
            ),
        ]
    )
    phase("Synthesize")
    return await agent(
        f"Synthesize a precise, source-aware answer for {topic}. "
        f"Reconcile these independent findings and preserve uncertainty: {findings}",
        label="synthesis",
        phase="Synthesize",
    )
