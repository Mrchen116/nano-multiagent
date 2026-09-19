# Implementation validation

## Red / Green

- Baseline: c5f1d5620 (product code same as 09cd75bd5).
- Red command: `PYTHONPATH=src python -m pytest -q tests/unit/personal_assistant/test_gateway_image_inbound.py tests/unit/personal_assistant/test_group_context_admission.py --tb=short`.
- Red result: 10 failed, 10 passed. Ordinary-file matrix produced image errors; history bad image blocked submit; image/submit rejection lost buffered text; rejected steer prematurely removed history before later accepted steer.
- Green: same command, 20 passed.
- Broader focused command: `PYTHONPATH=src python -m pytest -q tests/unit/personal_assistant/test_session_run_coordinator_admission.py tests/unit/personal_assistant/test_group_context_store.py tests/unit/personal_assistant/test_image_attachment_resolver.py tests/unit/personal_assistant/test_gateway_image_inbound.py tests/unit/personal_assistant/test_group_context_admission.py tests/unit/personal_assistant/test_inbound_attachment_types.py tests/integration/test_global_gateway_runtime.py --tb=short`.
- Result: 70 passed, 5.01s, 2026-09-19. Code/test tree committed with this evidence; this is automated seam validation, not product acceptance.

## Existing test disposition

Image download/size/corruption, Feishu order and global Inbox commit tests kept. The group steer test now asserts accepted input preservation rather than resolver call count, since group FIFO deliberately refreshes unconsumed snapshots. Lock-capacity test uses actual image descriptors to gate asynchronous resolution instead of relying on a resolver call for empty attachments. Global real-kernel test parameterized with mixed file/image input. New classification test owns shared descriptor contract; new group admission file owns buffer loss/duplication at public dispatch seam, avoiding extending the existing >400-line admission file with independent behavior.

## Review corrections

- Static R1: two confirmed gaps. Historical oversize inline image produced 6,990,658 characters of model text (red public-pipeline test); failed source descriptions now omit data URL payloads. Global Feishu indexed image was absent from actual model tool content (red integration); global now resolves indices, preserves provider text/image order and includes the actual image block.
- Correction command: `PYTHONPATH=src python -m pytest -q tests/unit/personal_assistant/test_gateway_image_inbound.py tests/unit/personal_assistant/test_recovery_handoff_concurrency.py tests/integration/test_global_gateway_runtime.py --tb=short` → 22 passed, 6.07s. Test code reads actual LLMMessage content image blocks rather than checking an image string only.
- Full initial PA shard: 1963 passed / 1 failed. The remaining recovery concurrency fixture depended on empty-attachment resolver calls; it now supplies an actual image descriptor to the gating seam, retaining its recovery/terminal assertions. Narrow rerun: 1 passed.
- Full remaining Python shard: 2044 passed, 27 warnings, 174.06s (log `/tmp/bugfix567-tests-rest.log` during this run).
- Frontend initial run: 769 passed / 1 timeout in unchanged agent-detail-page skills usage test (5s limit) while Python suites were concurrent. No frontend diff. Targeted file: 20 passed in 4.98s. Full rerun performed separately, result recorded below. This is timing sensitivity evidence, not a proven root cause.
- Ruff check/format and documentation integrity passed with repository venv. Initial docs-check used system Python lacking yaml; rerun with venv PATH passed (238 maintained Markdown, 73 routes).

## Final local checks at 800f4dfe3

- PA/agent shard: 1965 passed in 29.57s, `/tmp/bugfix567-tests-pa-final.log`.
- Remaining shard retained except changed global integration already rerun: 2044 passed; correction integration included in 22 passed.
- Frontend full rerun: 83 files / 770 tests passed in 61.61s; `/tmp/bugfix567-frontend-rerun.log`. No frontend modifications; initial isolated timeout did not reproduce in targeted or full reruns.
- Static R2: both findings closed, code review `[]`, corrected delta aligned; independent correction suite 22 passed.
- Product R2 remains FAIL due to external LLM_PROXY nested tool-image loss. See regression.md and evidence/proxy-image-boundary.md. Unit stays active; no archive/Ready PR before product gate closes. Cross-repository scope clarification requested from user.
