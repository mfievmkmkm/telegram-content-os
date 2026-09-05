from __future__ import annotations

from dataclasses import dataclass

from .content_quality import QualityDecision, build_fingerprint, review_candidate
from .editorial_memory import EditorialMemory


@dataclass(slots=True)
class DirectorResult:
    draft: object
    decision: QualityDecision
    rewrites: int = 0


class ContentDirectorService:
    """Quality gate that sits between generation and admin review.

    It uses deterministic checks first. A model rewrite is only spent when the
    material fails the gate, and at most two rewrites are attempted.
    """

    def __init__(self, editor, database, memory: EditorialMemory | None = None):
        self.editor = editor
        self.db = database
        self.memory = memory or EditorialMemory(database)

    def evaluate(self, draft) -> QualityDecision:
        channel = draft["channel_key"]
        history = list(self.memory.fingerprints(channel))
        # Imported own posts give lexical anti-repeat coverage before v2 memory has
        # accumulated enough structured fingerprints.
        for row in self.db.style_examples(channel, limit=12):
            text = str(row["text"] or "")
            fp = build_fingerprint(
                text=text,
                topic="legacy_history",
                angle="legacy_history",
                format_key="legacy",
            )
            history.append((fp, text))
        return review_candidate(
            text=draft["text"],
            channel=channel,
            topic=str(draft["source_title"] or draft["format_key"]),
            angle=str(draft["format_key"]),
            format_key=str(draft["format_key"]),
            history=history[-50:],
        )

    async def polish(self, draft_id: int | str, max_rewrites: int = 2) -> DirectorResult:
        draft = self.db.draft(int(draft_id))
        if not draft:
            raise KeyError(f"Draft {draft_id} not found")
        decision = self.evaluate(draft)
        rewrites = 0
        while not decision.approved and rewrites < max(0, min(max_rewrites, 2)):
            has_duplicate = any(issue.code in {"duplicate", "similar"} for issue in decision.report.issues)
            mode = "rewrite" if has_duplicate else "harder"
            text, hook_score = await self.editor.rewrite(draft, mode)
            self.db.update(int(draft_id), text=text, hook_score=hook_score)
            draft = self.db.draft(int(draft_id))
            decision = self.evaluate(draft)
            rewrites += 1
        return DirectorResult(draft=draft, decision=decision, rewrites=rewrites)

    def remember(self, result: DirectorResult) -> None:
        if not result.decision.approved:
            return
        draft = result.draft
        self.memory.remember_content(
            draft["channel_key"],
            result.decision.fingerprint,
            draft["text"],
            draft_id=draft["id"],
        )
