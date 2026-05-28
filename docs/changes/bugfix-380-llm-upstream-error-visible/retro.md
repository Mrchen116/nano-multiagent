# refactor-381 复盘:bugfix-380 为什么做了 4 个多小时

> 来源:bugfix-380(LLM 上游错误用户可读)PR #53。spec / design 写得相对清楚,M1 实施代码量也不大(~400 行 src + 1100 行 test),但从 spec 写完到 PR 提交经历 4 小时 15 分钟。本文用本次 session 的 jsonl 实测数据复盘,目的是把可工程化的瓶颈钉死成下一个 unit(refactor-381)的工作清单。

---

## 1. 时间分布(jsonl 实测)

按 subagent jsonl 文件起讫 timestamp 还原:

| 时段(UTC) | 角色 | wall-clock | 产出 |
|---|---|---|---|
| 03:35 → 04:10 | 我(spec + design + orchestrator setup) | ~35 min | incident.md / design.md / unit branch |
| 04:10 → 04:30 | worker-M1 | **19 min** | M1 实施 ~400 行 src + TDD 5 个 roadpoint |
| 04:31 → 04:41 | verifier-r1 round 1 | **10 min** | verdict=pass + 2 WARNING(缺测试) |
| 04:32 → 05:12 | reviewer-r1 round 1 | **40 min** | 起服务走旅程 → 抓 SOCKS 干扰 |
| 05:01 → 05:12 | fix-worker-r2 round 1 | **11 min** | trust_env + HTTP/transport 14 条新测试 |
| 05:12 → 05:51 | reviewer-r1 round 2 | **39 min** | 抓 SSE 事件顺序 bug |
| **05:54 → 07:45** | **fix-worker-r3 反复 3 轮 + reviewer 复验** | **1h 51min** | round 3 v1 / rev2 / rev3 |
| 07:45 → 07:54 | 我接管 | **9 min** | code review + 端到端 curl 验 + 提 PR |
| **总计** | | **~4h 15min** | PR #53 |

**主要时间黑洞**:fix-worker-r3 反复 3 轮占 50% (1h 51min)。worker 被唤醒 4 次(对应 4 个 jsonl 累计 9.5 MB),reviewer 被唤醒 6 次。

---

## 2. fix-worker-r3 那 1h 51min 实际花在哪

`agent-a03a1eec45fcd42ff.jsonl`(3.2 MB,1333 events)是 worker 最终生命周期累积。tool_use 计数:

- bash: 407 次
- read: 65 次
- edit: 15 次
- write: 6 次
- **其中服务起停 / e2e 排错相关:108 次**

进一步看 35 次失败 bash 输出的归类:

| 失败类型 | 占比 | 根因 |
|---|---|---|
| Gateway 单例锁互撞(`gateway is already running pid=...`)反复 4-5 次 | ~40% | **AGENTS.md PID 范式 vs 启动器内部 PID 范式不一致**(详见 §4) |
| fixture provider 桩协议试错(httpx chunked encoding / transport vs SSE event 帧格式) | ~30% | **项目无 ready-made fixture 桩**,worker 自己复现 anthropic `event: error\ndata: {...}` 双行 SSE 帧,试 5 个版本才对 |
| LLM env var 名错(`LLM_BASE_URL` vs `NANO_MULTIAGENT_LLM_BASE_URL`)被卡 30+ 分钟 | ~15% | **文档没在显眼位置写真名**,要翻 `LLMFactoryConfig.from_env()` 才能确认 |
| 其它(`timeout` 命令不存在 / `workspace_root` 没 mkdir / config YAML 顶层 list vs dict / IM node binding 拦路) | ~15% | worker 经验缺口 + 文档缺口混合 |

**真正改源码 + 写测试只占 35% wall-clock(~45 min)**。剩 65% 是 e2e 环境搭建 + 排错的隐性成本。

每次 worker wake 都要重做一遍:

