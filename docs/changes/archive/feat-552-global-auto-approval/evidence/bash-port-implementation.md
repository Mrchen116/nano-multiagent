# Bash permission port: fixed CC 2.1.267

Implementation evidence for design D2, recorded 2026-09-12. The runtime checks are Python; no Node, Claude Code process, or shell execution is used to classify a command.

## Fixed source

The official `@anthropic-ai/claude-code@2.1.267` package contains `bin/claude.exe`, 200489184 bytes, SHA-256 `a681f3008f0050029aeebcab3af51bb6a55ddeb625a3af3141a4416d43cd2558`. Extraction used `/private/tmp/feat552-cc267-pinned/node_modules/@anthropic-ai/claude-code/bin/claude.exe`. The binary was rehashed before final validation. The older reconstructed repository was not used as implementation input.

Offsets below are zero-based bytes with an exclusive end; the extracted bytes, before formatting, have these hashes:

| Source | Byte interval | SHA-256 |
|---|---|---|
| Native `pu` / `Ub` parser | 161625295–161686844 | `6654bf14765251ac5c73412ba43f769e6174c7a4d90033a3878ffc1e6139194e` |
| Shallow argv `_8` / `GRe` / `dr` / `Zu` | 161687207–161688564 | `a0bdecd056c36bfb4f91687d31b5bcb42c81880aabe147bdf42ee4f37288e423` |
| `E_` argv entry | 164767098–164767222 | `68a4181f60116eddf92e9d90e712a15fa71f840748966d8450b4cc51c1e2e51f` |
| `Hhe` / `_ur` AST and syntax security | 161782815–161850005 | `4154aa5d57d1e5d5e8cf08e2c9b02a756ff3389827ec04ddfb165e876e399347` |
| Shared flags, `P_`, `T2e` | 161850005–161873317 | `e99b96d38bd03f68aab0d600cf10d1936e69ff34e68be96b0975389f8843cb2a` |
| `v7` / `TIo` / `hxn` sed validation | 165459438–165464672 | `af81c52bce3acf195a8bf5b8bbb46d5ea76f630b7affc4c27046806f7ea6a1ca` |
| `Jxn` / `aMo` / `yMo` table and callbacks | 165505004–165525585 | `b1c4a0ae74779733173eaa5cc8688f570a07e028bb2466f726a40098d6b19a51` |
| `Nlt` / `SMo` / `lRn` composition | 165525585–165534787 | `ad66fd5955ac1bf963a4391e183ddac47f6c6a511662cd9a5b34cd60b9ca7ebd` |

The separate literal-shape helpers `tue`/`rue` start at 164765296, with `ntt`/`Rtt` at 164767222. Windows path predicates `Tn` and `CG` start at 158521200 and 158533151. Git directory guard `fSe` starts in the 159596700 region. These source functions were inspected in addition to the table slices.

## Runtime mapping

