# 目录重建与长时读取证据

被测后端源码：`bf0cdfdc32df872c9c40a0461c8284652d142d2f`，Node 24.22.1 / 锁定 DSH 0.2.1-alpha.1，macOS Air。本地构建、独立验收报告提交不改变该源码。使用隔离 daily 实例；未操作生产、未发送模型请求。

## 100 次实际重建

命令：`PATH="$HOME/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH" node /tmp/refactor-682-refresh.mjs`。脚本逐次调用真实 ConfigurationInspector，使用独立随机临时 home，不走 IM 缓存；每次等待 worker 释放后检查 root 与活动数。运行时无全量测试负载。

| 指标 | 结果 |
| --- | --- |
| 实际重建数 | 100，全部成功 |
| p95 / 最大耗时 | 1320 / 1699 ms |
| 每轮检查结束时目录 | 100 轮均为空 |
| 最终活动 worker / 错误 / 超时 | 0 / 0 / 0 |
| 每次目录工具数量 | 39 |
| inspector owner RSS 首 / 末 / 最大 | 58,130,432 / 68,370,432 / 68,714,496 bytes |

最后 25 次构建的 owner RSS 为 65.2–65.5 MiB。owner RSS 包括 Node/V8 的进程内开销；这里不声称任意时长或其他负载下绝无内存泄漏。临时 home 已在 finally 清理。原始结果：`/tmp/refactor-682-refresh100.json`；执行日志：`/tmp/refactor-682-refresh100-r2.log`。

## 30 分钟 HTTP soak

本轮真实 Web 同源 settings HTTP → IM → Node → DSH 链路完成 1001 次请求，有效计时 1800.065 秒，全部 ready=true，无 HTTP/读取失败；每 1.8 秒发起一次。正常按现有认证协议每 600 秒刷新 access token；不修改服务器认证期限。以目录 `captured_at` 是否在该请求开始之后区分实际冷重建和缓存命中，避免把首个已有缓存误记为冷读。

每约一分钟记录 Node/IM RSS、数字文件句柄、inspection home 与持久 preview 目录；不测真实聊天负载或完整舰队内存。脚本 `/tmp/refactor-682-soak.py`，执行日志 `/tmp/refactor-682-soak-r4.log`，完整结果位于 `/tmp/refactor-682-soak.json`。

首轮全量 native 与性能并行的样本已停止，不作为性能证据；初次 soak harness 的短启动在预检发现 15 分钟 token 到期与首个缓存样本分类问题后重启，保留原日志，仅统计最终完整一轮。


| 指标 | 结果 |
| --- | --- |
| 实际冷重建 | 6 次；p95 / 最大 2324.085 ms |
| 缓存命中 | 995 次；p95 12.951 ms，最大 159.936 ms |
| access token 正常续期 | 3 次 |
| 资源采样数 | 32（初始、约每分钟、结束） |
| Node RSS 首 / 末 / 范围 | 69,184 / 58,336 / 54,480–73,360 KiB |
| IM RSS 首 / 末 / 范围 | 92,000 / 69,600 / 67,024–92,000 KiB |
| Node / IM 数字文件句柄 | 始终 39 / 20 |
| 请求完成后的 inspection home / 持久 preview | 所有资源采样均为 0 / 0，净增长为零 |

冷读样本为第 112、280、448、522、690、858 个请求，耗时分别 2013.870、1903.139、1962.031、2033.548、2324.085、2058.420 ms。这些是有限时长的 catalog 负载观察，不外推其他负载或无限运行时间。原始结果及脚本已另存受保护本地 `/Users/czj/.codex/reports/refactor-682-20261031/`，不含 auth token 或原始能力配置。
