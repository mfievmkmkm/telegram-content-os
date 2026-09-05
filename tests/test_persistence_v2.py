from content_os.persistence_v2 import install


class LegacyDB:
    def __init__(self):
        self.events = []

    def save_funnel_event(self, user_id, event_type, source="", offer_key=""):
        if event_type not in {"landing", "offer_view", "order_created"}:
            raise ValueError("legacy constraint")
        self.events.append((user_id, event_type, source, offer_key))


def test_new_funnel_events_degrade_to_legacy_names_without_loss():
    db = install(LegacyDB())
    db.save_funnel_event(1, "recommendation", "c_g_1_p", "tracker")
    db.record_growth_event(1, "paid", "c_g_1_p", "tracker", order_id=7, revenue=990)
    assert db.events == [
        (1, "offer_view", "c_g_1_p", "tracker"),
        (1, "order_created", "c_g_1_p", "tracker"),
    ]