1. kill 旧 .pid + 等进程死透
2. 起 IM uvicorn(裸的 OK)
3. 起 Kernel API uvicorn(裸的 OK)
4. 拷主 config 到 worktree 副本 + yq 改 `node_id` / `im_service.url` / `workspace_root`
5. mkdir 各 workspace_root 子目录
6. 起 Gateway(必须用启动器,不能裸 uvicorn,因为它**不是** ASGI app)
7. Gateway 首次连新 IM 时 IM 要求 node binding,要么手点 URL 要么写脚本调 `/im/v1/nodes/bind/confirm`(没文档)
8. 起 fixture SSE error server(自己写桩)
9. 配 `NANO_MULTIAGENT_LLM_BASE_URL` env var 指向 fixture port
10. 起 coding-cli managed API(可选)
11. curl 拿 token + sender_user_id + 真实发消息
12. 验证 /messages 响应

这套 12 步没有任何自动化,每个 worker / reviewer / 自己手起 e2e 全部从零抄一遍。

---

## 3. worker-M1 为什么没一次做对

worker-M1 实际表现**没问题**:19 分钟跑完 TDD 5 个 roadpoint,提交时全套 2333 passed。后来 reviewer 反复抓的 3 个 bug 都**不在 worker 自由发挥的空间里** —— 它们是 design.md 描述中未被验证的乐观假设。

具体看 design.md 当时怎么写的:

> 决策 1:"...通过现有 `message_end` 钩子链路**自动转成** SSE `assistant_message` 事件。"

> 风险 R3 对策:"runtime 同步先 dispatch hook 再 raise,registry 在 `_mark_failed_async` 才发 run_error。**同进程顺序由 Python 语义保证**。对策:M1 worker 加端到端测试(mock provider 强制 SSE error → 断言 IM messages API 既能看到错误内容,delivery_status 也是 failed)。"

这两句话埋了 **3 个未被验证的跨层契约假设**:

1. ❌ **"hook 链路自动转成 SSE 事件"** — 实际:`realtime_stream.on_message_end` 的 `_extract_run_id` 早返回,需要 `payload['run_id']`。runtime.except 块新调用 `_dispatch_observe("message_end", ...)` **忘了带 run_id** → 事件被 hook 静默丢弃。round 3 rev2 抓到。

2. ❌ **"同进程顺序由 Python 语义保证"** — 实际:Gateway `_await_terminal_run_async` 看到 `run_status=failed` 就 `raise RuntimeError` 退 SSE 循环,后续 buffer 里的 `assistant_message` 根本不被消费。Python 顺序对的没用,**Gateway 侧的提前 raise 把整个保证废了**。round 3 rev2 第二条修法。

3. ❌ **"delivery_status=failed 也"** — 实际:`IM.event_bridge.on_message_completed` 硬编码 `delivery_status="completed"`,**根本没有把 agent 气泡标 failed 的入口**。`delivery_receipt(failed)` 只标用户消息。round 3 rev3 核心修法。

这 3 个 bug 共同点:**都是跨层契约假设**。design 列了 5 层要改,但每层都说"**复用现有链路**"。**失败路径在每条链路上都有自己的边界条件**,design 没逐层 trace 过 —— 因为我当时也没真起服务跑一遍。

worker 按 design 写的"复用"做了,设计文档的"M1 集成测试"是 `AgentRuntime.run() → manager.list_turn_messages()`,**绕过了 Gateway observer + IM event_bridge 链路**,这条才是真正出 bug 的地方。worker 写的测试全绿,但端到端不通。

**归因**:
- **planning/design ~75%**:我没真起一次完整链路 trace 失败路径,把跨层契约假设当不证自明
- **worker 理解 ~10%**:本可以多走一层 Gateway observer 自验,但没这义务
- **orchestrator 决策 ~15%**:reviewer 抓 bug 后,我每次只让 fix-worker 修最新发现的那一层,而不是早一轮让 worker 完整 trace 整条链路

---

## 4. Gateway PID 范式冲突的具体证据

bugfix-380 期间最反复的失败模式是这个,值得单独记录。

**AGENTS.md "PID 文件 + 退出清理" 段教的范式**:

```bash
PYTHONPATH=src python -m personal_assistant.main --config ... \
  > .gateway.log 2>&1 & echo $! > .gateway.pid       # 带点的 .gateway.pid

for f in .im.pid .gateway.pid .vite.pid .coding-cli.pid; do
  [[ -f $f ]] && kill "$(cat "$f")" 2>/dev/null; rm -f "$f"
done
```

