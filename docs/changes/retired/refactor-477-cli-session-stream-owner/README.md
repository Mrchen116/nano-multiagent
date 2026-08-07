# Retired

- Retired: 2026-08-07
- Reason: The current `Kernel.stream()` contract intentionally supports independent history-replaying fan-out subscribers. The CLI's foreground and background consumers therefore are not competing readers, and no current loss or duplication incident justifies the proposed single-owner rewrite.
- Revisit: Create a new bugfix only if duplicate output, lost background notifications, or subscriber overflow is observed in a real CLI session.
