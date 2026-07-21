# bugfix-471-M2 — Progress

## 启动记录

- 已读取 incident、design、prototype、AGENTS、LOGBOOK 与 `docs/TESTING_GUIDE.md`。
- M2 范围：Gateway durable boundary outbox / external shadow saga、IM typed timeline 与协议、Web IM typed reducer/render，以及相应回归和真实产品入口证据。
- 前端原型必须匹配：固定文案、首条采用新配置用户消息前、非消息语义，以及 reload/reconnect/older-page prepend 的稳定锚定；证据将写入 `evidence/`。
- 基线：`PYTHONPATH=src pytest -m "not e2e"` 正在运行。

## R1 — IM typed timeline 与配置边界协议

- Status: TODO

## R2 — Gateway outbox 与外部 shadow saga

- Status: TODO

## R3 — Web IM timeline union 与真实浏览器验收

- Status: TODO
