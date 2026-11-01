# bugfix-689 配置编辑恢复的事后设计

本文依据 `7e79e9b79..071622c09` 的实际实现与测试整理。

## 请求与持久化

`configuration-assembly.ts` 为每个 IM context 提供一份 ConfigOperations。PA 改名、通用设置保存和既有后台恢复按同一 Agent 排队。PA 在队列内读取本次操作后的响应状态。

两个 PATCH 各自沿用现有表单到候选配置的转换。存在未确认操作时，`ConfigOperations.recoverEdit` 在恢复前按原 profile 构造本次候选。对于 apply，它检查原版本、提交版本（通用设置）、含服务端 PA 绑定的候选指纹及 IM 自有的描述。这样既可识别丢回执后的同一次重试，也能在 Gateway 规范化返回字段后作出判断。

- 同一次重试沿用原 operation ID 和回执，无二次写入。
- 另一笔操作恢复成功或已明确拒绝后，当前请求重读 profile，按原有版本、在线和写入规则执行。
- 回执仍无法确认时保留原操作，返回既有待确认结果。通用设置遇到过期版本仍返回冲突。PA 改名没有客户端版本字段，排在前面的写入完成后以最新 profile 保存。

持久化记录、协议、客户端与配置应用链均沿用原实现，无数据迁移。回退 IM 代码即可回到旧行为，也会重新暴露此并发缺陷。当前配置契约已要求成功响应反映持久值、过期版本被拒绝、未确认操作可恢复，本修复纠正实现偏差，无新增公开契约。

## 前后证据

同一场景见 `apps/im-server/tests/configuration-edits.test.ts`。基线用该文件的复现用例得到 B 的 200 / A。修复后 A 获得 200 / A，B 得到 409 版本冲突，SQLite 保存 A（版本 2）。按版本 2 提交 B 后得到 200 / B，SQLite 保存 B（版本 3）。

在隔离 worktree、Node 24.22.1 下执行：

```sh
pnpm exec vitest run --maxWorkers=2 apps/im-server/tests/{configuration-edits,control,personal-agent,configuration-boundaries,agent-settings}.test.ts
```

5 文件、73 项通过，覆盖上述并发顺序、待确认、原操作重试、仅描述不同、版本不同及另一笔被节点拒绝后的新提交。既有用例覆盖恢复时的 profile、绑定和会话标题一致性，以及冲突补偿。

验证通过真实路由和 SQLite，节点回执由测试控制。无生产、真实节点、浏览器或用户亲测记录。
