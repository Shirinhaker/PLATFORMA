from app.catalog.schemas import PublicCatalogItem


def test_unlinked_catalog_card_disables_owner_actions():
    item = PublicCatalogItem(
        kind="product",
        public_id="p_abc",
        name="Mebel",
        price_text="Kelishiladi",
        owner_state="unlinked",
        owner_label="Egasi hali akkauntini bog‘lamagan",
        can_order=False,
        can_chat=False,
    )
    payload = item.model_dump()

    assert payload["owner_state"] == "unlinked"
    assert payload["can_order"] is False
    assert payload["can_chat"] is False
    assert payload["unit"] == "dona"
    assert "business_account_id" not in payload
    assert "image_object_key" not in payload
    assert "legacy_id" not in payload
