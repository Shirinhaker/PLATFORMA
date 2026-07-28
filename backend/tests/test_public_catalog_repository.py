from app.catalog.repository import (
    build_catalog_statements,
    build_content_public_id,
)
from app.catalog.schemas import PublicCatalogParams


def compile_sql(statement) -> str:
    return " ".join(
        str(statement.compile(compile_kwargs={"literal_binds": True})).split()
    ).lower()


def test_content_public_id_is_stable_opaque_and_kind_specific():
    product = build_content_public_id("product", 42)
    service = build_content_public_id("service", 42)

    assert product == build_content_public_id("product", 42)
    assert product.startswith("p_")
    assert service.startswith("s_")
    assert product != service
    assert "42" not in product


def test_catalog_query_excludes_inactive_and_review_required_rows():
    data, count = build_catalog_statements(
        PublicCatalogParams(
            kind="product",
            q="mebel",
            district="Qumqo‘rg‘on",
            page=2,
            page_size=10,
        )
    )
    sql = compile_sql(data)

    assert "catalog_items.status = 'active'" in sql
    assert "catalog_items.review_state = 'ready'" in sql
    assert "catalog_items.kind = 'product'" in sql
    assert "limit 10 offset 10" in sql
    assert "order by lower" in sql
    assert "count(" in compile_sql(count)

    for private in (
        "password_hash",
        "telegram_user_id",
        "phone",
        "pay_card",
        "tax_id",
        "director",
    ):
        assert private not in sql

