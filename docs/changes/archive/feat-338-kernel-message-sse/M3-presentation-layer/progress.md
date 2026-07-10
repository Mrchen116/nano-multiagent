# M3: Presentation Layer — Progress

## RP1: Core presentation protocol
- `src/agent/core/tools/presentation.py`: `ToolPresentationEvent` dataclass + `ToolPresenter` Protocol.

## RP2: Platform presentation registry + default presenter
- `src/agent/platform/tools/presentation.py`: `register_presenter()`, `resolve_presenter()`, `_DefaultPresenter`.
- `_enforce_cap()` tail-truncates known string fields (stdout/stderr/diff/content) at 256 KiB and sets `detail["truncated"] = True`.

## RP3: Built-in tool presenters
- `read`: start=path, end=line count/summary/image/unchanged.
- `write`: start=path, end=created/overwritten + bytes, detail=full content.
- `edit`: start=path, end=updated/failed, detail=unified diff + firstChangedLine.
- `bash`: start=command (truncated 80 chars), end=exit+elapsed, detail=stdout/stderr/exit_code.
- `web_fetch`: start=url (truncated 100 chars), end=status+title, detail=url/final_url/status/title/body_excerpt.
- `task`: start=description (truncated 80), end=status, detail=description/status/summary/artifacts.

## RP4: Registration
- `_register_builtin_presenters()` called at module load time.
- Unknown tools fall back to `_DefaultPresenter`.

## Test Results
```
tests/unit/platform/tools/test_presentation.py: 20 passed
tests/unit/platform/tools/test_presentation_cap.py: 5 passed

25 passed total
```

## Commits
- `core/tools/presentation.py`: `ToolPresentationEvent`, `ToolPresenter` Protocol.
- `platform/tools/presentation.py`: registry, default presenter, 6 built-in presenters, `_enforce_cap()`.
- `tests/unit/platform/tools/test_presentation.py`: 20 unit tests.
- `tests/unit/platform/tools/test_presentation_cap.py`: 5 hard-cap tests.
