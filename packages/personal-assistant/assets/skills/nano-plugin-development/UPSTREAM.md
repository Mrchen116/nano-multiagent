# Upstream provenance

Baseline: DeepSeek Harness `5badb15009ae1756c3afe0ae0cef1faafc290ccc`, MIT, Copyright (c) 2026 DeepSeek. The retained license is [LICENSE.upstream.txt](LICENSE.upstream.txt).

Source: [cordis-plugin-development](https://github.com/deepseek-ai/deepseek-harness/tree/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/preset/agent-preset/skills/cordis-plugin-development).

The entry workflow and bundle guidance are adapted from its `SKILL.md` and `references/host-plugin.md`. Effect ownership, prompt sections and service composition follow `references/practices.md` and the upstream `cordis-composition-reference` / `editing-cordis-compositions` Skills. Verification retains working-first, risk-scaled checks and bounded temporary resources. Public package READMEs and declarations remain authoritative for APIs.

Nano adaptations are limited to workspace ownership and tool selection, its finite API documentation query, absence of DSH Client/MCP destinations, the workspace overlay, and Nano's queued manual schedule tool. Display/icon/UI-browser instructions and Host-profile editing are omitted because they do not apply to Nano's clients. Small tool/prompt/service examples demonstrate the supported public APIs; they do not define another runtime or package-update mechanism.

Package replacement retains native `restart-required` semantics. There is no Nano guarantee of code hot replacement, no copied API registry and no compaction pressure-test recipe.
