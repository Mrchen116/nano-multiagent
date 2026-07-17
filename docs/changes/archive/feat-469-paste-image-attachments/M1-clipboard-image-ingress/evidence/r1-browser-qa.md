# R1 desktop Chromium QA

- Browser: Playwright bundled Chromium 148.0.7778.96 (Chrome for Testing), headless desktop context.
- Viewport: 1440×900.
- Product entry: ephemeral worktree IM `http://127.0.0.1:55046/chat/12157a23b72a4a628e32a47cb2b75c06` with real login, Gateway-synced `default-agent`, real upload endpoint and real message POST.
- Screenshots: `r1-pasted-images.png`, `r1-mixed.png`.
- Console errors: none.
- Product API failures: none. One external Google Fonts request was aborted when the one-shot browser context closed; it did not affect the product page or any IM API.

## Observations

| Check | Result |
|---|---|
| Single image paste | paste event was prevented, `single.png` became the existing pending image chip, and Remove deleted it |
| Existing chip shape | reused `AttachmentChip`; its thumbnail contract remains 64×64 (`.chat-attachment-thumb`), with the existing adjacent remove control |
| Multi-image paste | `first.png`, `second.png` rendered in clipboard order; `r1-pasted-images.png` records the state |
| Send with caption | removed `first.png`, typed `caption from Chromium`, sent `second.png`; real message POST returned 201 and the composer pending chip cleared |
| Mixed image + text | paste event was prevented, `mixed.png` became pending, textarea remained empty (no URL/alt text); `r1-mixed.png` records the state |
| Non-image file paste | paste event was not prevented and no attachment was added |

## Harness note

The `playwright-cli` wrapper selected the machine's `/Applications/Google Chrome.app`, whose daemon process was externally killed before page creation in this execution environment. The repository's installed Playwright package exposes its own signed Chrome for Testing binary; a one-shot Playwright driver using that bundled real Chromium completed the full interaction. No test script or browser profile was persisted.
