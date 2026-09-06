from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from .experiment_results import evaluate
from .experiments import Experiment, ExperimentVariant


KEY = "v2:experiments"


class ExperimentStore:
    """Small durable experiment lifecycle on top of the shared settings store."""

    def __init__(self, db, limit: int = 50):
        self.db, self.limit = db, limit

    def list(self) -> list[dict]:
        try:
            value = json.loads(self.db.get(KEY) or "[]")
            return value if isinstance(value, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    def create(self, project: str, hypothesis: str, variable: str, control: str, challenger: str,
               metric: str, draft_ids=()) -> dict:
        row = {"id": uuid4().hex[:10], "project": project, "hypothesis": hypothesis,
               "variable": variable, "control": control, "challenger": challenger,
               "metric": metric, "status": "planned", "draft_ids": list(draft_ids),
               "control_scores": [], "challenger_scores": [], "created_at": datetime.now(timezone.utc).isoformat()}
        rows = self.list(); rows.append(row); self._save(rows[-self.limit:]); return row

    def add_sample(self, experiment_id: str, variant: str, score: float) -> dict:
        rows = self.list(); found = next((row for row in rows if row.get("id") == experiment_id), None)
        if found is None: raise KeyError("experiment not found")
        key = "control_scores" if variant == "control" else "challenger_scores" if variant == "challenger" else ""
        if not key: raise ValueError("variant must be control or challenger")
        found.setdefault(key, []).append(float(score)); found["status"] = "collecting"
        exp = Experiment(found["hypothesis"], found["variable"],
                         ExperimentVariant("control", {found["variable"]: found["control"]}),
                         ExperimentVariant("challenger", {found["variable"]: found["challenger"]}), found["metric"], 2)
        result = evaluate(exp, found["control_scores"], found["challenger_scores"])
        found.update(status=result.status, uplift_percent=round(result.uplift_percent, 2), recommendation=result.recommendation)
        self._save(rows); return found

    def _save(self, rows):
        self.db.set(KEY, json.dumps(rows, ensure_ascii=False))
