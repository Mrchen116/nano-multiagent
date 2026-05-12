<!--
模板说明（定稿后删除本块）

产品视角验收。问"用户拿到这版能干成事吗"，不是"测试是否通过"。
真实走用户旅程，记看到/听到/触碰到的体验，而非代码路径。

发现的问题按严重度处置：阻塞 → 在本 unit 内补；非阻塞 → 开 bugfix lite。
-->

# <type-id> — 验收报告

> 对齐: spec.md / motivation.md 的验收标准

## Verdict

<!-- pass / fail / pass-with-issues -->

## 用户旅程体验

<!-- 主路径 + 边界路径，截图/录屏/对话粘贴。 -->

## 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| 1 |  |  |  |

## 验收标准覆盖

<!--
逐条复制首文档的验收标准。结果只能是 pass / fail / inconclusive / not-applicable。
第 2 轮起必须继承上一轮所有 fail / inconclusive 项,直到有证据关闭。
任一必验项 fail 或 inconclusive 时,Verdict 不能是 pass。
-->

| ID | 验收项 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| A1 | <从 spec.md 复制验收标准> | <真实入口/操作步骤/替代验证理由> | <截图/日志/输出/报告位置> | pass / fail / inconclusive / not-applicable |  |

## 行动账本

<!--
必填。按桶分类列出本轮 reviewer 做的所有动作 + 工具调用次数 + 关键时间点。
让 orchestrator 一眼判断行为是否健康(例如读源码比例 / 是否发生 SHELL_MUTATION)。
跨 session 的也要标注。
-->

| 桶 | 计数 | 关键内容 |
|---|---|---|
| READ(文档/源码) |  | 列文件名,源码只允许单次例外引用 |
| START_SERVICE / RESTART_SERVICE |  | 见 §环境声明 |
| BROWSE / INVOKE(用户旅程) |  | 主要入口/操作 |
| CAPTURE(取证) |  | 截图/抓帧/日志摘取 |
| SHELL_MUTATION(改机器状态) |  | kill / 写 /tmp / 启停进程 |
| SENDMESSAGE 给 orchestrator |  | 次数 + 简述 |

## 环境声明

<!--
必填。reviewer 本轮启动/重启的服务清单 + 占用资源 + 留下的临时文件。
让下一轮 reviewer 或 fix worker 接得上,不踩坑。
-->

| 服务 | 动作 | PID | 端口 | commit hash |
|---|---|---|---|---|
|  | started / restarted / killed |  |  |  |

留下的临时文件 / 占用端口 / 后续 reviewer 需要知道的状态:

- 

## 上层文档同步

<!--
本 unit 是否需要回头更新项目级文档？验收阶段必须显式检查，避免知识游离。
不需要改的文档也要勾"无需更新"，证明检查过。
-->

- [ ] `SPEC.md`（架构总览）：__需要更新 / 无需更新__
- [ ] `docs/内核设计SPEC.md`（agent 内核）：__需要更新 / 无需更新__
- [ ] `AGENTS.md` / `CLAUDE.md`：__需要更新 / 无需更新__
- [ ] 相关产品 SPEC（CodingCLI / NodeGateway / IM 等）：__需要更新 / 无需更新__

需要更新的，列出 PR/commit 链接。
