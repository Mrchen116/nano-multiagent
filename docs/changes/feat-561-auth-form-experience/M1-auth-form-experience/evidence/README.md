# M1 authentication experience evidence

## Baseline

- Branch: `unit/feat-561`
- Product commit: `5db91abfc`
- Executed base: `origin/main@241db5f79`
- Browser: Playwright Chromium against the built frontend served by an isolated worktree IM + Gateway stack
- Runtime: `http://127.0.0.1:61480`, isolated SQLite/JWT/Gateway workspace; stopped after verification and port 61480 confirmed released

## Visual and responsive experience

- **Claim:** `/register` and `/login` use the current nano IM brand, palette, type hierarchy, line icons and surfaces on desktop and mobile; the narrow layout does not overflow horizontally and remains vertically reachable on a short viewport.
- **Method:** build with `npm run build`, start `./scripts/e2e-up.sh --wt <unit-worktree>`, then inspect both routes in Chromium at 1280×800, 390×844 and 375×667. On the short viewport, switch to English, submit an empty registration form, measure the auth scroll container, and scroll it to the bottom.
- **Result:** pass. At 375×667 the auth container measured `clientHeight=667`, `scrollHeight=871`, `maxScroll=204`; `body.scrollWidth=375` matched the viewport. The first invalid field was focused. At maximum scroll, submit bottom was 566 and footer bottom was 606, both inside the 667px viewport.
- **Locators:** `register-desktop-en.png`, `register-mobile-zh.png`, `login-desktop-en.png`, `login-mobile-en.png`, `register-short-mobile-errors-en.png`.
- **Limit:** Chromium and the listed viewports only; system sans fallback is accepted when Google Fonts is unavailable.

## Registration failure and recovery

- **Claim:** the originally reported four-character password is explained at the password field without a doomed request; valid registration succeeds; duplicate usernames are recoverable in place.
- **Method:** in the real `/register` page, submit username `poppy` with password `1234` while counting `/im/v1/auth/register` requests; then register a unique isolated account with a valid password and repeat it to trigger 409.
- **Result:** pass. The short password produced `0` register requests, focused `#password`, and displayed `Password must be at least 8 characters.` A valid account navigated to `/chat`. The duplicate attempt focused `#username`, displayed the localized taken message, and preserved the password value.
- **Locator:** `register-short-password-en.png`; isolated IM log contained the successful 201 and duplicate 409 requests but was not committed.
- **Limit:** the created account and database were isolated runtime data and are not retained as a fixture.

## Login, pending state and navigation

- **Claim:** invalid credentials and service failure are distinct, pending prevents duplicate interaction while locale remains available, and protected deep links survive login.
- **Method:** use the real isolated account to submit a 401 login, abort a login request, delay and fulfill a login request with 503 while switching locale, then open `/settings/agents?view=work#focus` unauthenticated and sign in.
- **Result:** pass. The page showed separate invalid-credentials and retryable-service messages without clearing username. During the delayed request, username and submit were disabled, locale was enabled, and `登录中…` changed immediately to `Signing in…`. Successful login restored `/settings/agents?view=work#focus` exactly.
- **Locator:** Playwright session `feat561actual`; results summarized here because the browser session and request interception were temporary.
- **Limit:** network failure was simulated at the browser request boundary; the remaining isolated stack stayed healthy.

## Automated protection

- **Claim:** stable form, routing and shared-brand regressions are protected at the lowest frontend seam, and existing auth API behavior remains green.
- **Method:** `npm test -- src/features/auth/auth-form-experience.test.tsx src/features/auth/auth-gate.test.tsx src/app/shell/app-shell.test.tsx --reporter=dot`; `npm test -- --reporter=dot`; `npm run build`; `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/im_service/integration/test_auth_routes.py`.
- **Result:** pass: 17 targeted frontend tests, 767 full frontend tests across 83 files, TypeScript/Vite production build, and 7 auth route integration tests. The full frontend run retained existing React `act(...)` and mocked realtime stderr noise but had no failures.
- **Locators:** `src/IM/frontend/src/features/auth/auth-form-experience.test.tsx`, `src/IM/frontend/src/features/auth/auth-gate.test.tsx`, `src/IM/frontend/src/app/shell/app-shell.test.tsx`, `tests/im_service/integration/test_auth_routes.py`.
- **Limit:** automated frontend tests use jsdom; browser layout and real HTTP behavior are covered by the separate evidence above.
