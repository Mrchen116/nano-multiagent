# M1 implementation

The Gateway owns message preparation, permission admission, publication receipts and recovery. The Kernel reports model-round completion and exposes a source-neutral permission operation; it no longer receives delivery results or decides image repair runs. Foreground and unattended coordinators use system-origin input and a durable two-admission repair budget.

## Test disposition

- Keep composed image/source-delete/ACK/offline and explicit/shadow integration behavior. Replace old recovery-constructor access with the actual delivery owner.
- Rewrite callback-race tests around the remaining observable risks: late running-event replay and a pending initial bubble ACK. The former test's circular wait relied on the deleted second publication entrance.
- Replace callback-specific Kernel tests with complete-round facts, real permission context, cross-loop execution and cancellation tests.
- Update standalone coordinator fan-out tests to assert delegation to the delivery owner rather than a second raw transport send. Composed background delivery integration continues to verify actual publication.
- Remove only retired output feature flags and constructor parameters; preserve original group reminder and revalidation tests.
- New-input admission, manual approval/denial/stop, complete fragmented-image buffering, feedback exhaustion and protocol silence have regression coverage at their lowest meaningful seams.

## Validation

- Kernel/SDK: 663 tests plus targeted follow-ups; details in `kernel.md`.
- Gateway owner: 80 tests and 15 composed integration tests; details in `delivery.md`.
- Independent code closure: 15 focused tests and additional composed probes passed.
- Frontend build, Ruff and documentation integrity passed. Final all-suite results and product evidence are recorded in the unit's verification/acceptance reports before delivery.

No production services or data were changed. The original PR #306 remains an unmerged draft; the replacement PR carries its product behavior plus this ownership correction.

## Background closure and broad validation

Non-group and external background replies now enter the same complete-round observer and permission admission as foreground output. The previous raw background sender and its separate preparation path are removed. Background repair runs retain the session, route, durable two-admission budget and persistent event consumer.

On the final background source tree, the broad Python run passed 3,980 tests; two external fixtures collected before their ACK correction failed, then both passed on `c2d8c1422`. These were fixture protocol mismatches, not a weakening of delivery checks. Frontend remains 770 passed (83 files), production build and critical-level dependency audit passed.

## Final permission and UI closure

Real acceptance identified two further concrete faults: permission classification represented a host ordinary reply as a model tool call, and IM rejected Bash return sidecars while preparing an approval bubble. SDK permission-only checks now accept a trusted host operation description without granting permission; Gateway projects only return-card types supported by IM.

Final broad Python run: **3,985 passed, 35 deselected** on the host-context source tree. The subsequent 13-line UI projection correction passed **19 related tests**, including **3 new strict-protocol real-Kernel/Bash/manual-approval tests**. Independent code patch reviews found no surviving issues. Frontend source was unchanged by these backend corrections, so its 770-test/build evidence remains valid.

## Delivery baseline and retention

- executed_base / effective_base: `c4ba604625001290f0191be06ae7ad741c9b4626`; origin/main has no later increment at final synchronization.
- Final source validated_at / effective_through: `d4a59af212690dfe50af77a1b689e572ad32499c`.
- Design Round 3 is Approved (0 critical / 0 warning); implementation verification Round 4 is pass with corrected-delta aligned; full code review plus all three correction patches have no surviving findings.
- After this source snapshot, only validation reports and the unit archive move change. The source gates retain validity through that documentation-only delivery commit; the PR records its final hash.
- Source tests and frontend evidence are recorded above; actual UI, external provider and offline journeys are recorded independently in acceptance.md.
