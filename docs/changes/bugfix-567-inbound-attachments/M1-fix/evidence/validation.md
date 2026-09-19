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
