# Upstream provenance

Adapted from the local OpenAI Codex bundled system skill at
`/Users/czj/.codex/skills/.system/skill-creator/`, captured 2026-10-29.
The accompanying `license.txt` is copied verbatim from that source (Apache-2.0).

The upstream SKILL.md supplies the writing principles and progressive disclosure
structure. Nano adaptation replaces Codex paths, initialization and UI metadata
instructions with the existing `skill_manage` interface, agent-default scope,
existing global authorization and actual save receipts. UI metadata, icons and
Codex helper scripts are not distributed; the migrated entrypoint has no missing
support-resource references. No third-party skill with the same name was used.

SHA-256 of the UTF-8 manifest below, including its final newline:
`544f9e178fe180e6fd3dd3899ce1aa4d7aa81dc449cc0ea5ed760d20d6a60bb5`.

```text
6656e54755638e8efcf275a472b9672eaa8a9a1b9e59dc210e275b03b59e1e66  SKILL.md
d07d21b93fcf3d4dc8d9a3399c05fc226a49a333a96d3e1c68b451b8dd9eade6  agents/openai.yaml
6591bf8ea9bb9435890dbdea299e0d2bd05f3aa893a335d26e4c535e93c8e7fb  assets/skill-creator-small.svg
a4024b0306ddb05847e1012879d37aaf1e658205199da596f5145ed7a88d9162  assets/skill-creator.png
cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30  license.txt
ffac39318e408108141d40f820968e59f70434a891694f9bf1d25be8237b150c  references/openai_yaml.md
816df12072d74faf924d802a6599a139997e1441e90bfe4869ec304f2e5e2851  scripts/generate_openai_yaml.py
bf0656a5f9d8d8cdecf0245eaf27e1df8e0e9b6d40ccdda814eb8e3d5f6992c8  scripts/init_skill.py
ee6dba90f44d37171c5a6edb8095979c54919ff6822c1a907afca2e78c48738c  scripts/quick_validate.py
```
