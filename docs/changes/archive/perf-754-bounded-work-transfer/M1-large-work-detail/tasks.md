# M1 · Large Work detail

- Check the retained source byte length before decoding. Keep the v1 paths for records within 16 MiB and probe the center for the larger transfer.
- Transfer 256 KiB chunks up to 64 MiB. Persist contiguous progress and verify the full original and its projection outside the HTTP lease.
- Atomically commit detail state, event projection and shared checkpoint. Persist quota deferral before confirming a preview and retry after regular journal sync.
- Apply current identity, Work scope and deletion checks on transfer, commit and streamed download. Provide separate execution/turn originals in Web and iOS.
- Protect recovery, two originals for one tool, ordered progress, quota deferral, cross-root validation, restored SQLite and deletion at the real HTTP and durable database seams. Retain the existing v1 tests and update their cursor expectation for capability negotiation.
