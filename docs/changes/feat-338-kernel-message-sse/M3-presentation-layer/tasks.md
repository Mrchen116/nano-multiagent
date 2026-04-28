# M3: Presentation Layer — Roadpoint Plan

## Goal
Implement `ToolPresenter` Protocol, `ToolPresentationEvent` dataclass, built-in tool presenters, and hard-cap truncation.

## Roadpoints

### RP1: Core presentation protocol
- `src/agent/core/tools/presentation.py`: `ToolPresentationEvent` dataclass + `ToolPresenter` Protocol.

### RP2: Platform presentation registry + default presenter
- `src/agent/platform/tools/presentation.py`: `register_presenter()`, `resolve_presenter()`, `_DefaultPresenter`.
- `_enforce_cap()` tail-truncates known string fields (stdout/stderr/diff/content) at 256 KiB and sets `detail["truncated"] = True`.

### RP3: Built-in tool presenters
- `read`: start=path, end=line count/summary, detail for non-text resources.
- `write`: start=path, end=created/overwritten + bytes, detail=full content.
- `edit`: start=path, end=updated/failed, detail=diff.
- `bash`: start=command, end=exit+elapsed, detail=stdout/stderr/exit_code.
- `web_fetch`: start=url, end=status+title, detail=url/final_url/status/title/body_excerpt.
- `task`: start=description, end=status, detail=description/status/summary/artifacts.

### RP4: Bind presenters to built-in tools
- Each built-in tool module gets a presenter instance registered under its name.

## Tests
- `tests/unit/platform/tools/test_presentation.py`: per-tool start/end assertions.
- `tests/unit/platform/tools/test_presentation_cap.py`: bash stdout > 256KiB → tail-truncated + truncated=true.

## Exit Criteria
Both test files pass.
