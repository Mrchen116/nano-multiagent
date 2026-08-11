# feat-530 M1 real-stack evidence

## Web IM human message envelope

- Claim: A real Web IM human message reaches the model with its actual ingress and occurrence time, while the browser, IM storage, and PA readable chat history retain the raw body.
- Baseline: `unit/feat-530@acd6a6512`; isolated IM + Gateway from this worktree; `Asia/Shanghai`; real configured LLM; browser role `nano` / direct chat with Agent `e2e`.
- Method: Start the isolated default profile, log in through the real browser, send `请只回答你在本条用户消息前看到的来源 channel 和消息发生时间...`, then compare the browser, IM SQLite query, PA readable history, Kernel transcript, and provider request.
- Result: PASS. The Agent answered `source=Web IM; time=Mon 2026-08-10 19:26 CST`. Browser and IM stored only the raw question. Readable history stored only the raw question. Kernel transcript and provider request stored `[Web IM Mon 2026-08-10 19:26 CST] <raw question>`.
- Locator: `.gateway-workspace/e2e/.nanoassistant/sessions/sess_163bd417f2035c5c.jsonl`; `.gateway-workspace/e2e/.nanoassistant/chat_history/sess_163bd417f2035c5c.jsonl`; `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-10_19-26-33_119_sess_163bd417f2035c5c/`.
- Limit: These are local gitignored/runtime locators from one real-stack run, not permanent regression artifacts.

## Header-shaped user body and cache-safe prompt

- Claim: A user-authored body that itself begins with a valid-looking Feishu header is not stripped from readable surfaces; per-message timestamps do not mutate the stable system prompt.
- Baseline: Same run and commit as above.
- Method: Send `[Feishu Mon 2026-08-10 09:16 CST] 这是用户正文，请原样重复此消息。`; compare browser/readable history with transcript/provider request; hash the `system` field of the first two provider requests.
- Result: PASS. Browser and readable history preserved the complete user-authored prefix byte-for-byte. Model input was `[Web IM Mon 2026-08-10 19:26 CST] [Feishu Mon 2026-08-10 09:16 CST] ...`. Both provider system fields had SHA-256 `3f2294f2fecfcf74cc5221f4fb483dc1ee5736b06347ae27d39f4ff7e20a3682`; both contained `Time zone: Asia/Shanghai` and `Current working directory:`, and neither contained `Current date and time:`.
- Locator: Same transcript/chat-history/provider directory as above; request files ending `19-26-33_119-req-anthropic_messages.json` and `19-26-54_328-req-anthropic_messages.json`.
- Limit: The hash proves equality for these two calls only; automated prompt tests protect the long-term policy.

## Restart recovery and active steer

- Claim: A Gateway restart reuses the prior decorated transcript bytes, and an active-steer human message receives the same envelope without adding a separate readable chat-history user pair.
- Baseline: Same worktree/commit; the Gateway alone was stopped and restarted against the same isolated IM database, binding store, and workspace.
- Method: After restart, ask for the prior user message's outer runtime annotation; then start `bash sleep 12` and send a second Web IM message while that run is active. Inspect the resulting UI, transcript, readable history, and final provider request.
- Result: PASS. After restart the Agent answered the prior value `source=Web IM; time=Mon 2026-08-10 19:26 CST`. The active-steer provider round contained `[Web IM Mon 2026-08-10 19:31 CST] 这是运行中的追加消息...`, and the Agent answered that channel/time. Readable history retained its existing one-user-pair semantics for the run.
- Locator: Same transcript/chat-history directory; provider request `2026-08-10_19-31-23_673-req-anthropic_messages.json`.
- Limit: This validates current active-steer delivery only; feat-530 intentionally does not change steer persistence/recovery lifecycle.

## Real Feishu direct ingress and model-input boundary

- Claim: The dedicated Feishu profile starts from the exact feat-530 branch, receives a real test-user direct message, and gives Kernel the frozen Feishu source/time envelope.
- Baseline: `unit/feat-530@658fc9cac`, rebased onto `origin/main@c40a9aa80`; private dedicated fixture; repository `--feishu` profile; no production Bot or default `lark-cli` profile used.
- Method: Start the isolated tmux-owned stack with `e2e-up.sh --feishu`; run `e2e-feishu-probe.py`; then send `feat-530-direct-1786424131` from the verified test user to the verified test Bot and compare Feishu readback, Gateway result, and Kernel transcript.
- Result: PARTIAL PASS. The repository ingress probe passed. Feishu accepted direct message `om_x100b689efa83c8a4de05ecdf85c65ff`, and Kernel transcript persisted `[Feishu Tue 2026-08-11 12:55 CST] feat-530-direct-1786424131 ...`, proving the source/time envelope crossed the real Feishu ingress boundary. The Bot's user-visible response was instead `模型调用失败: anthropic transport error: All connection attempts failed` because the configured local LLM proxy was not listening.
- Locator: `.gateway-workspace/e2e/.nanoassistant/sessions/sess_fe7889e78e099195.jsonl`; local gitignored `.gateway.log` / `.im.log`; `/Users/czj/Repos/LLM_PROXY/logs/proxy-console.log` for the independent OAuth startup failure.
- Limit: The LLM proxy's idempotent launcher exhausted its own authentication window with `refresh_token_reused`; no account or credential was changed. A successful real-model answer and the remaining group/catch-up journey are therefore not claimed as passed. All feat-530 runtime resources and the dedicated listener lock were released.
