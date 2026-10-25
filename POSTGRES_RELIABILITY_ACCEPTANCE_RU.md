# POSTGRES_RELIABILITY_ACCEPTANCE_RU

Дата проверки: 2026-10-25. Независимый read-only source/CI review; не является физическим commissioning.

## Exact-source boundary

Проверен исходный HEAD PR #30: `fe9833a3aa9606b04f98f0f655916b83270dfdb3`. Эта audit-ветка создана от него; результаты предыдущего `bd36863e` не наследуются. До завершения всех workflow на точном SHA статус полного CI — PENDING. Никакие production DB или ADMINIT не проверялись.

## Проверенные source contracts

- `scripts/prepare-ci-postgres18.ps1`: отказывает вне `GITHUB_ACTIONS=true` и Windows runner, проверяет SHA256 архива PostgreSQL 18.6, фиксирует бинарную версию. Это защита disposable Windows CI, не доказательство идентичности физического кластера.
- `scripts/test-windows.ps1`: создаёт отдельный `initdb` под `RUNNER_TEMP`, loopback/случайный порт, устанавливает тестовые DSN и останавливает сервер в `finally`. Риск: порт резервируется и освобождается до старта PG (TOCTOU); `--auth=trust` допустим только в действительно изолированном runner. Проверка не заменяет аттестацию `system_identifier`, прав и ownership.
- Linux storage workflow использует disposable PostgreSQL 18.1 service. Windows full CI использует 18.6. Нельзя переносить результат 18.6 на физическую 18.1 без отдельной проверки.
- `src/meta_analyse/storage.py`: `Store.connect` задаёт connect/statement/lock timeouts, но не проверяет ожидаемые host, port, database, current_user, server_version_num, system_identifier, read_only и роль. Нужен отдельный opt-in fail-closed commissioning gate; нельзя навязывать test DSN policy всем обычным вызовам без анализа совместимости.
- `storage_migrations.py`: `IF NOT EXISTS` плюс transaction advisory schema lock, однако требуется проверка drift существующих объектов, owner и grants.
- `archive_db_import.py`: предварительная проверка snapshot/receipt, Decimal без float, `pg_advisory_lock` с 15s lock timeout и batch+checkpoint в одной транзакции. Для ошибок проверяются rollback и сохранение предыдущего checkpoint. В таблице допускается `quantity >= 0`, тогда как importer требует строго `> 0`; нужна согласованная миграционная политика, а не слепая ALTER на production.
- `write_drain.py`: `asyncio.shield` и ожидание executor task до commit/rollback при отмене. Требуется инвентаризация всех call sites и shutdown sequencing, а также fault injection при повторной отмене, ошибке commit и аварийном выходе.
- `orderflow_archive_reader.py`: read-only transaction и детерминированный порядок, но `LIMIT` не сообщает о truncation; отсутствие строк не доказывает покрытие. Историческое покрытие должно оставаться UNVERIFIED.
- Не подтверждён полноценный reconnect/resubscribe orderbook после invalidation; требуется state-machine chaos test с конечным дедлайном восстановления.

## Exact HEAD evidence, checked 2026-10-25

- PR #30 HEAD `fe9833a3...`: Storage integration run 40182611620 SUCCESS, Kernel identity offline 40182611611 SUCCESS, Public JUnit privacy synthetic 40182611664 SUCCESS.
- Main CI 40182611622 был IN_PROGRESS во время проверки. CI content security synthetic 40182611625 и CI audit synthetic 40182611639 — SKIPPED по политике; это не PASS.
- Предыдущий SHA `bd36863e...` (не текущий): Windows full 1812 passed / 0 skipped; Linux 1811 passed / 1 explicit installer skip; Storage 107 passed; archive 8 passed; lifecycle 10 x 67 на каждой платформе. Только исторический контекст.

## P0 / P1 / P2

**P0:** ADMINIT NO-GO. Нет физического DSN/cluster attestation, native process authorization, PostgreSQL ownership и отдельного согласования оператора.

**P1:** Ввести изолированный DSN attestation contract с точными ожидаемыми `system_identifier`, version, database, role, host/port и ownership; протестировать несовпадения до любой DDL/DML. Проверить shutdown drain при многократной отмене и commit/rollback failure. Устранить неопределённую orderbook recovery state. Провести disposable crash/restart тесты с checkpoint consistency.

**P2:** Проверить CSV/GZIP decompression budgets, malformed Decimal, disk-full, exhausted connections, lock timeout, duplicate imports и migration drift. Укрепить orderflow history truncation signal.

## Proposed test matrix (disposable only)

1. Negative DSN matrix: wrong host/port/database/role/version/system_identifier; deny before any mutation.
2. PG roles: read-only role cannot DDL/INSERT; importer role limited to schema; verify cleanup only for uniquely owned disposable database.
3. Advisory contention: two identical archives and distinct archives same symbol; success after release, timeout under stuck holder, no partial checkpoint.
4. Crash injection at pre-COPY, mid-COPY, pre-checkpoint, post-commit and after reconnect; verify exactly-once logical rows and consistent committed_rows.
5. Cancellation: repeated cancel during to_thread write and rollback; owner/lock survives until worker completion, no detached write after shutdown.
6. Orderbook: invalid delta, reconnect, stale snapshot, missing sequence, resubscribe and bounded UNVERIFIED interval; never promote to VERIFIED without proof.
7. Lifecycle: 10 fresh processes x 67 with exact identity manifests, zero unexpected skips, JUnit counters and SHA/tree/run/attempt custody.
8. Privacy: projected JUnit without hostname/paths/system-out; no raw PG logs or private host evidence in public artifacts.

## Future staged commissioning (not authorized here)

- **30m:** only after separate operator GO, exact source/provenance, read-only attestation, isolation/permissions, stop and rollback proof; zero trading orders.
- **2h:** only after 30m PASS; forced reconnect/cancel and bounded recovery, consistent checkpoints and stable resources.
- **24h:** only after 2h PASS; resource/leak/latency and crash-recovery monitoring with signed receipts and explicit stop conditions.

For each stage: immediately stop on unknown cluster identity, unexpected role/port, transaction inconsistency, infinite UNVERIFIED, detached executor write, data corruption or privacy leak. No automatic stage escalation.

**Final status: SOURCE REVIEW PARTIAL / DISPOSABLE CI EVIDENCE PARTIAL / NATIVE WINDOWS TARGET UNVERIFIED / PHYSICAL ADMINIT NO-GO.** No merge, deployment, production DB access or physical tests.

## Exact SHA follow-up

На source SHA `fe9833a3aa9606b04f98f0f655916b83270dfdb3` GitHub Actions завершились: CI run `40182611622` SUCCESS; Storage `40182611620` SUCCESS; Kernel offline `40182611611` SUCCESS; Public JUnit privacy `40182611664` SUCCESS. CI content security `40182611625` и CI audit synthetic `40182611639` SKIPPED по политике, не засчитываются как PASS. Эти результаты относятся к исходному SHA, а не к данному документальному audit-коммиту. Физическая готовность ADMINIT по-прежнему NO-GO.
