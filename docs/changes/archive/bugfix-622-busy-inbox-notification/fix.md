# bugfix-622: 恢复工作中 Inbox 新消息提醒

## Relations

- Related: refactor-581

## 原始报告

> 比如开始做一个大任务，我中途发现问题，给他指正，那肯定要尽快收到吧，而不是等他干完了啊
>
> 自动把纠正内容及其来源放进上下文，这也不对，应该是收到新消息的提醒，跟之前一样
>
> 然后之前的“发送前复核”，当然保持不变
>
> 改了这个问题，这是重构成DSH引出的bug

## 现象 / 复现

全局 Agent 正在执行任务时，用户追加更正。消息已存入 Inbox，但工作中的后续 LLM 请求没有新消息提醒；只有主 Agent 回到 idle 才收到通知，或发送前复核拦截后才发现未读。

预期：符合现有接收/触发配置的新输入，在主 Agent 下一次 LLM 请求前进入上下文的仅是系统提醒。正文和真实来源仍由 Inbox check/read 摄取。不得硬中断当前模型请求或正在执行的工具；空闲唤醒、背景消息策略、持久摄取和发送前复核保持。

## 根因

DSH 迁移提交 `129b083613`（refactor-581）引入的 `GlobalAgent.wake` 在 `session.observe` 状态非 idle 时直接返回，只有 idle 时提交 followup。未将忙碌时通知接到 DSH 的下一 step 调度入口。既有 attention 测试反而断言 running 时没有 submit，因此未保护这一回归。

原迁移 design 要求改接 Inbox 与摄取、保留产品业务规则，不重新设计收发语义。current global-agent 契约要求忙碌时不强制中断并允许自主读取，但没有明确下一次模型请求前提醒，需补齐这项可观察时效契约。修复保留系统通知不代表真人授权、显式读取正文、完整持久摄取后消费，以及原发送前复核边界。

## 修复

使用 DSH 公开 steer 调度系统提醒，移除仅 idle 才提交的限制。沿现有 watermark 和幂等 inputId 提交；提交期间到达的新输入继续排入提醒，不等下次 idle。正文、来源、personal 提醒附加说明、attention 过滤和发送前复核保持原逻辑。

## 验证

修前：更新后的 attention 用例有 2 个失败；真实 DSH 子进程用例显示下次模型请求仍只有 1 条提醒，期望 2 条。修后：两个测试文件共 37 个用例通过，覆盖忙碌提醒、连续到达及去重、空闲唤醒、背景过滤、只提醒不注入正文、原发送前复核。

扩展 global-agent.test.ts 保留产品协议与 attention 策略保护；新增 apps/node/tests/global-inbox-native.test.ts 在节点集成层连接真实 PA、SQLite Inbox 与锁定版本的 DSH 子进程，以确定性的模型 fixture 观察实际模型请求，验证 next-step 时机、正文读取与旧稿拦截。它保护跨进程调度接线，不替代真实模型或生产验证。

验证基线：origin/main `793c68472`；修复版本 `d7518ebd7`。

- `pnpm build`、`pnpm typecheck` 通过。
- `pnpm test`：450 通过，workspace-tools 原生插件测试一次 90 秒超时；该单文件独立复跑通过（34.25 秒）。未将此结果声明为首轮全绿，未修改无关测试或放宽 timeout。
- 前端 `npm ci`、critical audit 与 100 文件 / 936 测试通过；audit 仍报告 5 个既有 low 项。
- `docs-check`、Python 非 E2E 62 项、ruff check/format 通过。Python 工具使用主仓已有 .venv，默认 python 缺少 PyYAML 的初次启动未执行检查。
- 独立 change-code-review 全差异审查 `[]`，见 code-review.md；归档只改变文档位置和验证记录，保留代码审查。

证据边界：真实本地 DSH 子进程和确定性模型 fixture 已验证，未执行真实外部 LLM、生产部署或设备验收。
