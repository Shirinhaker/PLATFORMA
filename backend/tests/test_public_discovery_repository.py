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
        "latitude",
        "longitude",
        "pay_card",
        "tax_id",
        "director",
        "avatar_object_key",
        "logo_object_key",
    ):
        assert private_column not in data_sql


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
