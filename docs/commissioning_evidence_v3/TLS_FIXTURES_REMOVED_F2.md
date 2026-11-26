# TLS loopback fixture material removed from the tree (F2, unified-system#156)

Дата: 2026-11-25. Ветка: `claude/f2-tls-keys-20261125`, база `b1a4d6a41054f0040a88dc80b585380fb6b4f323`.

## Что удалено из рабочего дерева

Из `docs/commissioning_evidence_v3/tls-loopback/` удалены 11 файлов: тестовые приватные
ключи, сертификаты, CSR и serial одноразового loopback CA. CA создан 2026-10-20,
срок действия 2 дня (`-days 2`), к 2026-10-22 истёк. Ключи не использовались ни одним
тестом, модулем `src/`, скриптом CI или инсталлятором. Единственный потребитель —
исторический скрипт `tls-loopback/audit.py`. Он сам генерирует свежие ключи через
`openssl` при каждом запуске и сохранённые файлы не читает.

История не переписывалась. Байты остаются доступны в неизменяемом коммите
`b1a4d6a41054f0040a88dc80b585380fb6b4f323` и в его предках. Первый раз они появились
в `b10cb5e2b8c41c2472e08d5248742cedc05817e9`. Поэтому `EVIDENCE_HASHES.json`
(candidate `446c72bd97cacc31f9937c9ab941d11539733be4`) не меняется: это неизменяемая
историческая запись. Её можно проверить так:

```
git show b1a4d6a41054f0040a88dc80b585380fb6b4f323:docs/commissioning_evidence_v3/tls-loopback/<file> | sha256sum
```

| файл | sha256 (совпадает с EVIDENCE_HASHES.json) | git blob в b1a4d6a |
|---|---|---|
| ca.key | 318a10f4d5d16b6581aef2382b2d764eb2e35b462f1cddffe9c0b8b485a6e139 | e6a2a225a163b74eedbe3a60858822ddfce6866a |
| ca.pem | 87c2f60a8847c1d6099ac7913419ff012cfbb1d90e8a953b4a8027215e891a9f | 97c036efa589038f6588987c2efb551671af93ca |
| ca.srl | daeb6cfdb2f01ae531271499a4f4b9a615dd89deba864820bd3266fe6faaca2a | fdb70f4ad4a851c554a50af46d929a03314f7469 |
| good.csr | 83b098a4a56c46470c4f56e5eb01500bcf49328065d21f5c752b3863522b16ac | 893d953978289658a99272738d0299ea46ba6f44 |
| good.key | 6d759dda7e789da996a270476e1b5fce2c859f3d71a41c057fa9227c770d082c | ad2f5c5145e3d01d83ea996b4740d564447e6c5f |
| good.pem | b5f3a168f20656755fcb88ab7b983aa3d74380721142f1a040ba59d2cb4b0200 | 98657042e92f179df5dd580030d864500229f1ad |
| self.key | 88e556dc12a689772eeacdd9a598193178917eac089205537d3b39c98e647b1c | 8610511efbcc03b5a942b498ccf712dd0096813a |
| self.pem | 1aada387aab2698ad26616c4338be70439055cf4698f37a44c9986dcd89fc6b4 | 20efda2d469eba10f8f79165079121e299dab0cd |
| wrong.csr | aacc546f6780566ecf2dc9996605f4f26c98e22371feec7dfb4c34836f9d8497 | 77ab17579cafb633106e2e4d051ba9ba8227f726 |
| wrong.key | 7d8fb5cd023b35ec54df7e93d8ec1c66c7a251bc2a7276d33802000a99c6d1cc | 05d3bc39ab1d81d8ac233ff722d89d55b7145821 |
| wrong.pem | 90340424dbc667cff2628321052f0961e3562bf23218ae53e71ec34006ad3099 | 61b16a920cd3b60689d37c5aadcf6594171a7658 |

В дереве оставлены логи (`results*.log`, `abort*.log`, `openssl.log`), скрипты
(`audit.py`, `abort.py`) и `*.ext`. Приватных данных в них нет.

## Почему ключи не попадут в поставку

1. Wheel содержит только пакеты из `src/` (`[tool.setuptools.packages.find] where = ["src"]`),
   а `[tool.setuptools.exclude-package-data]` явно исключает `*.key`, `*.pem`, `*.p12`,
   `*.pfx`, `*.csr`, `*.srl`, `*.der`, `*.crt`, `*.cer`, `*.jks` и `*.keystore`.
2. `MANIFEST.in` выполняет `prune docs` и `global-exclude` по тем же суффиксам для sdist.
3. `install.ps1` ставит пакет через `pip install -e` из checkout'а и файлы репозитория
   не копирует. После этого изменения в checkout'е нет ключевого материала.
4. `.gitignore` запрещает `*.key`, `*.p12`, `*.pfx` и `*.srl`. Если `audit.py`
   перезапустят, сгенерированные ключи останутся неотслеживаемыми.
5. `scripts/check_no_private_key_material.py`:
   - `--git-tree .` проверяет все отслеживаемые файлы по суффиксу и по PEM-заголовкам;
   - `--dist DIR --require-wheel --require-sdist` проверяет каждый член собранных wheel
     и sdist.
   Linux-job в `ci.yml` собирает wheel и sdist из `git archive HEAD` в отдельном venv и
   запускает обе проверки. Тест `tests/test_no_private_key_material.py` падает, если
   ключевой материал есть в отслеживаемом дереве, в `src/` или в синтетически собранном
   архиве (проверка детектора), а также если пропадает любое из исключений выше.

Тестам, которым нужен TLS, сертификаты следует генерировать во время выполнения во
временном каталоге (`tmp_path`). Хранить ключи в репозитории нельзя.
