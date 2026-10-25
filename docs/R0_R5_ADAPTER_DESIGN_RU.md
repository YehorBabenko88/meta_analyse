# R0–R5 adapter: scope и план

Base — точный PR39 4a92643c00a7e4d113025e1df427d8f4850f0981. Отдельная ветка/Draft, без изменения #39. User-approved R0–R5 реализуется как отдельный Python entrypoint, использующий existing collect_facts и готовый assessment, не вызывающий classifier повторно. Новых native API нет.

Сначала tests red: типы, join/coverage/lifetime, PID reuse, fixed stage/error buckets, configuration subpredicates, privacy и output/source failures. Затем shared pure configuration checks с эквивалентностью исходному predicate; сам VERIFIED policy не расширяется. Adapter проверяет original/evidence/results binding, выдаёт только aggregate count dictionaries и fixed states. Source SHA/tree/clean/hash binding до и finally после collection; ошибка binding стирает summary. Git-only source acceptance; неподтверждённый packet/подпись не обходится.

Всегда FAIL_CLOSED/NONE/exit1; нет save_private, DPAPI, enrollment, G1. Existing NewOutput обеспечивает exclusive new output; late I/O failure не даёт raw fallback. Runtime rights/PowerShell policy из #39 сохраняются. Protection/architecture не собираются заново: NOT_COLLECTED. Collection/lifetime failure не считается zero/success.

Dedicated Windows/Linux Python3.12 synthetic CI, pinned dependencies и минимальный staged JUnit. Full/native/storage jobs новой ветки исключаются, PG audit/** trigger не совпадает. Требуемые hosted evidence проверяются только на final SHA; queued/skipped не PASS. После source review готовится инструкция одной отдельно разрешённой read-only попытки ADMINIT, но physical collection в разработке не выполняется.
