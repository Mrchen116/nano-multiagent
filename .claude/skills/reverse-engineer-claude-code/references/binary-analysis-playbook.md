# Installed package and binary analysis playbook

Use this escalation only when the three primary lanes leave a material implementation decision unresolved. Prefer the highest-level artifact that answers the question; native disassembly is the last step, not the first.

## Evidence ladder

1. **Package surface** — resolve the executable, inspect package metadata, wrappers, adjacent source/maps/type declarations, and version.
2. **Binary identity** — record file type, architecture, size, SHA-256, code signature, linked libraries, and build/runtime markers.
3. **Feature strings** — search exact tool errors, schema fields, notification text, environment variables, and generated artifact names.
4. **Embedded source** — bundled Bun/Node/Deno binaries often contain minified JavaScript. Recover the feature-specific validation → compile → execute call chain before inspecting native instructions.
5. **Native symbols/disassembly** — use only when the behavior is implemented natively or embedded source cannot answer the discriminating question.
6. **Dynamic observation** — process/file tracing or debugger attachment only when static evidence remains ambiguous and it can be done without exposing credentials or altering behavior.

## Read-only baseline

Representative macOS commands:

```bash
BIN="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$(command -v claude)")"
claude --version
file "$BIN"
shasum -a 256 "$BIN"
otool -L "$BIN"
codesign -dvv "$BIN"
strings -a "$BIN" | rg 'Workflow launched|resumeFromRunId|journal\.jsonl'
```

Do not reuse broad system variables such as `HOME`. Do not patch, re-sign, inject libraries into, or redistribute the executable.

## Bundled JavaScript procedure

When a binary contains a JavaScript runtime such as Bun/JavaScriptCore:

1. Search for an exact feature string and record all byte offsets.
2. Extract a small printable window around the feature occurrence for local inspection; do not commit a vendor bundle dump.
3. Identify feature-specific function boundaries and imports such as parser, VM, worker, process, or filesystem APIs.
4. Follow the same minified identifiers across validation, compilation, launch, and execution.
5. Require an actual call-site chain before concluding that a bundled library is used by the feature.

Examples of evidence strength:

- `node:vm` exists somewhere in a Bun binary — weak; it may be runtime baggage.
- The Workflow compiler constructs `new vm.Script(...)`, its launcher passes that object to the runner, and the runner calls `runInContext(...)` — strong.
- Acorn is bundled — weak.
- The Workflow metadata parser calls Acorn, traverses the resulting AST, rejects nodes, then rewrites selected await/return/yield ranges — strong.

## Provenance record

```text
installed_version:
binary_path:
sha256:
file_format_arch:
signer:
runtime_markers:
feature_needles:
byte_offsets:
call_chain:
observation:
limit:
```

Minified function names and byte offsets are build-specific. Never present them as stable public APIs. Distinguish:

- **package observation** — wrapper/manifest/source shipped beside the binary;
- **binary observation** — exact bytes or embedded call sites in the hashed executable;
- **inference** — interpretation not directly established by the recovered call chain.

## Stop conditions

Stop when the recovered call chain answers the discriminating implementation question. Do not continue into disassembly merely to make the investigation look deeper. If strings or embedded source reveal secrets, personal data, credentials, or unrelated proprietary content, do not copy or report it.
