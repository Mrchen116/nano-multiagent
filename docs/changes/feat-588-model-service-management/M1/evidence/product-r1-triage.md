# Product R1 triage

## Built-in provider identity

The independent product reviewer observed that a renamed built-in DeepSeek service showed its user-defined name in the vendor label and provider selector after restarting the node. After deleting that service, the cached add-service catalog still used the custom name, obscuring the built-in provider identity.

Root cause: `providerProfiles` copied the product service label into the native DSH profile's `displayName`. The public configurable-provider directory legitimately exposes that configured profile name. Node caches its catalog, so the first startup before configuration and the next cold startup showed different identities. Product labels already have their own YAML/status/capability fields; native DSH profiles do not need that override. The fix removes only the native profile override and retains the custom service label in the product projection.

A real DSH cold-initialization regression in `apps/node/tests/providers.test.ts` first read the empty-profile catalog, then initialized the renamed built-in service and read it again. Before the fix it failed with expected `deepseek`, received `My Research API` (`/tmp/nano588-catalog-red.log`). After the fix, provider, model-setup, capability and integration setup tests passed: 4 files / 11 tests (`/tmp/nano588-catalog-green.log`). Independent targeted browser revalidation is recorded in the acceptance report.

## Replies followed by a failed run

The reviewer observed real replies `43` and `47`, followed by a failed status on the corresponding user messages after refresh. Read-only inspection of the isolated IM database and DSH event projection distinguishes the published reply from the later whole-run result:

- First reply was created at `2026-10-13T03:58:22.522Z`; DSH turn 1 ended at `03:59:01.874Z` with `reason.kind=error`.
- Second reply was created at `04:01:39.494Z`; turn 2 ended at `04:02:23.192Z` with the same error.
- Both terminal errors were HTTP 502 `upstream_empty_stream`: the upstream reported success without text or tool calls during a subsequent model step. The IM failed receipts correspond to those actual terminal failures.
- Turns 3, 4 and 5 ended `completed`, and their message statuses remained completed, including after credential/URL rotation and model migration.

This is a real user-visible execution failure in the test upstream after a reply was published; it is not evidence that service saving changed a completed run into failure or corrupted the old connection. No receipt, delivery or agent-loop code was changed to hide it. The product report retains the observation and the explicit test-upstream boundary.
