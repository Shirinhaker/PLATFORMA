# Legacy v1656 active-source removal

Date: 2026-08-13 20:07:34 +05:00

Archive reference preserved:
- rchive/legacy-v1656-production-cutover

Active branch removal scope:
- root FastAPI/SQLite monolith runtime
- old monolith admin UI
- old static/index.html
- old root test suite
- old Railway monolith startup configuration
- completed cutover/helper scripts
- backend tests whose only purpose was reading active v1656 root artefacts

Preserved:
- modular ackend/
- modular rontend/
- PostgreSQL/Alembic migrations
- Redis/outbox worker
- infra/
- compose.yaml
- historical docs/
- archive branch

Backend legacy-bound tests removed by content scan: 6