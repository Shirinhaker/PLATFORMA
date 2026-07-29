from app.legacy_migration import cli as base_cli
from app.legacy_migration.runner_v6 import build_database_runner


base_cli.build_database_runner = build_database_runner


def main() -> None:
    base_cli.main()
