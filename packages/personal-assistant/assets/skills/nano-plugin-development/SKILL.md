---
name: nano-plugin-development
description: "Use when creating, installing, configuring, updating or debugging a workspace plugin in Nano: tools, prompt contributions, private services, local observations or compaction. Ordinary one-off work needs no plugin."
---

# Workspace plugins

Adapted from DSH's `cordis-plugin-development`; provenance and adaptation scope are in [UPSTREAM.md](UPSTREAM.md). Use ordinary workspace files to author a bundle, then `plugin_manager` with `action: install_bundle` and the absolute package directory as `target`. Changes affect every Agent sharing this workspace and survive restart.

## Nano scope

The current destination is this Agent's workspace. Nano owns identity, approvals, credentials, Inbox delivery, node lifecycle and its Web IM/iOS/Feishu clients. DSH Web UI slots and MCP templates are not supported Nano destinations. Plugins are trusted local code, not an OS sandbox. Respect disabled Skills and existing tool choices. Use existing tools for one-off work, Skills for reusable knowledge and Workflow/Cron for orchestration.

## Design or review

Inspect the proposed or existing plugin against current APIs. Report design choices or findings instead of following the installation workflow. Do not write files, install bundles, or change profile state unless the user requests implementation.

## Deliver a working plugin first

1. Resolve the requested result and destination. Choose reasonable details and implement a small first version.
2. Discover only the APIs needed for that version: `plugin_manager` with `action: describe_api` and the relevant topic below. Read the returned package README and public declarations; the installed runtime is the authority. Public Host APIs are not automatically supported Nano extension points.
3. Read and copy the matching template files into one workspace directory, or author the package, patch and required files there. Check JavaScript syntax and the manifest, then install. Never install or syntax-check a template in place.
4. Read the installation result: `application` and warnings decide whether the change is live. After `application: applied`, exercise the capability. Replacing an installed package can return `restart-required`: report the saved update and wait for the node's normal authorized restart before verifying new code. Do not claim an online upgrade or repeatedly toggle the bundle to force one.
5. Fix observed defects in the same plugin. When the requested result works, finish with its location and verification status. Do not continue speculative variants or optional features. Restore user state changed during testing.

## Knowledge sources, in order

1. The finite `describe_api` result locates the currently installed public interfaces; it substitutes for DSH's broad Host/Client inspection tools in Nano.
2. Read those package READMEs and the relevant public types. Do not guess paths from a profile or copy another version's API.
3. Start source-level diagnosis from a concrete installation or runtime failure. Missing browser control or a failed optional output is not a reason to repair the environment, inspect credentials or unrelated sessions, or modify the host.

## Read next

Paths are relative to the base directory returned by `skill`. Read only the applicable files.

| Task | Topic | Files |
|---|---|---|
| Bundle, configuration, installation and updates | relevant capability | `references/bundle.md` |
| A callable tool | `tool` | `references/tools.md`; `templates/tool/package.json`, `templates/tool/cordis.patch.yml`, `templates/tool/tool.mjs` |
| Prompt contribution | `prompt` | `references/prompt.md`; `templates/prompt/package.json`, `templates/prompt/cordis.patch.yml`, `templates/prompt/prompt.mjs` |
| Private service or file index | `service` | `references/services-events.md`; the four files in `templates/service/`: `package.json`, `cordis.patch.yml`, `provider.mjs`, `consumer.mjs` |
| Local observation | `events` | `references/services-events.md` |
| Compaction | `compaction` | `references/compaction.md` |
| Business verification and delivery | relevant capability | `references/verification.md` |
