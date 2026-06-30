# CLI delta-spec: Ctrl-C during active runs

This delta applies to `docs/specs/cli/spec.md`.

## Added Requirement: Interactive Ctrl-C Interrupt

In the interactive Coding CLI REPL:

- Pressing Ctrl-C while no assistant run is active keeps the existing idle behavior.
- Pressing Ctrl-C while an assistant run is active calls the kernel interrupt API for the current session.
- The CLI prints the existing interruption notice and keeps the REPL usable in the same session.
- If the interrupted run is executing `web_fetch`, the run must close with user-interrupt attribution instead of waiting for HTTP or prompt processing to finish.
- The recovered tool result content for user-interrupted tool use must be exactly:
  `[Request interrupted by user for tool use]`
- A later user message in the same REPL session must not include late output from the interrupted `web_fetch`.

