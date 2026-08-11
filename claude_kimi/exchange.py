"""Exchange orchestrator: routes prompts and results between Claude and Kimi.

Modes
-----
review : Claude drafts, Kimi reviews with a verdict, Claude revises — loop
         until Kimi approves or max rounds are reached.
collab : the agents take turns building on a shared transcript until one of
         them declares FINAL ANSWER (or rounds run out, then Claude wraps up).
debate : both answer independently, rebut each other for N rounds, then
         Claude writes a synthesis of the strongest points.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .agents import ClaudeAgent, KimiAgent, Turn

APPROVE_TOKEN = "VERDICT: APPROVE"
FINAL_TOKEN = "FINAL ANSWER"


@dataclass
class Exchange:
    task: str
    mode: str = "review"
    max_rounds: int = 4
    turns: list[Turn] = field(default_factory=list)
    result: str = ""

    def __post_init__(self):
        self.claude = ClaudeAgent(system=self._claude_system())
        self.kimi = KimiAgent(system=self._kimi_system())

    # -- system prompts -------------------------------------------------

    def _claude_system(self) -> str:
        if self.mode == "review":
            return (
                "You are the author in an author/reviewer workflow with another AI "
                "(Kimi). Produce complete, high-quality work for the given task. "
                "When you receive review feedback, address every point and return "
                "the full revised deliverable, not just a diff."
            )
        if self.mode == "collab":
            return (
                "You are collaborating turn-by-turn with another AI (Kimi) on one "
                "task. Build concretely on the shared transcript — add new value "
                f"each turn. When the work is complete, start a line with "
                f"'{FINAL_TOKEN}:' followed by the finished deliverable."
            )
        return (
            "You are debating another AI (Kimi). Argue your position rigorously, "
            "concede points that are correct, and refine your answer each round."
        )

    def _kimi_system(self) -> str:
        if self.mode == "review":
            return (
                "You are the reviewer in an author/reviewer workflow with another AI "
                "(Claude). Critique the submitted work: correctness, completeness, "
                "clarity. List concrete, actionable issues. End with exactly one "
                f"line: '{APPROVE_TOKEN}' if the work needs no further changes, or "
                "'VERDICT: REVISE' otherwise."
            )
        if self.mode == "collab":
            return (
                "You are collaborating turn-by-turn with another AI (Claude) on one "
                "task. Build concretely on the shared transcript — add new value "
                f"each turn. When the work is complete, start a line with "
                f"'{FINAL_TOKEN}:' followed by the finished deliverable."
            )
        return (
            "You are debating another AI (Claude). Argue your position rigorously, "
            "concede points that are correct, and refine your answer each round."
        )

    # -- helpers --------------------------------------------------------

    def _record(self, agent: str, role: str, content: str) -> None:
        self.turns.append(Turn(agent=agent, role=role, content=content))
        print(f"\n{'=' * 70}\n[{agent} — {role}]\n{'=' * 70}\n{content}\n")

    # -- modes ----------------------------------------------------------

    def run(self) -> str:
        runner = {"review": self._run_review, "collab": self._run_collab, "debate": self._run_debate}
        if self.mode not in runner:
            raise ValueError(f"Unknown mode: {self.mode!r} (use review, collab, or debate)")
        self.result = runner[self.mode]()
        return self.result

    def _run_review(self) -> str:
        draft = self.claude.send(f"Task:\n{self.task}\n\nProduce your best complete draft.")
        self._record("Claude", "draft", draft)

        for round_no in range(1, self.max_rounds + 1):
            review = self.kimi.send(
                f"Task:\n{self.task}\n\nSubmitted work:\n{draft}\n\nReview it."
            )
            self._record("Kimi", f"review {round_no}", review)
            if APPROVE_TOKEN in review.upper().replace("**", ""):
                break
            draft = self.claude.send(
                f"The reviewer returned this feedback:\n{review}\n\n"
                "Address every point and return the full revised deliverable."
            )
            self._record("Claude", f"revision {round_no}", draft)
        return draft

    def _run_collab(self) -> str:
        message = f"Task:\n{self.task}\n\nYou go first — start the work."
        agents = [self.claude, self.kimi]
        for i in range(self.max_rounds * 2):
            agent = agents[i % 2]
            reply = agent.send(message)
            self._record(agent.name, f"turn {i + 1}", reply)
            if FINAL_TOKEN in reply:
                return reply.split(f"{FINAL_TOKEN}:", 1)[-1].strip() or reply
            message = (
                f"Your collaborator ({agent.name}) said:\n{reply}\n\n"
                "Continue the work. Declare the final answer only when it is truly done."
            )
        final = self.claude.send(
            "Rounds are exhausted. Write the final, complete deliverable now, "
            f"starting with '{FINAL_TOKEN}:'."
        )
        self._record("Claude", "final", final)
        return final.split(f"{FINAL_TOKEN}:", 1)[-1].strip() or final

    def _run_debate(self) -> str:
        prompt = f"Question:\n{self.task}\n\nGive your position and reasoning."
        claude_pos = self.claude.send(prompt)
        self._record("Claude", "opening", claude_pos)
        kimi_pos = self.kimi.send(prompt)
        self._record("Kimi", "opening", kimi_pos)

        for round_no in range(1, self.max_rounds + 1):
            claude_pos = self.claude.send(
                f"Your opponent argued:\n{kimi_pos}\n\nRebut and refine your position."
            )
            self._record("Claude", f"rebuttal {round_no}", claude_pos)
            kimi_pos = self.kimi.send(
                f"Your opponent argued:\n{claude_pos}\n\nRebut and refine your position."
            )
            self._record("Kimi", f"rebuttal {round_no}", kimi_pos)

        synthesis = self.claude.send(
            "The debate is over. Write a balanced synthesis: the strongest points "
            "from both sides and the best-supported overall answer."
        )
        self._record("Claude", "synthesis", synthesis)
        return synthesis

    # -- persistence ----------------------------------------------------

    def save(self, out_dir: str | Path = "transcripts") -> Path:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = out / f"{self.mode}-{stamp}"

        base.with_suffix(".json").write_text(
            json.dumps(
                {
                    "task": self.task,
                    "mode": self.mode,
                    "turns": [t.__dict__ for t in self.turns],
                    "result": self.result,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        md = [f"# {self.mode.title()} exchange\n", f"**Task:** {self.task}\n"]
        for t in self.turns:
            md.append(f"## {t.agent} — {t.role}\n\n{t.content}\n")
        md.append(f"## Result\n\n{self.result}\n")
        base.with_suffix(".md").write_text("\n".join(md), encoding="utf-8")
        return base.with_suffix(".md")