- `bash_policy.py` remains the one decision entry point and retains override file lookup/precedence. Its default route now uses parsed command structure and the pinned policy, replacing the broad prefix allowlist. Ordinary commands that cannot be proved read-only return `review`; only configured explicit denies return `denied`. Existing explicit `allow_prefixes` remain replacement permissions with their existing scope.
- `bash_syntax.py` adapts `tree-sitter==0.25.2` and `tree-sitter-bash==0.25.1` into the pinned `SimpleCommand` contract: original text, quote-decoded argv, redirects, assignment facts, and whole-command review reasons. It covers pipelines/lists, wrappers, loops, conditions, quoted substitution, literal heredocs, arithmetic/test validation, expansion/glob distinctions, comments, control characters, and unparseable/unsupported forms. The 10000-unit analysis bound uses JavaScript-compatible UTF-16 units.
- `flag_words()` is a separate port of the source's shallow `E_`/`GRe` tokenizer. This matters: the command table does not always see the same representation as the native AST argv; using the AST alone produced a real differential on literal arithmetic arguments.
- `bash_readonly.py` contains the complete external-user table callbacks and argv fast paths: literal simple forms, `find`, `printf`, tests/`[[ ]]`, readonly `sed`, Git list/format/remote restrictions, docker connection flags, process-environment access, `man`/`help`, `lsof`, `ss`, `tput`, variable/redirect safety, shell wrappers, and the original glob-safe command set. Regex-only `uniq`/`jq` paths are retained. All compound segments must satisfy the same applicable checks.
- `bash_readonly_commands.json` is the versioned runtime asset: 53 command entries, 1496 safe-flag declarations, 48 literal simple forms, xargs targets, and the source's supporting find/shell/integer/volatile/docker constants. It contains no local configuration. `pyproject.toml` includes the pinned dependencies and packages this JSON.
- Git checks use the effective tool cwd, including ancestor bare-repository indicators and `.git` file/symlink indirection. Normal repositories and worktree gitdir locations are tested separately. Compound `cd` + Git requires review. Creating Git internals cannot reach the readonly path because file-writing commands/redirections are already rejected; no write/edit grant is introduced.
- Windows-only `P_` UNC/WebDAV checks, attached/equals option operands, native-NT path prefixes, input redirections, the secondary decoded-operand check, and the Windows exclusion of `xargs` are ported under the platform condition. Their decision branches were replayed in the reference and Python implementations; this is not a Windows shell execution test.

The source's internal-employee-only extra command table is excluded under its original external-user condition. Nano has no OS sandbox, so sandbox/edit-grant branches are not asserted and `sed` uses the source's `allowFileWrites=false` branch. These are capability/identity conditions, not substitutions for missing command checks.

## Complete external-user table

`flag types` means the shared `T2e` algorithm, including `--`, numeric and string values, attached values, short-option bundles, positional restrictions, and xargs target rules. Named entries also run their source-specific callback. The source exceptions to `--` handling are preserved for `base64`, `pyright`, and `test`.

| Command | Safe flags | Additional check |
|---|---:|---|
| `xargs` | 11 | flag types |
| `git diff` | 56 | flag types |
| `git log` | 64 | git log |
| `git show` | 29 | git show |
| `git shortlog` | 20 | git shortlog |
| `git reflog` | 19 | git reflog |
| `git stash list` | 12 | flag types |
| `git ls-remote` | 13 | git ls-remote |
| `git status` | 20 | flag types |
| `git blame` | 26 | flag types |
| `git ls-files` | 34 | flag types |
| `git config --get` | 16 | flag types |
| `git remote show` | 1 | git remote show |
| `git remote` | 2 | git remote |
| `git merge-base` | 5 | flag types |
| `git rev-parse` | 18 | flag types |
| `git rev-list` | 37 | git rev-list |
| `git describe` | 12 | flag types |
| `git cat-file` | 6 | flag types |
| `git for-each-ref` | 8 | git for-each-ref |
| `git grep` | 49 | flag types |
| `git stash show` | 16 | flag types |
| `git worktree list` | 4 | flag types |
| `git tag` | 14 | git tag |
| `git branch` | 24 | git branch |
| `file` | 34 | flag types |
| `sed` | 20 | sed |
| `sort` | 45 | flag types |
| `man` | 11 | man |
| `help` | 1 | help |
| `netstat` | 12 | flag types |
| `ps` | 42 | ps |
| `base64` | 13 | flag types |
| `grep` | 85 | flag types |
| `egrep` | 85 | flag types |
| `fgrep` | 85 | flag types |
| `rg` | 60 | flag types |
| `sha256sum` | 17 | flag types |
| `sha1sum` | 17 | flag types |
| `md5sum` | 17 | flag types |
| `tree` | 62 | flag types |
| `date` | 15 | date |
| `hostname` | 21 | flag types + raw regex |
| `lsof` | 37 | lsof |
| `pgrep` | 49 | flag types |
| `tput` | 3 | tput |
| `ss` | 65 | ss |
| `fd` | 65 | flag types |
| `fdfind` | 65 | flag types |
| `pyright` | 9 | pyright |
| `docker logs` | 9 | docker logs |
| `docker inspect` | 5 | docker inspect |
| `test` | 31 | test |

