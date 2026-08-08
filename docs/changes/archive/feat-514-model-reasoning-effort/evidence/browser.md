# Browser acceptance evidence

## Model-dependent reasoning, responsive UI, and real response

The isolated E2E stack was started with `config/e2e/gateway.yaml`; Kimi Coding is declared
`reasoning: fixed`. In the Web IM agent detail page, the reasoning section renders the fixed
state and does not offer a user-selectable effort. The accompanying chat sends and receives a
real response through the configured Kimi Coding route.

| Evidence | What it proves |
| --- | --- |
| `create-selectable-1440.png` + `create-selectable-controls.png` | The 1440px desktop form remains usable; choosing DeepSeek exposes only its declared `High` and `Maximum` choices, with `High` selected as the recommendation. |
| `create-fixed-375.png` + `create-fixed-375-controls.png` | The 375px mobile form keeps its one-column layout; choosing Kimi Coding renders the fixed-state explanation rather than an effort selector. |
| `fixed-model-detail-desktop.png` | A persisted fixed Kimi model shows the same concise fixed-state explanation in its detail page. |
| `fixed-model-chat-desktop.png` | The same fixed model completes a real chat turn after the E2E catalog was corrected to a routable Kimi Coding model ID. |

The E2E catalog also declares DeepSeek as selectable (`high`, `max`, default `high`) and Mimo
without a reasoning declaration. Their form-state rendering, model-change reset behavior, and
pending/stale conflict UX are covered by the focused frontend and IM/Gateway contract tests.

## Kimi routing correction

The original E2E fixture used the display-only `kimi:kimi-k3` ID for its fixed state. That ID
was not registered by the local LLM bridge, so a genuine chat ended before a terminal stream
event. The fixture now uses registered `kimiCoding:kimi-for-coding`; a repeated browser chat
returned `fixed model works.`. The correction changes only E2E fixture model IDs, not the
reasoning capability implementation.
