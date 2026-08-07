# M3 implementation record

## Scope

- CLI's product factory now explicitly passes `~/.nanocode` as the global
  configuration root while retaining `.nanocode` as its workspace dirname.
- The auto-mode direct-hook fallback first consumes the selected
  `workspace_config_root`; if no scope metadata exists, the product-neutral
  kernel default is `<workspace>/.nano`, not a CLI directory.
- The write/edit dangerous-directory guard now protects `.nanoassistant` as
  the PA's current persistent configuration directory.

## M1 verification closure

- Added a real streamed bash turn whose only deny rule is
  `<workspace>/.consumer/policy.toml`.  The pre-tool chain returns
  `reason_code=denied`, proving that policy selection follows the scoped
  workspace config root rather than a hard-coded product directory.

## Verification

- CLI product wiring, auto-mode hook, dangerous-path and scoped kernel suites:
  101 passed.
- Bash integration suite with the new real pre-tool policy check: 4 passed.
- `ruff check` and `git diff --check` passed for the changed files.
