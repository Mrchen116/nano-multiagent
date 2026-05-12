<!--
模板说明（定稿后删除本块）

bugfix full 的回归验证报告。bugfix milestone 完成后写。
-->

# <bugfix-id> — 回归验证

> 对齐: incident.md

## Verdict

<!-- pass / fail -->

## 复现验证

<!-- 修前能复现的步骤 → 修后跑同一步骤不能复现。给证据。 -->

## 回归测试

<!-- incident.md 影响范围内的相关功能仍正常。 -->

## 自动化测试增量

<!-- 新增的单测/集成/e2e，覆盖什么场景，防什么回归。 -->

## 行动账本

<!--
必填。按桶分类列出本轮 reviewer 做的所有动作 + 工具调用次数。
让 orchestrator 判断行为是否健康。
-->

| 桶 | 计数 | 关键内容 |
|---|---|---|
| READ(文档/源码) |  | 列文件名,源码只允许单次例外引用 |
| START_SERVICE / RESTART_SERVICE |  | 见 §环境声明 |
| BROWSE / INVOKE(复现/回归) |  | 主要入口/操作 |
| CAPTURE(取证) |  | 截图/抓帧/日志摘取 |
| SHELL_MUTATION(改机器状态) |  | kill / 写 /tmp / 启停进程 |
| SENDMESSAGE 给 orchestrator |  | 次数 + 简述 |

## 环境声明

<!--
必填。reviewer 本轮启动/重启的服务 + 留下的临时文件 / 端口占用。
-->

| 服务 | 动作 | PID | 端口 | commit hash |
|---|---|---|---|---|
|  | started / restarted / killed |  |  |  |

留下的临时文件 / 端口 / 后续接盘者需要知道的状态:

- 

## 上层文档同步

<!-- bug 修复偶尔会牵动架构假设；显式检查。无需更新也要勾，证明检查过。 -->

- [ ] `SPEC.md`：__需要更新 / 无需更新__
- [ ] `docs/内核设计SPEC.md`：__需要更新 / 无需更新__
- [ ] `AGENTS.md` / `CLAUDE.md`：__需要更新 / 无需更新__
- [ ] 相关产品 SPEC：__需要更新 / 无需更新__

