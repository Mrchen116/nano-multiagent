# M1: lark-skill-bundle

## Context

Feishu-bound agents previously received only the obsolete `feishu-doc` entry.
The milestone packages the complete Lark skill bundle and makes explicit Feishu
allowlists retain it across static startup, managed activation, reconnect, and
online profile sync.

## Decisions

- `lark_bundle.py` is the only source of the packaged skill names. Bootstrap
  continues its generic non-overwriting directory install.
- Static and managed paths append only missing bundle names to non-empty
  allowlists. Empty lists retain global discovery.
- Both IM profile ingress paths share the static Feishu merge before publish.
  Reconnect skips only an agent whose PATCH fails; realtime sync keeps its
  existing retry behavior.
- The copied `lark-im` and `lark-event` skills contain the approved Gateway
  reply-ownership boundary. Runtime delivery code is unchanged.

## Design review status

R8 approved the D1--D3 architecture with no findings. After that review, the
user asked that the bundle-source wording remain generic rather than encode a
transient source snapshot; the user explicitly waived another design-review
round because this did not change behavior or architecture.

## Evidence

- Full source comparison finds exactly the two intended `SKILL.md` boundary
  differences between the packaged bundle and its source.
- Focused regression suite: 54 passed.
- `ruff check` on changed implementation/tests and `scripts/docs-check` pass.
- Product acceptance still requires the isolated external Feishu fixture from
  the design Runbook. It must remain an environment blocker if unavailable;
  no mock substitutes for it.

## Rollback

Revert this milestone commit to restore the prior packaged skill and activation
behavior. The install path never deletes user-owned runtime skills or existing
allowlist entries.
