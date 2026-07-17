# R2 desktop Chromium QA

- Browser: Playwright bundled Chromium 148.0.7778.96 (Chrome for Testing), headless desktop context.
- Viewport: 1440×900.
- Product entry: ephemeral worktree IM `http://127.0.0.1:55046/chat/f8d9766a8add4ca099a0c06cbab96e28` with real login, Gateway-synced `default-agent`, and the real upload endpoint.
- Screenshot: `r2-attachment-error-toast.png`.
- Expected product failure: one `413 POST /im/v1/uploads?file_name=too-large.png`, intentionally triggered with an image larger than 10 MiB.
- Console errors: one matching 413 resource error from the intentionally rejected upload; no unexpected product error.
- Other failed requests: one external Google Fonts `ERR_ABORTED` when the one-shot browser context closed; no product API request failure beyond the expected 413.

## Observations

| Check | Result |
|---|---|
| Three-image partial success | one paste containing `first-ok.png`, `too-large.png`, `last-ok.png` was prevented and left the textarea empty |
| Failed item excluded | no `too-large.png` chip rendered |
| Successful items retained | `first-ok.png`, `last-ok.png` remained in clipboard order |
| Existing chip shape | both `.chat-attachment-thumb` boxes measured 64×64 |
| Page-level feedback | alert title was `Attachment upload failed`; body was `This image is larger than the current attachment limit.` |
| Dismiss | clicking `Dismiss attachment error` removed the alert; remaining alert count was 0 |

## Prototype comparison

| Reference | Result | Evidence |
|---|---|---|
| `#attachment-error-toast` | match | page-level visible, localized, dismissible alert; rejected item absent while both successful items remain |
| `#composer-pasted-images` | match | existing 64×64 pending chips retained in successful clipboard order |
| sidebar / message list / composer redesign | unchanged | no layout expansion outside the existing composer and page toast owner |

## Harness note

The `playwright-cli` wrapper selected the machine's `/Applications/Google Chrome.app`, whose daemon process was externally killed before page creation in this execution environment. The repository's installed Playwright package exposes its own signed Chrome for Testing binary; a one-shot Playwright driver using that bundled real Chromium completed the full interaction. No test script or browser profile was persisted.