**启动器 `personal_assistant.main` 实际行为**(`src/personal_assistant/main.py:2139`):

```python
def _gateway_pid_path(config: LocalConfig) -> Path:
    return config.source_path.parent / "gateway.pid"   # 不带点的 gateway.pid
```

启动时 `_write_gateway_pid()` 写**自己的进程 pid**(`os.getpid()`),启动前 `_read_gateway_pid()` 检查单例,撞了报 `gateway is already running (pid=N)`。

**两套 PID 文件互不知道**:

| 谁写 | 文件名 | 路径 | 里面的 pid |
|---|---|---|---|
| worker(按 AGENTS.md `& echo $!`) | `.gateway.pid`(**带点**) | `$WT_ROOT/.gateway.pid` | shell job pid |
| 启动器内部 `_write_gateway_pid` | `gateway.pid`(**无点**) | `$WT_ROOT/gateway.pid`(config 同目录) | 启动器真实主进程 pid(`os.getpid()`) |

worker 按 AGENTS.md 操作:
1. `kill $(cat .gateway.pid)` —— 杀了 shell job pid(可能不是真正监听端口的进程)
2. 立刻 restart —— 启动器读 `gateway.pid`(无点)文件 → **里面 pid 还在**(或文件还在但 pid 已死),启动器**误判为另一个实例还在跑** → 报错拒绝启动
3. worker 莫名其妙(我刚 kill 过),又 kill 又 restart,**再撞**
4. 循环若干次,最终发现要用启动器自己的 `python -m personal_assistant.main stop` 或 `rm gateway.pid`(无点)才能彻底逃出来

jsonl 里 `pid=89375` 就是启动器自己写在 `gateway.pid`(无点)里的内部 pid,跟 worker `echo $!` 抓到的 pid 完全不是一个数。

**根本病因**:

- AGENTS.md 给的"统一 pid 范式"假设所有服务都是**裸 uvicorn**(IM 这样,所以 IM 那条 OK)
- 但 Gateway **不是**裸 uvicorn,是一个 wrapper 启动器:
  - 不是 ASGI app(`personal_assistant.main` 不能塞给 uvicorn 跑),它是一个进程主管,内部 spawn IM WebSocket client / kernel API uvicorn / heartbeat scheduler / run_queue 等多个 worker
  - 命令行设计上是给"用户手起的工具",有 `stop` / `restart` 子命令 + 单例保护,**内部自管 PID** 是这套用户体验的必然产物
  - 类比:IM 像 nginx(干净 daemon,外部进程管理工具说了算);Gateway 像 docker daemon(supervisor 模式,自己管别人,也自管 PID)
- AGENTS.md 把这两类服务混在一起教统一范式 → 外部脚本 vs 启动器内部范式打架

---

## 5. 改进路线(refactor-381 工作清单的种子)

按 ROI 排:

### 小动(零功能改 / 一周内)

1. **`scripts/e2e-up.sh` / `scripts/e2e-down.sh` 一键起停**
   - 自动 `scripts/free-ports.sh` 分配端口
   - 拷 config + yq 改字段 + mkdir workspace_root
   - 顺序起 IM → Kernel → Gateway,做健康检查
   - echo 出 `IM_PORT=... API_PORT=... GW_PORT=...` 供后续 curl 用
   - 可选 `--fixture-provider sse-error` 启动桩
   - worker / reviewer / 自己**零认知**起 e2e

2. **AGENTS.md 范式分类整理**
   - 显式说明"裸 ASGI 服务"(IM、Kernel API)走通用 `& echo $! > .pid` + `kill $(cat .pid)`
   - "wrapper 启动器"(Gateway)必须用启动器自身命令(`stop` / `restart`)
   - 给两类服务各贴一个范式 snippet,worker 直接抄

3. **`scripts/fixtures/` 入仓**
   - `anthropic_sse_error.py`:正确的 `event: error\ndata: {...}` 双行 SSE 帧
   - `openai_compat_error.py`:top-level `{"error":{...}}` 帧
   - `http_429.py` / `http_500.py` / `slow_stream.py` 等
   - 配套 README:env var 写法 + 端口约定

