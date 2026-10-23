# M1 后端实施与验证

- 基线：`1ef49808ffd2618c275b6e38683f93f74ff8455d`，共享隔离 worktree `unit-bugfix-644`；仅修改 IM 后端与对应测试。
- 实施：新增 `/settings` 与 `/settings/sections/{plugins|cron|usage}`、持久有限投影；按 owner/node/binding epoch/workspace 隔离，RPC 后重新认证并检查连接对象及 profile version；旧成功 wire 不变，cron 未知不再返回空列表。新增配置、渠道、插件、cron 删除及 PA 设置写入使用真实连接门禁，已有 configuration operation 和 manifest 恢复保留。
- 未运行真实服务；此处是 HTTP 注入、真实 SQLite 与 Gateway binding 校验的后端证据，不代表生产部署或浏览器验收。

## 测试归属与 red

新增 `apps/im-server/tests/agent-settings.test.ts`：新设置读取协议、持久快照的授权/时效与全设置写入前置条件没有既有 owner，放在最低可观察的 Fastify HTTP + SQLite seam；复用 `control-fixture`，通过真实 Gateway `valid` 验证绑定。

首次执行收集失败：工作区 `@nano/product-contracts` 尚未构建，不计作 red。构建后同一测试 10/10 真实失败：新 settings 路由 404；离线 PATCH 创建 operation 并返回 503 pending，而要求 409 且无新 operation。随后实现并逐步扩大覆盖到 16 项。

已有覆盖处置：
- `control.test.ts` keep：durable apply/ACK 恢复、CAS 补偿和渠道生命周期风险继续由原测试负责。
- `approval-configuration.test.ts`、`plugins.test.ts` rewrite-merge：在线写入成功用例接入有效连接 fixture；保留在线检查之后 ACK 丢失的 pending 断言。
- `personal-agent.test.ts` rewrite-merge：原离线解除限制改为 409 且保留限制，再连接后解除成功；聊天中的屏蔽保护保持原行为。
- `personal-sources.test.ts` keep：节点内授权来源操作不受设置页新请求门禁影响。

## Green

Node `24.22.1`，命令前置 `PATH=/Users/czj/.npm/_npx/ef8b185be06dfeb4/node_modules/node/bin:$PATH`：

```sh
pnpm exec vitest run apps/im-server/tests/agent-settings.test.ts apps/im-server/tests/control.test.ts apps/im-server/tests/approval-configuration.test.ts apps/im-server/tests/plugins.test.ts apps/im-server/tests/personal-agent.test.ts apps/im-server/tests/personal-sources.test.ts
pnpm --filter @nano/im-server typecheck
git diff --check
```

结果：6 files / 61 tests 通过；后端 typecheck 通过，diff whitespace 检查通过。测试覆盖断线、替换连接、绑定 epoch、workspace/node 改绑、profile version、owner/space/session 撤销；分区安全投影、成功空列表与未知、timeout 保留旧快照；渠道全部新写入口无 revision/密钥/回执副作用；PA 离线改名/范围/解除限制拒绝；已接受配置恢复仍只提交同一 operation。
