# refactor-381: e2e workflow 工程化

> 来源:`bugfix-380-llm-upstream-error-visible/retro.md`(commit f665324d)。bugfix-380 PR #53 实测,worker/reviewer 起 e2e 环境的 12 步散文流程,在反复 wake 中累计消耗 65% wall-clock,改代码只占 35%。本 unit 把 retro §5 的"小动 1-4"做掉。

## 现状痛点(从 retro 摘要)

每次 worker / reviewer / 自己手起 worktree e2e,都要重做这 12 步:

1. kill 旧 .pid + 等进程死透
2. 起 IM uvicorn
3. 起 Kernel API uvicorn
4. 拷主 config 到 worktree 副本 + yq 改 `node_id` / `im_service.url` / `workspace_root`
5. mkdir 各 workspace_root 子目录
6. 起 Gateway(必须用启动器,不能裸 uvicorn)
7. **Gateway 首次连新 IM 时 IM 要求 node binding,要么手点 URL 要么写脚本调** `POST /im/v1/bind`
8. 起 fixture provider(自己写桩,试错 anthropic SSE 帧格式)
9. 配 `NANO_MULTIAGENT_LLM_BASE_URL` env var
10. 起 coding-cli managed API(可选)
11. curl 拿 token + sender_user_id + 发消息
12. 验证 /messages

具体证据:bugfix-380 fix-worker-r3 一次 wake bash 407 次,其中**服务起停 / e2e 排错 108 次**。35 次失败按归因 ~40% Gateway 单例锁互撞 / ~30% fixture 协议试错 / ~15% LLM env var 真名找错 / ~15% 其它经验缺口。

## 本 unit 范围

retro §5 小动清单的 1-4 条:

1. **`scripts/e2e-up.sh` + `scripts/e2e-down.sh`** 一键起停 IM+Kernel+Gateway,自动分配端口、改 config、健康检查、写 `.e2e-ports.env` 供后续 curl 用。脚本里**不**带 fixture provider flag —— fixtures 是独立工具(item 3),由调用者按需另起。
2. **AGENTS.md PID 范式分类整理**:显式区分"裸 ASGI 服务"(IM、Kernel API,通用 `& echo $! > .pid` 范式)vs "wrapper 启动器"(Gateway,必须用启动器自带命令 / 或 --foreground + 外部 pid 文件)。给两类各贴一个完整 snippet。
3. **`scripts/fixtures/` 入仓**:`anthropic_sse_error.py`、`openai_compat_error.py`、`http_429.py`、`http_500.py`、`slow_stream.py` 等小 HTTP 桩(各 ~30-50 行)+ README 讲端口和 env var 写法。
4. **Gateway 加 `--auto-bind` flag**:启动时自动调 `POST /im/v1/bind {action:start}` 拿 bind_url → 解 token → 调 `{action:confirm,bind_token}` → 完成绑定,不等人手点 URL。worktree e2e 默认应该用这个。

## 非目标

- retro §5 中动 5-8 不在本 unit(NANO_MULTIAGENT_LLM_BASE_URL 文档化、SSE 事件契约文档、Gateway 拆 supervisor)。
- retro §5 大动 9(取消 Gateway 进程实体)不在本 unit。
- Gateway 启动器砍掉自管 PID + stop/restart 子命令(retro §5 中动 6)不在本 unit —— 那是 backward-incompatible 改动,需要单独走 spec 流程评估对用户手起命令习惯的影响。本 unit 只在 worktree e2e 路径上**绕开**自管 PID 的痛点(用 --foreground + 外部 .pid)。

## 验收

- `scripts/e2e-up.sh` 在空白 worktree 里跑能拉起完整 IM+Kernel+Gateway 三件套,echo 出端口,健康检查通过
- `scripts/e2e-down.sh` 干净停掉,无残留进程 / pid 文件
- AGENTS.md 改完后,新人按文档抄命令起 e2e,不会撞 Gateway 单例锁
- `scripts/fixtures/anthropic_sse_error.py` 起来后,kernel 配 `NANO_MULTIAGENT_LLM_BASE_URL` 指过去,触发 retryable=False 的 ModelError(不走 20 次重试)
- Gateway `--auto-bind` 启动时不再打印 "waiting for IM binding URL",`POST /im/v1/bind` 在启动流程内完成

## 实施

不走 worker / verifier / reviewer 全流程 —— 这是个工程化 unit,改动可分割性高 + 没有跨层契约假设,直接实施。

单 PR,合到 main。
