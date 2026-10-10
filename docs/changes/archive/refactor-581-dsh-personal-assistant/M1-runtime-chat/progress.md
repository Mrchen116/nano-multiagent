# M1 DSH 驱动的完整单聊

状态：实现与 worker 纵向验证完成；最终独立 reviewer/verifier/code review 尚未执行。此阶段仍使用 Python IM，完整迁移未完成。

## 实现

- 锁定官方 `@deepseek-ai/dsh@0.2.1-alpha.1`，由官方 launcher/profile 启动，Nano bundle 是唯一 stdio JSON-RPC server；没有修改上游源码。已核查 alpha.2 增量，本 unit 保持 Gate 2 的 alpha.1 基线。
- SessionController 创建/恢复、named preset 模型/prompt 接入、真实来源 followup/steer/inject、稳定 input ID、flush/lookup/observe；取消、审批与反向回调独立分发。
- 节点 SQLite 保存输入、会话绑定、持久事件与输出/receipt；IM 丢 ACK 使用同一 output key 恢复，流仅作展示，最终内容从持久历史校正。
- 原生工具/思考/Token Usage 投影、图片授权下载、停止当前执行并保留上下文；同 session 可继续。
- 正常退出先停止准入、取消并 flush、dispose SessionController，再终止官方宿主。DSH 意外退出后节点保持运行，最多自动重启三次并根据持久事实恢复，调用不盲目重放。
- `scripts/e2e-up.sh` 实际启动 TypeScript node 与 DSH；过渡阶段只有设备绑定 bootstrap 和 IM 使用 Python。

## 验证记录（2026-10-09，worker）

- `pnpm build` 通过；原有 15 项窄契约测试通过，新增 supervisor 真进程测试 1 项通过。
- 输入接入测试：SIGKILL 后 pending 输入可查；重复相同 input ID 不重复追加；正常关闭前 owner 取消事实可在冷恢复读取。
- 本地 proxy 实际模型 `deepseek:deepseek-v4-flash`，隔离 IM `127.0.0.1:56221`，node `wt-unit-refactor-581-28867`；工作区、身份、数据、端口与生产隔离。
- 真实 IM 文本回复 `NANO_IM_DSH_OK`，消息 `a2114ec2df4a45a0a69a4d452f87eb2a`。
- 原生 bash harmless printf 触发人工审批；批准后输出 `NANO_APPROVAL_OK`，消息 `f1565d798d404512b0b69fc0bb01a6dd`。Web 页面实际展示 bash 输出、思考段及 19.1k token / 4% context。
- 长 bash 执行时 `/stop` 返回固定中文确认，后续消息返回 `NANO_AFTER_STOP_OK`；被取消输出未发布。
- 待审批时停止，原卡片变为 cancelled；迟到 allow_once 仅返回已取消状态，不重启执行。
- 图片经受权 IM media 下载后，真实模型正确辨认红色正方形和蓝色圆；修复下载缺少 agent_id 导致 404，已持久未接受输入在恢复后只接收一次。
- 同 DSH 会话在节点正常重启后记住随机恢复码；DSH PID 32065 被 SIGKILL，节点 PID 32064 保持，自动启动 DSH 32133，继续同会话召回。
- 临时原始证据在本 worktree 忽略目录 `.dsh-runtime/`；未将日志、数据库、token、截图或 PID 提交。

## 仍属后续 milestone

global、Work、配置 operation、Feishu、群复核、Feature 插件启停与主动机制归 M2；工具/Skill名单及知识/模型 policy、新历史归 M3；Workflow 归 M4；TypeScript IM、入口退役、最终验证与发布演练归 M5。此记录不代表独立产品验收、真机/飞书平台验收或生产部署。
