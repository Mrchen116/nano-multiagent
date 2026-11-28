import type { DesktopUpdaterSnapshot } from "@nano/product-contracts/desktop-local";

export function makeSnapshot(overrides: Partial<DesktopUpdaterSnapshot> = {}): DesktopUpdaterSnapshot {
  return {
    platform: "darwin-arm64",
    current_version: "1.3.2",
    auto_update: true,
    phase: "up_to_date",
    mode: null,
    target: null,
    progress: null,
    active_tasks: 0,
    last_checked_at: "2026-04-20T08:00:00.000Z",
    just_updated_version: null,
    capsule_dismissed: false,
    active_ui_sha256: "a".repeat(64),
    reload_generation: 1,
    error_code: null,
    ...overrides,
  };
}
