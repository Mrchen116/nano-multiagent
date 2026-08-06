# bugfix-507-M1 browser QA

- Date: 2026-08-06
- Runtime: isolated IM/Gateway under `/tmp/nano-bugfix-507-browser.2rRXH8`
- IM port: `57418`
- Vite port: `41987`
- Node: `wt-nano-bugfix-507-browser.2rRXH8-63571`

## Journey

1. Signed in to the isolated IM frontend and opened Agents > e2e > Config.
2. Replaced Custom Instructions with a long two-paragraph role, saved it, and
   confirmed the field remained populated with no dirty changes.
3. Expanded **Preview stable system prompt** and confirmed the saved role was
   present in the stable prompt.
4. Confirmed the help text still says group-chat and memory runtime segments
   are excluded from the preview.
5. Repeated the expanded-preview check at desktop `1440x1000` and mobile
   `390x844`; the long role remained readable through wrapping/scrolling.

## Browser evidence

- Desktop: [desktop-stable-prompt-preview.png](desktop-stable-prompt-preview.png)
- Mobile: [mobile-stable-prompt-preview.png](mobile-stable-prompt-preview.png)
- Browser console: 0 errors, 0 warnings.
- Network: agent config PATCH returned 200; all observed stable prompt preview
  POST requests returned 200; login, agents, nodes, sync, and conversations
  requests also returned 200.
- Prototype / Reference Contract: N/A; the approved design supplied neither.

The browser session, Vite server, IM/Gateway processes, isolated listeners, and
temporary frontend dependency symlink were cleaned after capture.
