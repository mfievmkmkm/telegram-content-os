from pathlib import Path


def test_supabase_schema_accepts_runtime_funnel_events_and_metrics():
    sql = Path("supabase_schema.sql").read_text("utf-8")
    for event in ("recommendation", "offer_view", "order_created", "paid", "sale"):
        assert f"'{event}'" in sql
    for column in ("comments", "subscriber_delta", "clicks", "leads", "orders", "sales", "revenue"):
        assert f"add column if not exists {column}" in sql
    assert "campaign_token text" in sql
    assert "idx_content_os_funnel_source" in sql
