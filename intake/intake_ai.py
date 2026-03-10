"""
Conversational AI intake engine for ts-demo-factory.

Guides the user through 6 steps to collaboratively design a ThoughtSpot demo:
  1. Customer context  — company name + web research (industry auto-detected)
  2. Analytics domain  — pick the business area to focus the demo on
  3. Use-case design   — concrete use-case within the selected domain
  4. Schema design     — design star schema (fact + dimensions)
  5. Dataset config    — volume, history depth, data patterns
  6. Liveboard design  — plan charts and KPIs

Usage:
    from intake.intake_ai import IntakeEngine
    config = IntakeEngine().run()
"""
from __future__ import annotations

import json
from pathlib import Path

import anthropic

from intake.intake_prompts import EXTRACTION_PROMPTS, SYSTEM_PROMPTS
from scripts.schema_to_pipeline import json_to_joins, json_to_table_defs

SKILLS_DIR = Path(__file__).parent / "skills"

STEPS = ["context", "domain", "usecase", "schema", "dataset", "liveboard"]

STEP_LABELS = {
    "context":   "Step 1/6 — Customer context",
    "domain":    "Step 2/6 — Analytics domain",
    "usecase":   "Step 3/6 — Use-case",
    "schema":    "Step 4/6 — Dataset schema",
    "dataset":   "Step 5/6 — Dataset configuration",
    "liveboard": "Step 6/6 — Liveboard design",
}

# Sentinel phrases — each system prompt instructs the AI to say exactly this when the user confirms.
SENTINELS = {
    "context":   "Let's move on",
    "domain":    "Domain confirmed",
    "usecase":   "Moving to schema design",
    "schema":    "Schema confirmed",
    "dataset":   "Dataset configured",
    "liveboard": "Building your demo",
}

# Kick-off messages injected as the first user turn of each step to trigger the AI to open.
# All steps have a kickoff so the AI always opens each step with clear instructions.
STEP_KICKOFF = {
    "context":   "Let's start the demo setup.",
    "domain":    "Let's pick the analytics domain.",
    "usecase":   "Let's define the specific use-case.",
    "schema":    "Let's design the data schema.",
    "dataset":   "Let's configure the dataset.",
    "liveboard": "Now let's design the liveboard.",
}


class _ResetException(Exception):
    """Raised when the user types 'reset'."""


