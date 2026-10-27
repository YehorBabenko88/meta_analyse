# Remaining other-subject effective access — подготовка без logon/ACL change

Сейчас NOT_EVALUATED / BLOCKED. Этот документ не запускает API/UI или collector.
Current process token administrator не представляет других пользователей или
все tokens одной учётной записи. При отсутствии их корректного existing context
не генерировать synthetic SID context и не объявлять отсутствие прав.

## Допустимый план после отдельного review

1. Independent reviewer приватно фиксирует actual owner и DACL двух родителей,
   scopes/applies-to/deny/inherit-only/CREATOR OWNER/OWNER RIGHTS, а также
   memberships/privileges и известные источники изменения namespace. Snapshot
   не доказывает quiescence. Нужны отдельная threat model, управляемый writer
   scope и границы времени; не утверждать «нет hostile writers» по ACL.
2. Определяет необходимые реальные representative contexts: уже существующие
   interactive/service/domain/restricted/UAC tokens, где они реально существуют.
   Не перечислять и не открывать чужие process tokens автоматически. Нет
   подтверждённого token/group/logon scope => BLOCKED для этого субъекта.
3. Для уже разрешённой существующей консоли субъекта можно отдельно предложить
   один explicit --current-token read-only запуск reviewed tool с approved
   runtime и M/A. Создание обычного дочернего процесса с существующим token
   не требует нового logon; однако здесь такой запуск НЕ выполнен и не
   разрешается автоматически. Не выполнять RunAs/LogonUser/CreateProcessWithLogon,
   S4U, impersonation, смену privileges или ACL для получения нужного результата.
4. Reviewer отдельно authenticates, чьим actual token был получен sample, и
   связывает ROOT/PROGRAMDATA с соответствующим private source/session receipt.
   Public tool projection намеренно не раскрывает SID/TokenId; её нельзя
   использовать как самостоятельное доказательство subject identity. Не
   «подписывать» чужой JSON как факт без проверки канала и origin.
5. Проверить DeleteChild на parent, DELETE/WriteDac/WriteOwner на самом ancestor,
   права вышестоящего parent на замену child, inheritance и привилегированные
   bypass paths. Не только CreateDirectories: оно само по себе не даёт чтения
   protected child. Негативный sample одного token не доказывает отсутствия
   access у всех членов группы/всех logon types или будущих tokens.

## Что НЕ является no-logon доказательством

Не запускать AuthzInitializeContextFromSid с default flags без отдельного
approval: он может выполнять S4U или AD membership lookup и не включает все
logon-specific группы при fallback. Windows Effective Access UI также нельзя
автоматически считать no-S4U/offline способом: пока его конкретный путь не
reviewed, этот способ BLOCKED. AUTHZ_SKIP_TOKEN_GROUPS даёт неполный контекст;
он не заменяет реальные effective rights и не разрешает PASS.

## Стоп и результат

Access denied/недоступный token не оправдывает SeDebugPrivilege, PPL bypass,
новый logon, reset/grant ACL, перезапуск service или изменение Windows.
Сохранить NOT_EVALUATED, не исключать неизвестную группу ради PASS.

Сводная private matrix: subject-context reference (не public SID), existing
token provenance/group scope, tool/source/approval references, time bounds,
ROOT/PROGRAMDATA descriptor/access results, residual claims/MIC/privileges,
concurrency assumptions, PASS/FAIL/BLOCKED конкретной проверки. Не выдавать
общий G0 PASS из отдельных negative rights. Raw rights combinations тоже могут
fingerprint host; держать локально до privacy review.

Даже полное совпадение measurement не доказывает anti-TOCTOU или quiescence.
Namespace creation остаётся отдельным gate; G0 FAIL_CLOSED / NONE, G1 NO-GO.

[Microsoft: SID context может использовать S4U и пропускать logon groups](https://learn.microsoft.com/en-us/windows/win32/api/authz/nf-authz-authzinitializecontextfromsid).
