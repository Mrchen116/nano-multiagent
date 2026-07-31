# M102 — Gateway WebSocket Client + send_message + 上报

## 任务目标
- 对齐 `SPEC.md`、`docs/NodeGateway-SPEC.md` §7/§8、`docs/IM-SPEC.md` §4 的 Gateway ↔ IM WebSocket 双向协议。
- 实现 Gateway 上报、WebIM relay 接入、`send_message(text, to)` 产品专属工具、可选配置同步入口。
- 保持 IM 离线时 Gateway 本地自治，不破坏既有本地主路径。

## 编码前已读
- `SPEC.md`
- `docs/NodeGateway-SPEC.md`
- `docs/IM-SPEC.md`
- `docs/内核设计SPEC.md`
- `LOGBOOK.md`
- `ROADMAP.md`
- `COMMENTING_GUIDE.md`

## 执行计划
1. 在 M102 worktree 做 baseline，确认现状可回归。
2. 补齐 Gateway 侧缺失模块：`ws/im_connection.py`、`reporter/upstream_reporter.py`、`channels/web_relay_adapter.py`、`config/sync_client.py`。
3. 补齐产品工具：`src/agent/products/personal_assistant/tools/send_message.py`，并接入默认 toolset。
4. 用真实 IM app + Gateway 边界做 focused tests，验证 relay/config sync/reporting/tool 合同。
5. 更新 `PROGRESS/` 记录证据，不触碰 `data/dev-tasks.json`，然后提交到 `milestone/M102`。

## 完成情况
- [x] `src/personal_assistant/ws/im_connection.py`：实现主动连接、断线重连、指数退避且上限受 `reconnect_max_seconds` 限制，断线时只记录状态并继续本地自治。
- [x] `src/personal_assistant/reporter/upstream_reporter.py`：实现 `node.register` / `node.heartbeat` / `node.report` / `node.delivery_receipt` payload 构建与发送。
- [x] `src/personal_assistant/channels/web_relay_adapter.py`：实现 `relay.message` 下推接入并规范化为 `InboundMessage`。
- [x] `src/personal_assistant/config/sync_client.py`：实现可选 `config.sync` 记录与拉取边界。
- [x] `send_message` 已迁移到 `src/agent/products/personal_assistant/tools/send_message.py`，并接入产品默认 toolset。
- [x] focused tests 已转绿。
- [ ] 提交 commit 并在 PROGRESS 补录最终 hash/证据。

## 范围约束
- 仅修改 M102 所需 Gateway / personal_assistant / product tool / milestone 文档 / board。
- 不做无关大重构；兼容层若有，保持最小且可解释。