class IntakeEngine:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic()
        self.state: dict = {
            "step": "context",
            "customer_name": None,
            "industry": None,
            "company_summary": None,
            "domain": None,          # {name, description}
            "use_case": None,        # {title, description, data_needs}
            "schema": None,          # {tables, relationships}
            "dataset_config": None,  # {row_count, years, patterns: []}
            "liveboard_spec": None,  # {charts: [...]}
        }
        self.history: list[dict] = []

    # ── Public entry point ─────────────────────────────────────────────────────

    def run(self) -> dict:
        """Run all 6 steps interactively. Returns pipeline_config dict."""
        print("\n=== ts-demo-factory — AI Demo Builder ===")
        print("Type 'reset' to start over, 'skip' to use defaults for the current step.\n")

        for step in STEPS:
            self.state["step"] = step
            print(f"\n{'─' * 52}")
            print(f"  {STEP_LABELS[step]}")
            print(f"{'─' * 52}\n")

            try:
                self._run_step(step)
            except _ResetException:
                self.__init__()
                return self.run()

        return self._build_pipeline_config()

    # ── Step runner ────────────────────────────────────────────────────────────

    def _run_step(self, step: str) -> None:
        """Conversational loop for one step. Exits when the AI says the sentinel."""
        # Every step has a kickoff — inject it so the AI opens the step with instructions.
        kickoff = STEP_KICKOFF[step]
        self.history.append({"role": "user", "content": kickoff})

        # Context step: kickoff uses standard call (no web search for opening greeting).
        # Web search fires later when the user provides the company name.
        response = self._call_api()
        self._print_assistant(response)
        self.history.append({"role": "assistant", "content": response})

        if SENTINELS[step] in response:
            self._extract_and_store(step)
            return

        while True:
            try:
                user_input = input("> ").strip()
            except (KeyboardInterrupt, EOFError):
                raise SystemExit(0)

            if not user_input:
                continue

            cmd = user_input.lower()
            if cmd == "reset":
                raise _ResetException()
            if cmd == "skip":
                self._skip_step(step)
                return

            self.history.append({"role": "user", "content": user_input})

            if step == "context":
                response = self._call_with_web_search()
            else:
                response = self._call_api()

            self._print_assistant(response)
            self.history.append({"role": "assistant", "content": response})

            if SENTINELS[step] in response:
                self._extract_and_store(step)
                return

    # ── API calls ──────────────────────────────────────────────────────────────

    def _call_api(self) -> str:
        """Standard API call with full conversation history."""
        resp = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=self._system_prompt_for_step(),
            messages=self.history,
        )
        return resp.content[0].text

    def _call_with_web_search(self) -> str:
        """API call with web_search tool (context step only). Falls back to standard on error."""
        try:
            messages = list(self.history)
            for _ in range(6):  # max 5 search rounds + 1 final
                resp = self._client.beta.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    system=self._system_prompt_for_step(),
                    messages=messages,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    betas=["web-search-2025-03-05"],
                )

                text_parts = [
                    b.text for b in resp.content
                    if hasattr(b, "text") and b.type == "text"
                ]

                if resp.stop_reason != "tool_use":
                    return "\n".join(text_parts)

                # Tool invoked — add assistant turn and continue loop.
                content_blocks: list[dict] = []
                tool_use_id: str | None = None
                for b in resp.content:
                    if b.type == "tool_use":
                        tool_use_id = b.id
                        content_blocks.append({
                            "type": "tool_use",
                            "id": b.id,
                            "name": b.name,
                            "input": b.input,
                        })
                    elif b.type == "text" and b.text:
                        content_blocks.append({"type": "text", "text": b.text})

                messages.append({"role": "assistant", "content": content_blocks})

                if tool_use_id:
                    messages.append({
                        "role": "user",
                        "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": ""}],
                    })

            return "\n".join(text_parts) if text_parts else ""

        except Exception:
            # Web search unavailable — fall back to standard call.
            return self._call_api()

    def _extract(self, step: str) -> dict:
        """Silent JSON extraction call. Not appended to self.history."""
        messages = self.history + [{"role": "user", "content": EXTRACTION_PROMPTS[step]}]
        extra_nudge = " Output ONLY valid JSON with no extra text, no markdown code blocks."
        for attempt in range(2):
            resp = self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system="Extract structured data. Respond ONLY with valid JSON. No markdown, no explanation.",
                messages=messages,
            )
            raw = resp.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip().rstrip("`")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                if attempt == 0:
                    messages = messages[:-1] + [
                        {"role": "user", "content": EXTRACTION_PROMPTS[step] + extra_nudge}
                    ]
                else:
                    raise RuntimeError(
                        f"Extraction failed for step '{step}' after 2 attempts. "
                        f"Raw response: {raw[:300]}"
                    )

    # ── State management ───────────────────────────────────────────────────────

    def _extract_and_store(self, step: str) -> None:
        data = self._extract(step)
        if step == "context":
            self.state.update({
                "customer_name": data.get("customer_name"),
                "industry": data.get("industry"),
                "company_summary": data.get("company_summary"),
            })
        elif step == "domain":
            self.state["domain"] = data
        elif step == "usecase":
            self.state["use_case"] = data
        elif step == "schema":
            self.state["schema"] = data
        elif step == "dataset":
            self.state["dataset_config"] = data
        elif step == "liveboard":
            self.state["liveboard_spec"] = data

    def _skip_step(self, step: str) -> None:
        """Advance step with minimal defaults, skipping the conversation."""
        print("  [skip]")
        if step == "context":
            name = input("  Customer name: ").strip() or "Demo Customer"
            self.state.update({
                "customer_name": name,
                "industry": "retail",
                "company_summary": f"{name} is a retail company.",
            })
            self.history += [
                {"role": "user", "content": f"Company: {name}"},
                {"role": "assistant", "content": f"Got it — {name}. Let's move on."},
            ]
        elif step == "domain":
            self.state["domain"] = {
                "name": "Sales & Revenue",
                "description": "Track revenue trends and sales performance.",
            }
            self.history += [
                {"role": "user", "content": "Skip, use sales & revenue."},
                {"role": "assistant", "content": "Sales & Revenue selected. Domain confirmed. Moving to use-case design."},
            ]
        elif step == "usecase":
            self.state["use_case"] = {
                "title": "Sales Performance",
                "description": "Analyse revenue and quantity trends.",
                "data_needs": "revenue, quantity, date, product category, region",
            }
            self.history += [
                {"role": "user", "content": "Skip, use sales performance."},
                {"role": "assistant", "content": "Sales performance selected. Moving to schema design."},
            ]
        elif step == "schema":
            from scripts.generate_schema import generate_schema  # lazy import
            print("  Generating schema via API…")
            uc = self.state.get("use_case") or {}
            schema = generate_schema(
                customer=self.state.get("customer_name", "Demo"),
                industry=self.state.get("industry", "retail"),
                description=uc.get("description", "sales analytics"),
            )
            self.state["schema"] = schema
            self.history += [
                {"role": "user", "content": "Use the auto-generated schema."},
                {"role": "assistant", "content": "Schema confirmed. Moving to dataset configuration."},
            ]
        elif step == "dataset":
            self.state["dataset_config"] = {"row_count": 10_000, "years": 2, "patterns": []}
            self.history += [
                {"role": "user", "content": "Use default dataset config."},
                {"role": "assistant", "content": "Small dataset, 2 years, no special patterns. Dataset configured."},
            ]
        elif step == "liveboard":
            # Empty charts list → orchestrator will auto-generate.
            self.state["liveboard_spec"] = {"charts": []}
            self.history += [
                {"role": "user", "content": "Use auto-generated liveboard."},
                {"role": "assistant", "content": "Liveboard confirmed. Building your demo."},
            ]

    # ── Pipeline config builder ────────────────────────────────────────────────

    def _build_pipeline_config(self) -> dict:
        schema = self.state["schema"]
        table_defs = json_to_table_defs(schema)
        joins = json_to_joins(schema)

        dataset_config = self.state.get("dataset_config") or {"row_count": 10_000, "years": 2, "patterns": []}

        liveboard_spec = self.state.get("liveboard_spec") or {}
        raw_charts = liveboard_spec.get("charts", [])

        # Keep only the keys the liveboard template expects; drop intermediates.
        CHART_KEYS = ("title", "search_query", "attr_resolved", "measure_resolved", "chart_type")
        charts: list[dict] | None = (
            [{k: c[k] for k in CHART_KEYS if k in c} for c in raw_charts]
            if raw_charts else None  # None → orchestrator auto-generates via _build_charts()
        )

        return {
            "customer_name": self.state["customer_name"],
            "industry": self.state["industry"],
            "use_case_title": (self.state.get("use_case") or {}).get("title", ""),
            "table_defs": table_defs,
            "joins": joins,
            "charts": charts,
            "row_count": dataset_config["row_count"],
            "years": dataset_config.get("years", 2),
            "patterns": dataset_config.get("patterns", []),
        }

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _system_prompt_for_step(self) -> str:
        step = self.state["step"]
        base = SYSTEM_PROMPTS[step]
        if step in ("schema", "liveboard"):
            skill_name = "star_schema.md" if step == "schema" else "ts_liveboard.md"
            skill = self._load_skill(skill_name)
            if skill:
                return f"{base}\n\n---\n\n{skill}"
        return base

    def _load_skill(self, name: str) -> str:
        path = SKILLS_DIR / name
        return path.read_text() if path.exists() else ""

    @staticmethod
    def _print_assistant(text: str) -> None:
        print(f"\nAI: {text}\n")
