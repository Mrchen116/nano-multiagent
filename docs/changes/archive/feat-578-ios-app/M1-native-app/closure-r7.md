# Code Review R7 — targeted static closure

- Finding origin: `c8eafc360`, R6 P2 / visual verifier V-W1.
- Fixed reviewed head: `3691c0f8b`; scope is solely `TasksView.swift` changing `.onSubmit(of: .search)` to `.onSubmit`.
- **closed (static):** the default text submission trigger now matches `NanoSearchField`'s ordinary TextField. The same `Task { await load() }` query action remains attached to the ancestor List; query binding, paging, loading guards and polling are unchanged. No surviving concrete code finding: `code-review-r7.json` is `[]`.
- No UI or tests were run. This does not claim that the keyboard Search action has been observed on the device/simulator. The relevant real interaction remains part of subsequent product review.
- P6 and `verification-visual-r1.md`'s overall `not_pass` remain open for their recorded evidence gates. No final verifier/product/device acceptance is updated here. The reported Release archive build in progress is not treated as completed evidence by this closure.

No implementation changes or commit were made by the reviewer.
