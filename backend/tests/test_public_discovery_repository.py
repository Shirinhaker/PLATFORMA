from app.public_discovery.repository import (
    build_public_id,
    build_public_search_statements,
)
from app.public_discovery.schemas import PublicResultKind, PublicSearchParams


def compile_sql(statement) -> str:
    return " ".join(
        str(statement.compile(compile_kwargs={"literal_binds": True})).split()
    ).lower()


def test_public_id_is_stable_and_does_not_reveal_the_database_id():
    first = build_public_id(PublicResultKind.USER, 42)
    second = build_public_id(PublicResultKind.USER, 42)
    business = build_public_id(PublicResultKind.BUSINESS, 42)

    assert first == second
    assert first != business
    assert first.startswith("u_")
    assert "42" not in first


def test_public_search_query_selects_only_the_public_projection():
    data_statement, count_statement = build_public_search_statements(
        PublicSearchParams(q="savdo", page=2, page_size=10)
    )

    data_sql = compile_sql(data_statement)
    count_sql = compile_sql(count_statement)

    assert "user_profiles" in data_sql
    assert "business_profiles" in data_sql
    assert "accounts.status = 'active'" in data_sql
    assert "limit 10 offset 10" in data_sql
    assert "order by lower" in data_sql
    assert "count(" in count_sql

    for private_column in (
        "password_hash",
        "telegram_user_id",
        "phone",
        "pay_card",
        "tax_id",
        "director",
        "avatar_object_key",
        "logo_object_key",
    ):
        assert private_column not in data_sql

    assert "user_profiles.latitude" not in data_sql
    assert "user_profiles.longitude" not in data_sql
    public_map_gate = (
        "case when (business_profiles.map_visible is true and "
        "business_profiles.latitude is not null and "
        "business_profiles.longitude is not null)"
    )
    assert f"{public_map_gate} then business_profiles.latitude end " in data_sql
    assert f"{public_map_gate} then business_profiles.longitude end " in data_sql


def test_business_only_search_excludes_user_profile_table():
    data_statement, _ = build_public_search_statements(
        PublicSearchParams(
            result_type="business",
            direction="savdo",
        )
    )

    sql = compile_sql(data_statement)

    assert "business_profiles" in sql
    assert "user_profiles" not in sql


def test_all_search_keeps_profiles_and_adds_content():
    data, _ = build_public_search_statements(
        PublicSearchParams(q="mebel", result_type="all")
    )
    sql = compile_sql(data)

    assert "user_profiles" in sql
    assert "business_profiles" in sql
    assert "catalog_items" in sql
    assert "review_state" in sql


def test_product_search_joins_public_business_map_projection():
    data, _ = build_public_search_statements(
        PublicSearchParams(q="mebel", result_type="product")
    )
    sql = compile_sql(data)

    assert "catalog_items" in sql
    assert "catalog_items.kind = 'product'" in sql
    assert "user_profiles" not in sql
    assert "business_profiles" in sql
    assert "business_profiles.map_visible" in sql
    assert "business_profiles.latitude" in sql
    assert "business_profiles.longitude" in sql


def test_content_search_can_be_disabled_without_removing_profiles():
    data, _ = build_public_search_statements(
        PublicSearchParams(result_type="all"),
        include_content=False,
    )
    sql = compile_sql(data)

    assert "user_profiles" in sql
    assert "business_profiles" in sql
    assert "catalog_items" not in sql


def test_district_search_keeps_v7_rows_whose_region_was_not_backfilled():
    data, _ = build_public_search_statements(
        PublicSearchParams(
            q="mebel",
            result_type="user",
            region="Surxondaryo viloyati",
            district="Qumqo'rg'on",
        )
    )
    sql = compile_sql(data)

    assert "coalesce(trim(user_profiles.region), '') = ''" in sql
    assert "coalesce(trim(user_profiles.district), '') = ''" not in sql
    assert "lower(user_profiles.district)" in sql
