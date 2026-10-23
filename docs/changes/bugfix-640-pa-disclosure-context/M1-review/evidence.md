# M1 实施与验证

## 基线与隔离

- Gate 2：R1 Approved，0 CRITICAL / 0 WARNING；设计没有实质变化。
- executed_base：`9600bf3b16929fa411bb6956909c5df9777b5c3a`。
- 实施分支：`unit/bugfix-640`；使用 Codex 托管 worktree `/Users/czj/.codex/worktrees/bugfix-640-pa-disclosure/nano-multiagent`，替代手工 `.worktrees` 路径，隔离契约相同。
- Node 24.22.1、pnpm 11.7.0；主仓既有修改未纳入。
- 私有运行证据：`/tmp/nano-pa-review-640/`，不提交原始聊天、配置、日志和 token。

## 测试策略与已执行结果

- 旧版失败：扩展现有 `apps/im-server/tests/personal-disclosure.test.ts`，在无关群增加 32 条长消息后，待审 evidence 含 `UNRELATED_PRIVATE_HISTORY`，新断言失败。命令 `pnpm exec vitest run apps/im-server/tests/personal-disclosure.test.ts -t 'independent of unrelated'`；本机 `red.log`。这是 IM 证据来源的最低验证层。
- 改后同文件 15 个测试通过；既有受众、来源、附件、版本、主人更正、共享任务、渠道回执和幂等测试继续保留。旧 guard 全文断言改为当前固定指纹，不再要求把授权库注入审核正文。
- 扩展现有 Codex budget/lifecycle 与 approval-sources 测试，覆盖完整私有材料、预算缺失标记、严格四态 parser、独立缓存、增量和上下文替换。复用既有 native 测试保护共享执行器，不新建平行执行器测试。
- `personal-child-delivery.test.ts` 保留真实 DSH 子执行范围，改为核对宿主 sessionId 和真正 reviewer 输入，消息/共享任务均经独立检查。接线初验发现 Cordis 服务需显式 inject，已按现有 service promise 方式修正；测试 fixture 改用原生 reviewer session 身份识别模型调用。
- 输入分类继续走原来的独立小调用，输出披露改用同一 Codex lifecycle。

## 真聊天种子边界

- 源材料：只读生产 DM `c_kuthz6vx`、群 `c_fqyj3bvq` 当天必要消息；原副本 17,121 bytes，权限 0600。
- 重放截止 `2026-10-23T04:28:00.810Z`，最终授权原话“直接放行吧，你帮我去发”；排除之后主人自行处理的消息。
- 创建新的隔离主人、PA、群和不会执行清理的测试参与者。历史作者映射与授权入口在验收记录中明确，不伪造生产发送成功。
- 本次只验证代发；不执行原文中的文件清理，不连接生产渠道。
