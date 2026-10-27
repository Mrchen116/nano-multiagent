# 线上失败轨迹：仅审核重放

用户追加要求：直接使用线上故障轨迹，停在审核失败点验证；取得判定后不得继续调用待审工具，以免改动用户文件。

## 基线与方法

- validated_at: `40cd54ddf81c5c7262d1d2f69cb83b5dd3287bad`；executed_base: `b5c1e97901467767a32efc66e83869181242f477`。
- 线上只读取得 `c_8wedfh29` 对应 PA 原生 session `8d36509c-91d0-423d-97d4-2f6419162253`。原始 audit 的 CC edit 失败为 estimated input 1,346,461 + reserve 2,112 > 258,400；Codex bash 失败为 `Guardian budget cannot fit complete pending action`。
- 用原始 session 的完整事件前缀，分别截于 tool/call seq 6224、6359 之前。使用锁定 DSH public `Session.create` 和 `deriveMessages()` 重建有效表面，保留压缩，不以全量消息串替代有效历史。待审参数直接取该 tool/call，未改内容。
- CC prefix SHA-256 `1f20d2b1ea36e7058088a4b45e14bc3dd61eac0fec5b19eeb089d581b43e588a`；Codex prefix SHA-256 `8142fbfed366135878bd1b4578519e27e8a86eac5b8db753645160aed7d9f4bf`。
- 使用线上当前 owner/workspace 合成审批配置，分别选择原失败点的 nano/codex。审核模型仍 `codexOAuth:gpt-6-luna`，low，同一本机兼容代理，contextWindow 258,400。回放中的 provider 名称 `replay` 仅是隔离注册名。
- 原进程的 Inbox live set 不持久化：根据仍存活生产 DSH 子进程启动时间 2026-10-20 13:06:36 +08 重建本次启动之后已完成 Inbox 的 live 标记，其前记录保留 restored。保留身份、页级背景和回执语义；不把整库所有 Inbox 都升为新授权。
- 回放只调用当前 `classify` / `CodexApproval.review`；没有向原 Agent submit/followup，没有调用原动作 executor。隔离运行时额外注册无条件工具执行拒绝屏障、拒绝 product.call 和主 Agent request；任何调查或待审工具调用都会被记录并拒绝。原始生产会话完全未写回。

## 结果

| 原失败点 | 有效消息 | 当前有效判定 | 模型 input tokens | 耗时 | tool attempts / 主 Agent 继续 |
|---|---:|---|---:|---:|---|
| CC edit，seq 6224 | 125 | allow | 46,451 | 5,399 ms | 0 / false |
| Codex bash，seq 6359 | 177 | allow，low risk，authorization unknown（上游 bare allow 默认） | 28,304 uncached | 3,274 ms | 0 / false |

请求序列化估算：CC 188,527 chars / 47,136 estimated tokens；Codex 94,536 chars / 23,638 estimated tokens。估算器与 provider tokenizer 不同，不能混用为同一计数。两者均不再发生原来的超窗/完整 action 放不下。

## Locator / Limit

私有一次性证据仅保存在本机权限受限目录 `/tmp/nano-626-production-replay/`：原始 session、两个截点输入、只审核驱动、独立 runtime 请求/结果及汇总日志。没有把原始聊天或文件内容提交仓库。输入 SHA 可核对截点，`results.log` 和各 runtime `result.json` 记录判定、用量、零工具调用与零续跑。

这是真实线上轨迹的离线真实模型审核回归。它证明上述两次故障动作在修复后可得到有效 verdict，不证明原动作已执行、文件已更新、生产已部署或所有未来动作都会获准。独立 PA 入站/外发检查仍由产品验收及其测试单独验证。
