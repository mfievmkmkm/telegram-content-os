from content_os.product_model import Asset, AssetKind, Campaign, ContentItem, Project, ProjectKind, ShortJob


def test_product_entities_link_without_ui_dependency():
    project = Project("gifts", "Gifts Intelligence", ProjectKind.GIFTS)
    campaign = Campaign("cmp1", project.key, "gifts_access")
    content = ContentItem("c1", project.key, "Редкая модель", "post", campaign_id=campaign.id)
    asset = Asset("a1", content.id, AssetKind.CARD, "memory://card")
    job = ShortJob("s1", content.id)
    assert content.project_key == project.key
    assert asset.content_id == content.id
    assert job.content_id == content.id
    assert campaign.id == content.campaign_id
