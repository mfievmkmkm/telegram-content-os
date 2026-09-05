from __future__ import annotations

from datetime import datetime
from types import MethodType


_LEGACY_EVENT_FALLBACK = {
    "visit": "landing",
    "bot_start": "landing",
    "recommendation": "offer_view",
    "lead": "offer_view",
    "order": "order_created",
    "paid": "order_created",
    "payment": "order_created",
    "sale": "order_created",
}


def install(db):
    """Install additive v2 persistence helpers without replacing the legacy DB layer.

    This bridge keeps old Supabase schemas usable during rollout: if a new funnel event
    hits the old CHECK constraint, it is stored using the closest legacy event type
    instead of being silently lost by the shop runtime.
    """
    original = db.save_funnel_event

    def safe_funnel(self, user_id, event_type, source="", offer_key=""):
        try:
            return original(user_id, event_type, source, offer_key)
        except Exception:
            fallback = _LEGACY_EVENT_FALLBACK.get(str(event_type or "").lower())
            if not fallback or fallback == event_type:
                raise
            return original(user_id, fallback, source, offer_key)

    db.save_funnel_event = MethodType(safe_funnel, db)

    def record_growth_event(self, user_id, event_type, source="", offer_key="", order_id=None, revenue=0.0):
        event_type = str(event_type or "").strip().lower()
        if hasattr(self, "client"):
            payload = {
                "user_id": user_id,
                "event_type": event_type,
                "source": source or None,
                "offer_key": offer_key or None,
                "created_at": datetime.now(self.timezone).isoformat(),
            }
            if order_id is not None:
                payload["order_id"] = order_id
            if revenue:
                payload["revenue"] = float(revenue)
            try:
                return self.client.table("content_os_funnel_events").insert(payload).execute()
            except Exception:
                # Rollout compatibility when additive columns/constraint migration has
                # not been applied yet.
                return safe_funnel(self, user_id, event_type, source, offer_key)
        return safe_funnel(self, user_id, event_type, source, offer_key)

    db.record_growth_event = MethodType(record_growth_event, db)
    return db
