# Retired

- Retired: 2026-08-07
- Reason: The kernel now owns per-skill queueing, deduplication, and settlement. CLI and Gateway only supply their distinct event-loop and workspace scheduling adapters, which is a real product seam rather than duplicate lifecycle ownership.
- Revisit: Create a new unit only for an observed cross-product review scheduling or workspace-isolation failure.
