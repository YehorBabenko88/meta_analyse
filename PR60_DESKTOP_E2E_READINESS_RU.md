# PR #60 — Desktop & Bybit E2E readiness, независимая проверка

**Вердикт: synthetic CI SUCCESS; physical Bybit→PostgreSQL→Desktop NO-GO.**

## Exact source and CI

База аудита — Draft PR #60, commit `0cc8c44d57514de6808fbbb6fdc7b9d9fd20ce30`, tree `a85846d46df6e95f3d757e25399d991ee1db872b` (проверить Git tree независимо при квалификации). Hosted runs:
- [CI 40399605883](https://github.com/YehorBabenko88/meta_analyse/actions/runs/40399605883) SUCCESS.
- [ADMINIT synthetic 40399605857](https://github.com/YehorBabenko88/meta_analyse/actions/runs/40399605857) SUCCESS.
- [Public JUnit privacy 40399605895](https://github.com/YehorBabenko88/meta_analyse/actions/runs/40399605895) SUCCESS.
- [Native SCM synthetic 40399605937](https://github.com/YehorBabenko88/meta_analyse/actions/runs/40399605937) SUCCESS.
- [Kernel identity offline 40399605833](https://github.com/YehorBabenko88/meta_analyse/actions/runs/40399605833) SUCCESS.

Новый независимый Draft PR с offline admission tests должен получить отдельный exact-HEAD CI; его PASS пока не подтверждён.

## Фактический UI benchmark

`scripts/benchmark_flow_ui.py` использует PySide6 offscreen/windows, 20 синтетических инструментов, состояние `connecting`, `trusted=False` и качество `UNVERIFIED`. Запись в PostgreSQL, сеть Bybit, приватные API и торговые операции исключены. Реальные Qt signals и repaint callbacks используются, но `render_fps` вычисляется как число измеренных repaint callbacks / wall time; это **не доказательство частоты реального экрана**. `tracemalloc` измеряет пик Python heap, а не RSS всего процесса.

Производитель исполняется в worker event loop, нагрузка создаётся вызовами `_flow_execution`, результат передаётся в Qt. Учитываются publication/receive/repaint, 20-row delivery, snapshot→render p95, heartbeat, CPU одного ядра, ошибки worker/UI, отсутствие thread violations и незавершённый shutdown. Отдельный supervisor ограничивает дочерний процесс `seconds+15`, а timeout публикует только FAIL_CLOSED/UNAVAILABLE. Внутренний watchdog и cleanup не доказывают bounded shutdown при произвольном зависании native SQL.

`scripts/project_ui_benchmark.py` проверяет типы, finite/nonnegative numbers, фиксированную схему, разрешённые reasons, отсутствие NaN/Infinity, целостность source/artifact SHA256, отсутствие render samples и нулевые error counters. **Но** при PASS не требуется минимальная частота кадров, минимальное число repaint samples, максимальный p95 latency/heartbeat или лимиты RSS/disk. Например, один корректный repaint за длительное окно теоретически может пройти admission при остальных выполненных условиях. Это подтверждённый P1 пробел качества benchmark, не доказанный ложный PASS конкретного Actions.

## P0/P1/P2

| Приоритет | Риск | Доказательство / дальнейшее действие |
|---|---|---|
| P0 | Synthetic PASS ошибочно трактуется как physical E2E | Добавлен отдельный `check_ui_e2e_acceptance.py`: без public feed, PostgreSQL commit/readback, Qt freshness, resources и exact SHA всегда BLOCKED |
| P1 | Нет измеримого FPS/latency admission threshold | Определить workload-specific минимальные samples/FPS и максимальные p95 на реальных offscreen Windows/Linux; добавить в projection после baseline и negative RED |
| P1 | Python heap ≠ RSS; CPU process ≠ CPU/RAM/disk budget | Добавить независимые OS counters с fail-closed при недоступности |
| P1 | Snapshot→render timestamp не равен exchange→UI latency | Внести exchange timestamp, epoch, queue occupancy, DB commit/readback и UI frame latency в единый witness |
| P1 | Bounded WebSocket max_queue не доказывает detection dropped updates | Real slow consumer + queue overflow→INVALID→reconnect→fresh snapshot fault-injection |
| P1 | Forced kill/PG rollback/checkpoint не проверены этим benchmark | Disposable PG18 crash/rollback witness и shutdown ownership |
| P2 | Offscreen Qt не подтверждает GPU/compositor latency | Реальный desktop witness только после G1/G2 |
| P2 | Renderer partial/full comparison зависит от среды | Хранить hardware/Qt/platform/workload/provenance, сравнивать только эквивалентные среды |

## Архитектура и cross-component contracts

Bybit public REST/WS → validated orderbook/trades → collector → PostgreSQL commit → read-only DesktopService DTO → Qt signal → repaint. Snapshot должен принадлежать текущему connection epoch; delta до snapshot, duplicate, sequence regression, malformed и stale данные не могут стать VERIFIED. Market telemetry обновляется только после успешного DB write. Archive receipt/checkpoint требует атомарности и crash-restart witness. Никаких trading credentials, private endpoints или order placement.

## G2–G5 runbook (не запускать до отдельного допуска)

| Этап | Preconditions | PASS | FAIL / STOP | Evidence и rollback |
|---|---|---|---|---|
| G2 smoke | G0/G1, exact SHA/tree, disposable PG18, public-only Bybit, no keys | 100% symbols fresh snapshot, 0 false VALID, commit/readback, UI responsive, health CURRENT только после verified | Любая торговая операция, stale CURRENT, потеря записи, неизвестный SHA | Epoch/u/seq, PG receipts, Qt p95, source/run/attempt/job SHA; stop producer, drain writes |
| G3 30m | G2 PASS, отдельный допуск | 0 false VERIFIED; 0 unexplained DB gaps; p95 UI <100ms как предварительный порог; RSS/CPU/disk/queue recorded | OOM, queue overflow без invalidation, freeze, SQL mismatch | 30m resource series, evidence hashes, graceful shutdown |
| G4 2h | G3 PASS, отдельный допуск | reconnect требует fresh snapshot, bounded memory/queue, 0 orphan writes | reconnect loop, unbounded resources, shutdown incomplete | 2h metrics, rollback/checkpoint witness, operator sign-off |
| G5 24h | G4 PASS, отдельный допуск | stable resources, retention/restart, 0 integrity mismatch, disk headroom | disk pressure, leaks, stale VERIFIED | 24h metrics, retention and restart receipts |

Перед G2 нужно закрепить конкретные лимиты CPU/RSS/queue/disk для ADMINIT и методику измерения; отсутствующие метрики = BLOCKED. Ни один synthetic benchmark не выдаёт G2–G5 PASS.

**Не выполнялись:** live Bybit, физический ADMINIT, G1–G5, production PostgreSQL, deployment, merge, торговые операции.


## Дополнительный P1 — неподтверждённые boolean witnesses

В независимом admission-классификаторе обнаружен обход: пять аргументов `*_verified=True` ранее позволяли вернуть `E2E_EVIDENCE_COMPLETE` без фактических файлов доказательств. Это не подтверждение существования физического E2E. Исправлено fail-closed: до реализации верификатора source-bound PostgreSQL/Bybit/Qt/resource receipts классификатор возвращает `BLOCKED`, даже если все пять флагов истинны. Добавлены два negative regression tests. Для будущего допуска нужен отдельный парсер с exact source SHA/tree, JUnit, digest каждого witness, source timestamps и сверкой с реальным состоянием, а не доверие к булевым флагам.
