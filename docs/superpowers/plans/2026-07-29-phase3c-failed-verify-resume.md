# Phase 3C Failed Verify Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Failed Phase 3C verify runini shu run ID bilan faqat media va verify bosqichlaridan xavfsiz davom ettirish.

**Architecture:** `MigrationRunner` running oldingi statusini o‘zgartirishdan avval resume stage’larini hisoblaydi. `failed + verify` holati `STAGES[-2:]`ga map qilinadi; boshqa resume va idempotency oqimlari o‘zgarmaydi.

**Tech Stack:** Python 3.12, pytest, asyncio, SQLAlchemy, GitHub Actions.

## Global Constraints

- Production bazasi va eski `web` monolitiga yozilmaydi.
- Mavjud `migration_run_id` saqlanadi.
- Akkaunt, biznes, katalog, listing va reklama bosqichlari qayta ishlamaydi.
- Failed resume boshlanishida eski `finished_at` tozalanadi.
- Failed idempotency verify markerini saqlaydi va first-pass counterlarini
  o‘zgartirmaydi.
- TDD RED → GREEN tartibi majburiy.
- Tuzatish faqat runner va uning regression testiga tegadi.

---

### Task 1: Failed Verify Resume

**Files:**

- Modify: `backend/tests/test_legacy_migration_runner.py`
- Modify: `backend/app/legacy_migration/runner.py`

**Interfaces:**

- Consumes: `MigrationRun.stage`, `MigrationRun.status`, `STAGES`.
- Produces: `_remaining_stages(run)` uchun `failed + verify -> media, verify` xatti-harakati.

- [ ] **Step 1: Write the failing regression test**

```python
@pytest.mark.asyncio
async def test_failed_verify_run_resumes_from_media_with_same_run_id(tmp_path):
    info = snapshot(tmp_path)
    run = migration_run(info)
    run.stage = MigrationStage.VERIFY
    run.status = MigrationStatus.FAILED
    run.finished_at = datetime.now(UTC)
    run.counters_json = {
        "catalog": {"created": 3},
        "media": {"created": 0},
        "verify": {"passed": False},
    }
    calls = []

    async def load_or_create(snapshot_info, environment, approval):
        return run

    async def save(value):
        return value

    def handler(stage):
        async def execute(snapshot_info, value):
            calls.append(stage.value)
            if stage is MigrationStage.VERIFY:
                return VerificationReport(passed=True, gates=[])
            return {"created": 0, "reused": 2}

        return execute

    runner = MigrationRunner(
        load_or_create=load_or_create,
        save=save,
        stage_handlers={
            MigrationStage.MEDIA: handler(MigrationStage.MEDIA),
            MigrationStage.VERIFY: handler(MigrationStage.VERIFY),
        },
    )

    resumed = await runner.run(info, "staging")

    assert resumed.id == 1
    assert calls == ["media", "verify"]
    assert resumed.status is MigrationStatus.COMPLETED
    assert resumed.counters_json["catalog"] == {"created": 3}
    assert resumed.counters_json["media"] == {"created": 0, "reused": 2}
    assert resumed.counters_json["verify"]["passed"] is True
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
cd backend
.venv/bin/pytest \
  tests/test_legacy_migration_runner.py::test_failed_verify_run_resumes_from_media_with_same_run_id \
  -q
```

Expected: FAIL because `calls` is empty.

- [ ] **Step 3: Implement the minimal resume rule**

In `MigrationRunner.run()`, calculate `definitions` before setting
`run.status = MigrationStatus.RUNNING`.

In `_remaining_stages()` add:

```python
if (
    run.status is MigrationStatus.FAILED
    and run.stage is MigrationStage.VERIFY
):
    return STAGES[-2:]
```

Failed resume boshlanishida `finished_at=None` qiling. Idempotency
verify markerini faqat `passed=True` bo‘lganda o‘chiring.

- [ ] **Step 4: Run focused tests to verify GREEN**

```bash
cd backend
.venv/bin/pytest tests/test_legacy_migration_runner.py -q
```

Expected: `7 passed`.

Qo‘shimcha regressionlarda failed resume timestampi va failed
idempotency verify’dan keyingi counter provenance tekshiriladi.

- [ ] **Step 5: Run full verification**

```bash
cd backend
.venv/bin/pytest -q
cd ..
python scripts/verify_phase3c.py
```

Expected: backend and Phase 3C gate PASS with zero failures.

- [ ] **Step 6: Commit the isolated change**

```bash
git add \
  backend/app/legacy_migration/runner.py \
  backend/tests/test_legacy_migration_runner.py \
  docs/superpowers/specs/2026-07-29-phase3c-failed-verify-resume-design.md \
  docs/superpowers/plans/2026-07-29-phase3c-failed-verify-resume.md
git commit -m "fix: resume failed Phase 3C verification"
```
