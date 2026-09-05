from content_os.growth.recommendations import recommend, recommendation_pack


def rows(count=5):
    data=[]
    for _ in range(count):
        data.append({"project":"gifts","hook_type":"conflict","format":"post","visual_type":"card","publish_hour":"17","offer":"access","engagement_rate":.18,"conversion_rate":.04})
        data.append({"project":"gifts","hook_type":"question","format":"meme","visual_type":"meme","publish_hour":"11","offer":"none","engagement_rate":.08,"conversion_rate":.01})
    return data


def test_recommendation_requires_real_sample_floor():
    assert recommend(rows(2), "gifts", "hook_type", "engagement_rate") is None


def test_recommendation_is_descriptive_not_autonomous():
    item=recommend(rows(6), "gifts", "hook_type", "engagement_rate")
    assert item is not None
    assert item.value == "conflict"
    assert "корреляция" in item.reason.lower()
    assert item.action.startswith("Протестировать")


def test_pack_can_cover_content_and_sales_dimensions():
    pack=recommendation_pack(rows(12), "gifts")
    dimensions={item.dimension for item in pack}
    assert {"hook_type","format","visual_type","publish_hour","offer"}.issubset(dimensions)
