# M9 Fix Gateway Live Run Tasks

## Goal

Close Round 5 product acceptance feedback for the Feishu Gateway live run: a real
Lark user message to the configured Bot must keep Gateway running and must create
the external IM shadow conversation/message, or produce the configured Bot reply.

## Tasks

- [x] Reproduce with the Bot derived from the worktree Gateway config.
- [x] Confirm `lark-cli auth status --json --verify` app identity matches config.
- [x] Isolate the `POST /im/v1/conversations/external/find-or-create` 400 root cause.
- [x] Add a regression test for the external shadow owner identity boundary.
- [x] Fix Gateway shadow sync to use the authenticated IM user.
- [x] Run narrow unit coverage and full non-e2e pytest.
- [x] Prove the fix with a real Lark inbound message and IM shadow DB evidence.

