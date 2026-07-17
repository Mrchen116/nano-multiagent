# M1 总门禁结果

执行日期：2026-07-15。

| 门禁 | 结果 |
|---|---|
| `pytest -q tests/contract/test_test_naming_and_size_contract.py` | `2 passed` |
| `ruff check src tests` | `All checks passed` |
| `pytest -m "not e2e" -q` | `3365 passed, 1 skipped, 20 deselected, 17 warnings in 140.67s` |
| `npm run test -- --runInBand` | `65 files passed, 609 tests passed` |
| `npm run test -- agent-channels-panel.test.tsx im-agent-config-api.test.ts agent-detail-page.test.tsx` | `3 files passed, 42 tests passed` |
| `npm run build` | `443 modules transformed`, build success |

Warnings are existing dependency/test-harness warnings: lark protobuf/event-loop deprecation, FastAPI status constant deprecation, short test JWT key, one pre-existing unawaited cache coroutine, React act and mocked sync console noise. No warning changed a gate result; real-browser console separately reported `0 errors / 0 warnings`.
