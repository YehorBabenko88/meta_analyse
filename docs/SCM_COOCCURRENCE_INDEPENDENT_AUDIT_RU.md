# Независимое заключение GPT-1: SCM aggregate co-occurrence, 2026-10-25

## Scope / exact base
PR #41 HEAD `5b622cc218fdf90d26164d544176dd647297fc53`, tree `210d69f19d3912013414e550da04594e6b7fd3f2`. Проверены `commissioning/native_scm_diagnostic.py`, `commissioning/process_identity.py`, тесты PR41 и отчёт R0–R5. Физический ADMINIT не запускался. Предлагаемый Codex co-occurrence adapter не был доступен как отдельный опубликованный diff на момент аудита; ниже контракт для проверки будущего кандидата, а не утверждение о его PASS.

## Строгий контракт
- Для каждого *reviewed member* вычислять ровно один из четырёх исходов: BOTH_PASS, REGISTRY_ONLY_FAIL, SCM_ONLY_FAIL, BOTH_FAIL. Счётчики должны суммироваться в число оценённых пар; NOT_EVALUATED учитывается отдельно, не как PASS.
- Registry/SCM service_type проверяются раздельно по `type(v) is int and v == 32`. Не разрешены `bool`, `float`, string, 16, 0x120, маски, неявное приведение и расширение Windows-valid type до reviewed.
- Shared-host membership: коррелировать по одному конкретному члену списка services в одном snapshot, а не по PID, host executable, суммам между фазами или общим module set. Два members в одном svchost/lsass могут дать два независимых отказа.
- Source binding: точный Git HEAD/tree и collector identity до и после read-only collection; reject dirty/mismatch, duplicated service names, inconsistent PID/creation FILETIME, malformed schema, unexpected result status.
- Adapter только projection; никакой reclassification, persistence, VERIFIED promotion, G0/G1 authorization, PPL bypass, SeDebug или fallback identity из error31.
- Privacy: фиксированные названия категорий и totals могут раскрывать редкий профиль. Не публиковать имена служб, PID, raw типы, путь, source identifiers, редкие per-member joins или последовательности; даже малые totals требуют отдельного privacy review. Не заявлять анонимность только из-за удаления имён.

## Adversarial RED/GREEN oracle
Два набора пяти members дают одинаковые marginal totals REGISTRY_FAIL=1/SCM_FAIL=1: [(16,16),32×4] и [(16,32),(32,16),32×3]. В первом BOTH_FAIL=1, во втором REGISTRY_ONLY_FAIL=1 и SCM_ONLY_FAIL=1. Любой адаптер, выводящий co-occurrence из marginal totals, должен быть отвергнут. Дополнительные тесты: exact int32, shared host, no VERIFIED/persistence, source and PID binding, rare aggregate leakage. Эти synthetic tests не заменяют native runtime witnesses.

## P0/P1/P2
- P0: подтверждённых путей к VERIFIED из PR41 adapter не найдено при source review; будущий adapter ещё не аттестован.
- P1: co-occurrence без per-member correlation / exact source binding может дать ложную диагностическую причинность. Обязательные RED/GREEN до принятия.
- P1: отсутствие независимой privacy acceptance редких co-occurrence категорий блокирует public artifact.
- P2: endpoint Win32 31 и VM_READ ACCESS_DENIED 5 не идентифицируют PPL/причину; ранняя alive projection в PR41 исправлена, но host validation отдельно BLOCKED.
- P2: aggregate не определяет точный failing service contract и не оправдывает расширение reviewed policy.

## Decision
**Q/G0 FAIL_CLOSED; G1 NO-GO.** Новые synthetic tests — независимый контрольный оракул; не включать production или физический rerun. Не менять чужой PR #41.
