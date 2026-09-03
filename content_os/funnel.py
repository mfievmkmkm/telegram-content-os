from collections import Counter


def summarize_funnel(events):
    kinds=Counter(str(row["event_type"]) for row in events)
    sources=Counter(str(row["source"] or "direct") for row in events if row["event_type"]=="landing")
    offers=Counter(str(row["offer_key"] or "unknown") for row in events if row["event_type"]=="order_created")
    landings=kinds["landing"]; orders=kinds["order_created"]
    return {"landings":landings,"offer_views":kinds["offer_view"],"orders":orders,
            "conversion":round(orders/landings*100,1) if landings else 0,"sources":sources,"offers":offers}
