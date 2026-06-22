# feat-421-M3: fix-round1 — Tasks

> 验收 round-1 三道闸（verifier / reviewer / code review）合并去重后的 fix 清单。
> reviewer 反馈循环小修快车道（复用 M2 worker 上下文）。

## 目标

修掉验收 round-1 暴露的 BLOCKING（CI/验收红）+ CORRECTNESS + CLEANUP 问题，让本 unit 满足
退出标准；heartbeat marker（skip→xfail）挂起等用户定 A/B（产品前缀=#126 另修）。

## 退出标准

- [x] contract `test_new_test_files_under_400_lines` 绿（所有新测试文件 ≤400 行）
- [x] `scripts/e2e-critical.sh` 全套绿（12 passed + heartbeat 1 xfailed，slow 子集正常）
- [x] 全树 ruff clean
- [x] 新增 subagent 失败隔离测试真端到端跑绿（live 证据）

## fix 清单 ↔ 落点

| # | 类别 | fix | 落点 | commit |
|---|---|---|---|---|
| 1 | BLOCKING | 拆 `_im_client.py`（552>400）+ 消重轮询 | `_im_client`(369)/`_im_ws`(165)/`_im_gateway`(120)/`_im_polling`(68)；`poll_until`+`assert_absent_within` 统一 5 处同构轮询 | 10ebf5a3 |
| 2 | BLOCKING | heartbeat skip→xfail(strict,#126) | `test_heartbeat_bubble_critical_path.py`（用户拍板 B：只测不改产品）。env off→SKIPPED（门控 fixture skip 先于 xfail）；env on→XFAILED（真跑 184s 验证） | e23b982c |
| 3 | BLOCKING | 补 subagent 失败隔离 e2e | `test_subagent_failure_isolation_critical_path.py` + catalog #4 行 | 10ebf5a3 |
| 4 | BLOCKING | M2 tasks.md 退出标准勾 [x] | `M2-remaining-paths/tasks.md` | 10ebf5a3 |
| 5 | CORRECTNESS | `_drain_one` 补捕 ConnectionClosedOK/Error | `_im_ws._drain_one` | 10ebf5a3 |
| 6 | CORRECTNESS | `restart_gateway` killpg（杀进程组） | `_im_gateway._terminate_process_group`（仅独立组长 killpg，非组长退单 pid 避免误杀 pytest 组） | 10ebf5a3 |
| 7 | CLEANUP | conftest teardown 检查 e2e-down.sh rc | `conftest.py` teardown，非零 WARN | 10ebf5a3 |
| 8 | CLEANUP | cron 无效「等 feature 同步」no-op 循环删除 | `test_cron_push_critical_path.py` + 注释说明 | 10ebf5a3 |

可选 polish（`_live_proxy_available` 抽共享 / 收窗口）：**判断不做**——前者 scope 外（fix 包明言别为它扩 scope），后者真 LLM 固有慢可接受，收紧收益低于 flake 风险。

## 测试策略

- 重构（拆文件 + 消重 + 异常捕获）：行为不变，靠现有 13 条 e2e + contract 400 行守护。
- 新增 subagent 失败隔离：live e2e，真派失败子 agent + 后续消息正常处理双锚。
- killpg 改动：易引入「误杀 pytest 进程组」回归（实测过 exit 144），靠重启续接 e2e 真跑守护。
- 落层/marker：`tests/e2e/critical_paths/`，marker `e2e`（新增隔离测试非 slow）。
