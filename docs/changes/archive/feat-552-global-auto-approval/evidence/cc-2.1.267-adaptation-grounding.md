# CC 2.1.267：Nano 适配补充定位

核对日期：2026-09-12。方法：读取固定官方 npm 安装包可执行文件内的 JavaScript；未修改安装文件，未启动 cron/阈值实测。本页是代码观察，不能替代实际模型请求。

固定二进制 SHA-256：`a681f3008f0050029aeebcab3af51bb6a55ddeb625a3af3141a4416d43cd2558`，200489184 bytes，来源 `@anthropic-ai/claude-code@2.1.267`。以下十进制字节偏移只适用于此哈希。其他上下文实测见[实验报告](cc-2.1.267-context-experiments.md)。

| 位置 | 观察 | 设计含义 |
|---|---|---|
| 168296232 `Bxs`；168344263 `jve` 分支 | 优先内部显式参数/开关，再读 `tengu_auto_mode_config.priorAssistantContext`，缺失 false；普通 subagent loop 强制不启用该 prose 分支 | Nano 主会话按用户要求启用；普通 child 保留 CC 条件，不把父子都统一开启 |
| 168307126–168316055 `yTr` | 来源感知投影，遇到真人才输出 pending assistant；task-notification/peer 不触发配对；工具结果另有 host context | Inbox 可以保留工具形态，不能把每条工具消息展开为真人 |
| 164483942 `Az=2000`；158831103 `oe` | host context 取开头至多 2000 UTF-16 单位，代理对边界处理 | 与 assistant 的末尾截取区别开，不能擅自承诺 host context 全量无限保留 |
| 166126000 附近 `Wjn`；166127386 `zjn` | 内存登记键为消息 uuid + tool_use_id，值为原始 hostClassifierContext；isLive 比较正文相等；上限 10000 条最早淘汰；degradeRestored 删除登记 | live 不是持久化 JSON 里的布尔值；Nano 复用同等运行态登记，不建原件认证服务 |
| 162613839 `mCt` | scheduled-trigger 完整说明：执行预先配置任务，同时明确不是实时真人输入/新的同意；调度不能证明文字作者身份 | Cron 任务可执行，但不能当作对待确认问题的回答 |
| 162612043–162613839 | 普通系统通知和与真人同轮的两种说明；两者均不将通知视为人工答复 | 混合 batch 不共用一个真人来源 |
| 182066500 附近调度入队 | prompt 入队带 isMeta、modelScheduledOrigin、wakeupSource 等来源信息 | 来源在入口写入，不从任意正文标签反推 |
| 177437892 附近来源映射；160654487 `zHt` | scheduled trigger 归 task-notification/subkind scheduled-trigger；投影 frame non-user | 外层 API/JSONL 的 user 键与真人身份不是一回事 |
| 168316794 `bTr` | text 按其 role 序列化；host_context 依据 live 选择 host_context_live/host_context，关联调用 id | 非真人通知仍可呈 user 行，靠来源包装保留区别 |
| 165599392 `M7`、`Sfe/Jlt/WV/Zlt` | 默认连续 3 / 总计 20；deny 双增，成功清连续 | 不按工具名分别计数 |
| 165611419 `D7`；165633383–165635200 `RIn/Ude/vOo` | 优先 localDenialTracking，否则主 state；阈值对本次动作提示/ask；总阈值清计数；headless 分支 abort | Nano 使用主/child 各自会话计数；已确认的全局返回和无人值守 fallback 是产品适配，不复制 headless abort |
| 167387720 fork 装配 | 普通 fork 创建 `Sfe()`；仅 shareSetAppState 显式共享父计数 | 撤销原草稿“整棵父子树强制共享根计数” |

## 本地重建源码的辅助用途

`/Users/czj/Repos/opensource-hub/claude-code` 中下列文件便于理解符号与完整依赖；该仓有既存工作区修改，不能以其当前文件冒充固定 2.1.267：

- `src/utils/permissions/denialTracking.ts`、`permissions.ts` 与 `src/utils/forkedAgent.ts`：辅助定位计数逻辑，关键归属已回到上述二进制验证。
- `packages/builtin-tools/src/tools/BashTool/{readOnlyValidation,bashPermissions,pathValidation,sedValidation}.ts`、`src/utils/shell/readOnlyCommandValidation.ts`：完整 Bash 迁移面。Python 实现需冻结与固定版本对应的命令/参数表及差分 fixture，不得只复制前缀表。

## 本次 Nano grounding

HEAD `d5f3183ba`，dirty workspace；仅修改本 unit 文档，未编辑产品代码。

- `RunOrigin` 到 hook 不等于每条历史消息来源；`runtime.py` 新 user metadata 目前主要是 submission_id/run_id，`prompting.py` / LLMMessage 不携带完整来源。global wake 的 HUMAN 和 child follow-up 的 USER 不能直接当真人。
- Inbox 已有唯一的 `to_auto_classifier_result` 实现；原始页面已经带 sender/type/target/id/partial，可继续使用该 seam。`conversations` 通过工具名判断不授予相同用户意图。
- `send_message` 参数与结果已有 target/text、ok/held/error；无需新增“已投递提议”实体。保持原状态，不把接受发送等同于已送达。
- Cron 实际 action 是 `list/add/update/remove/run/runs`，配置/持久化在 `.nanoassistant/cron/`；不要虚构 create/delete/get 等 API。当前 classifier payload 只取 240 字符摘要，迁移时要保留完整当前动作。
- Broker 当前按 run/tool 计数，更新为每个实际 session 的双计数；不引入根树锁。SDK 现有 metadata 可传全局交互选择，不需要新增公开 Approval DTO 或配置根。

设计审查、产品实现及 Nano 真模型验收均不是本页声称完成的工作。
