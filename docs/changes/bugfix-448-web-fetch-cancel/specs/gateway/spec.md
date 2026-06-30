# Gateway delta-spec: stop during web_fetch

This delta applies to `docs/specs/gateway/spec.md`.

## Modified Requirement: `/stop` Interrupts Active Tool Runs

When a user sends `/stop` while the bound kernel session has an active run:

- Gateway continues to call the kernel interrupt API for that session.
- Gateway immediately acknowledges the command with the existing stop confirmation text.
- If the active run is executing `web_fetch`, the resulting tool call must be reconciled as interrupted rather than left running until HTTP or prompt processing finishes.
- The interrupted tool call content surfaced through Gateway must include exactly:
  `[Request interrupted by user for tool use]`
- After the interrupted run reaches terminal state, the same chat/session must accept the next user message normally.
- Late results from the interrupted `web_fetch` must not be relayed as a new tool completion for the next run.

## Unchanged Requirement: Tool Presentation

The WebFetch presentation contract remains unchanged. Gateway continues to relay existing `web_fetch` presenter fields such as URL, status, and content when the tool completes normally or fails with a fetch/prompt error.