Examples of observable corrections include reviewing `git config --list`, `git tag v1`, `git branch new`, `python -V`, and `command -v python3` under the fixed source policy, while allowing readonly pipelines, `sleep 1`, literal stdin `sed 's/a/b/'`, and supported wrappers. This is source parity, not a new informal list of commands considered safe by Nano.

## Validation and limits

Before implementation, the expanded focused Bash suite produced **36 failures / 81 passes**, including incorrect Git write allowances and missing read-only syntax. The existing assertions were then reconciled against the fixed source: historical Nano defaults are not treated as the reference when the approved design explicitly replaces them.

The committed fixture `tests/unit/agent/platform/tools/builtins/fixtures/bash_readonly_cc_2_1_267.json` contains **2437 independently generated expected decisions**:

| Group | Cases | Reference errors | Decision differences |
|---|---:|---:|---:|
| Every command, every declared safe flag with its type value, unknown flags, literal forms | 1650 | 0 | 0 |
| Syntax, substitutions, assignment, redirects, Git/sed/path/security and prior regressions | 757 | 0 | 0 |
| Windows conditional path/operand and xargs decisions | 30 | 0 | 0 |

The reference replay evaluated original JavaScript source from the pinned binary in a Node VM. Crucially, final expected decisions use its **own native `pu` AST parser and original `E_`/`GRe` argv parser**, not the Python adapter's AST. It calls `Hhe`, `_ur`, and `lRn` with external-user settings and sandbox disabled. The fixture cwd has no bare Git indicators; Git filesystem guards are therefore tested with real temporary directories in Python rather than inferred from that replay. Telemetry and host-only services were stubbed; no tested Bash command was executed by the oracle. Two additional native replays confirmed the 9999/10001 UTF-16 boundary with non-BMP characters.

Development replay scripts and extracted source are local scratch artifacts under `/private/tmp/feat552-bash-*`; they are not runtime dependencies or committed binaries. Fixture provenance records the binary hash, reference functions, and environment conditions. To regenerate, use the pinned package and byte map above, execute the original parser/security/table/flow functions under those conditions, and project `behavior: allow` to `allowed`, every other result to `review`.

The older policy-only chain/emulate/environment assertions in `test_tool_safety_policy.py` are folded into the source fixture instead of preserving a second, inconsistent command truth table. BashTool boundary tests now expect classification for unproved commands. The loader/hook/registry tests distinguish explicit user denies from unavailable classification by checking decision provenance, and the readonly gate fixture supplies the real cwd required by BashTool. The new provenance assertion exposed a dropped-field defect in HookRunner; the parent integration owns that core fix.

Final focused validation:

```sh
.venv/bin/python -m pytest -q tests/unit/agent/platform/tools/builtins/test_bash_policy.py tests/unit/agent/tools/test_bash_tool.py tests/integration/test_bash_check_permissions_integration.py
.venv/bin/ruff check src/agent/platform/tools/builtins/bash_policy.py src/agent/platform/tools/builtins/bash_readonly.py src/agent/platform/tools/builtins/bash_syntax.py tests/unit/agent/platform/tools/builtins/test_bash_policy.py
git diff --check
```

Result: **42 tests passed**, Ruff clean, diff check clean. The 2437 fixture decisions are evaluated within three parameterized tests; they are not reported as 2437 separate pytest tests. Integration coverage verifies the tool permission entry and no second executor policy check. Existing BashTool unit tests execute bounded local commands and verify output/timeout/error behavior. No persistent service was started for this work.

This evidence proves the recorded source decisions, command table coverage, and local permission integration. It does not claim exhaustive equivalence over every possible shell program, a real approval-model journey, Windows shell execution, production deployment, or an OS sandbox that Nano does not provide. The parent implementation owns gate ordering, model classification, SDK/PA integration and those broader journeys.