4. **IM node binding 加 `--auto-bind` flag**(或 IM 侧 env var)
   - Gateway 启动可加 `--auto-bind` 自动调 `/im/v1/nodes/bind/confirm`
   - 移除"e2e 环境下还要人手点 URL"的拦路虎

5. **AGENTS.md 加 `NANO_MULTIAGENT_LLM_BASE_URL` 等关键 env var 名表**
   - 当前 env var 真名要翻源码,bugfix-380 rev2 被这卡 30 分钟

### 中动(架构调整 / 1-2 周)

6. **Gateway 启动器去掉自管 PID + `stop` / `restart`,只保留 `--foreground`**
   - 12-factor app 第 9 条 "Disposability":自管 vs 外管二选一,选外管最朴素
   - 改完所有服务都是 `& echo $! > .pid` + `kill $(cat .pid)`,范式真统一
   - 影响面:用户手起命令习惯变(失去 `python -m personal_assistant.main stop` 的 CLI 便利);可以包一个 `scripts/gw.sh stop` 兼容

7. **`docs/事件契约.md`** 写流式 SSE event lifecycle
   - bugfix-373 / bugfix-375 / bugfix-380 都踩同一区域的隐式契约
   - 必须列:谁可以发哪些 event;event 之间合法顺序(状态机);每个 event 的 payload schema(强调失败模式下哪些字段必填如 `run_id`);consumer 契约(看到 terminal 后是否继续读 buffer)
   - 不写文档,下次再有人改流式行为要再踩一次坑

8. **Gateway 内部 supervisor 职责拆分**
   - 当前一个进程塞了:IM channel relay + Kernel uvicorn(可能 spawn 子进程)+ Heartbeat + Background hooks + run_queue
   - 拆成:Gateway 主进程只跑 channel relay + run_queue;Kernel 用独立 `python -m uvicorn`(本来就支持);Heartbeat 拆 `python -m personal_assistant.heartbeat`
   - 每个进程都是 ASGI app 或简单 daemon,12-factor 标准化

### 大动(暂不建议短期做)

9. **彻底取消 Gateway 进程实体**:IM 直接调 Kernel API,Gateway routing 逻辑做成 Kernel mount path 或 IM 插件;Heartbeat 独立 cron;Background hooks Kernel 自管。系统拓扑变 2 个 ASGI app + 1 cron,全部 12-factor。**3-4 周重构,需要产品迭代窗口配合**,不是 quick win。

---

## 6. 元教训(对后续 unit 都通用)

1. **"复用现有链路"在 design.md 里不是结论,是假设**。任何说"复用 X"的决策必须配一个跨层 trace —— 把这条链路在**失败模式**下从源头走到用户感知点,逐 hop 列出 payload 字段、consumer 契约、状态机边界。本次没做这个 trace,直接把 3 个跨层契约假设埋进 design,worker 按字面意思实施完全没毛病。

2. **subagent 报"DONE"必须有不可绕过的端到端硬要求**。worker 给的"单测+集成测试 2333 passed"在跨进程 SSE/observer 路径上是**假阳性**,reviewer round 1/2/3 三次抓到的都是单测覆盖盲区。下次 design.md 写退出标准时,`[reviewer]` 轨条目必须含**真起服务的 curl 断言**,不能只写 "覆盖 incident.md 全部 Scenario"(太抽象,worker 测试范围里"等价"自己就能糊弄过去)。

3. **reviewer 反复抓 bug 时(>2 轮),orchestrator 早点亲自接管做端到端 trace**,不要再派一轮 worker。本次用户在 07:45 接管让我亲手做最后一步,9 分钟提 PR;之前每轮 subagent 来回平均 30+ 分钟。**协调税在小任务上比工作本身贵**,中后期单点突破远比"再派一个 worker"快。

4. **小到中型 bugfix(< 500 行)不该走完整 orchestrator → worker → verifier → reviewer 流程**。这套流程的协调税对小任务是负价值。流程价值在跨 milestone / 跨模块 / 需要并行的真大 unit 上。bugfix 380 量级的应该有个"轻量轨"。
