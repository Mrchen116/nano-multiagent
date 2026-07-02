# M9 Fix Gateway Live Run Progress

## Summary

Round 5's observed "Gateway did not keep running" was not the product blocker in
this reproduction. Gateway and IM stayed alive, but external shadow sync failed
with `400 Bad Request` on `POST /im/v1/conversations/external/find-or-create`,
so the real Lark inbound message never landed in the worktree IM DB.

Root cause: Gateway used `config.node.user_id` as the shadow participant and user
message sender. In a live worktree config copied from another IM instance, that
value can be stale. The IM external find-or-create API derives ownership from the
Bearer token current user and rejects participant ids that reference unknown or
non-current users.

Fix: Gateway now resolves the current authenticated IM user via `GET /im/v1/me`
inside `_IMShadowConversationSyncClient` and uses that user id for the shadow
conversation participant and user message sender. The old `owner_user_id`
constructor argument remains only for compatibility with existing construction.

## Verification

- `pytest -q tests/unit/personal_assistant/test_gateway_im_relay.py::test_external_shadow_sync_uses_authenticated_im_user_not_stale_config_user tests/unit/personal_assistant/test_gateway_im_relay.py tests/unit/personal_assistant/test_inbound_pipeline_session.py tests/unit/personal_assistant/test_gateway_feishu_owner_open_id.py`
  - Result: `38 passed, 7 warnings in 2.52s`
- `pytest -m "not e2e"`
  - Result: `3237 passed, 1 skipped, 22 deselected, 20 warnings in 138.02s`

## Live Lark Evidence

- Worktree IM: `http://127.0.0.1:51600`
- Gateway config channel: `feishu:default-agent`
- Config/auth appId: `cli_aac9315ef3f9dbda`
- Bot openId used as `--user-id`: `ou_b33ae16df1338a00a77d4cdbec653b71`
- Authenticated Lark user openId: `ou_e6d1591026cfdac8d131eb1fdd71bdb9`
- Nonce: `feat447-m9fix-20260702-155227`
- Lark send command: `lark-cli im +messages-send --as user --user-id ou_b33ae16df1338a00a77d4cdbec653b71 --text "feat447-m9fix-20260702-155227 fixed external shadow user" --idempotency-key feat447-m9fix-20260702-155227 --format json`
- Lark message id: `om_x100b6b55c50f751cc49212aa422fe4b`
- Lark chat id: `oc_1906eead0189484ce5ea8a4c245400a6`
- Gateway process stayed running during validation: wrapper pid `90520`, worker pid `90529`
- IM process stayed running during validation: pid `90417`
- IM API after fix:
  - `GET /im/v1/me` -> `200`
  - `POST /im/v1/conversations/external/find-or-create` -> `201`
  - `POST /im/v1/conversations/2e032b8aceab4c24a3b97f7230ddf322/messages` -> `201`
- IM shadow conversation row:
  - id `2e032b8aceab4c24a3b97f7230ddf322`
  - title `default-agent · feishu`
  - external_source `feishu`
  - external_chat_id `feishu:cli_aac9315ef3f9dbda:dm:ou_e6d1591026cfdac8d131eb1fdd71bdb9`
  - config_agent_id `default-agent`
- IM shadow user message row:
  - id `08a0c712dc9240178b0fccec01755c1a`
  - conversation_id `2e032b8aceab4c24a3b97f7230ddf322`
  - sender_type `user`
  - delivery_status `sent`
  - content `feat447-m9fix-20260702-155227 fixed external shadow user`

