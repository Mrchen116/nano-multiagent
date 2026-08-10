# bugfix-446: Gateway-IM 连接韧性——休眠/断网/IM 重启后 Gateway 变僵尸

## Relations

- Closes: #162

## 原始报告

来源：用户在对话中提出 + GitHub issue [#162](https://github.com/Mrchen116/nano-multiagent/issues/162)。

用户原话：

> https://github.com/Mrchen116/nano-multiagent/issues/162 分析下。我的需求：Gateway 和 IM 通常不在同一台机器上。当 Gateway 所在机器断网、休眠、或 IM 重启后，Gateway 进程变成僵尸——事件循环死了但进程没退出，IM 侧标记 heartbeat_timeout，需要手动重启。到底有哪些地方需要加固，需要你分析

issue #162 关键内容（原文摘录）：

> Gateway 和 IM 通常不在同一台机器上。当 Gateway 所在机器断网、休眠、或 IM 重启后，Gateway 进程变成僵尸——事件循环死了但进程没退出，IM 侧标记 `heartbeat_timeout`，需要手动重启。
>
> 严重性：高。个人助手是常驻服务，用户无法接受"电脑休眠一次就要手动重启 Gateway"。
>
> 核心原则：连接层的所有异常都是可恢复的瞬态故障，永远不应该导致 Gateway 死亡。

issue 列出 6 条未捕获异常路径（裸 `connect_once()`、`_post_im_connect` 只 catch `GatewayStartupError`、finally 内 `_await_background_task`、`_scheduler.tick()` 裸 await、`run_forever` 只 catch `Exception` 漏 `CancelledError`、`set_exception` TOCTOU）。详见 issue 正文表格。

## 澄清记录

- Q1: 修复的"恢复保证"范围——只堵 issue 列的 6 条已知异常路径，还是把保证提升为"连接维护循环本身因任何原因退出，节点也能自动恢复"？
  A(原话): 我的需求：Gateway 和 IM 通常不在同一台机器上。当 Gateway 所在机器断网、休眠、或 IM 重启后，都能正常重连
  Agent 解读: 用户用"结果"定义需求（三种场景都能正常重连），不限定手段。采更强的保证——验收按"节点自动恢复"判，6 条 catch 点 + watchdog 都是为达成它的实现手段，不作为验收标准本身。

- Q2: 断网/休眠期间发给该 agent 的消息，恢复后要不要补收？还是只保证连接自愈、离线投递语义不变？
  A(原话): 好
  Agent 解读: 采纳推荐——离线期间消息补发为非目标。本单元只保证连接自愈/节点恢复 online；离线消息补发属 IM 投递可靠性，另立 unit。

## 现象与复现

Gateway 与 IM 通常部署在不同机器。三类瞬态故障会让 Gateway 变"僵尸"——进程还在、但连接不再恢复，IM 侧把节点标记为 `heartbeat_timeout`/离线，用户必须去终端手动重启 Gateway 才能恢复。

复现（issue #162 给出的最小路径）：

```bash
# 1. 启动 Gateway
PYTHONPATH=src python -m personal_assistant.main --foreground

# 2. 模拟断网：kill 掉 IM
kill <im_pid>

# 3. 等 30s 后恢复 IM
PYTHONPATH=src python -m uvicorn IM.app:app --host 0.0.0.0 --port 8011

# 4. 查节点状态
curl -s http://127.0.0.1:8011/im/v1/nodes | jq '.[] | select(.node_id=="demo-node") | .status'
# 期望: "online"   实际: "offline"（Gateway 未自动重连）
```

等价触发场景：Gateway 所在机器休眠后唤醒；Gateway 所在机器网络中断后恢复；IM 服务重启。三者本质相同——一段瞬态不可达。

## 影响范围

- **谁受影响**：所有把 Gateway 与 IM 跨机器部署的常驻个人助手用户（即典型部署形态）。
- **严重程度**：高。个人助手是 24×7 常驻服务；"电脑休眠一次就要手动重启 Gateway"不可接受，且故障静默——用户往往在需要 agent 时才发现它早已离线。
- **数据损坏**：无。纯连接可用性问题，不涉及数据写坏。
- **离线期间消息**：断连窗口内发给该 agent 的消息可能延迟或丢失（取决于 IM 投递语义）——本单元不负责补发（见非目标）。

## 目标状态 / 验收标准

镜头：回归基线——恢复"连接层瞬态故障应自愈"这一本应成立的行为。验收只看用户在 IM 上能观察到的结果，不看具体在哪些代码点加了防护。

### Requirement: 瞬态故障后节点自动恢复 online

#### Scenario: Gateway 所在机器休眠后唤醒
- **GIVEN** Gateway 与 IM 在不同机器、节点处于 online
- **WHEN** Gateway 所在机器休眠一段时间后唤醒
- **THEN** 无需人工重启，节点在有限时间内自动恢复 online，该节点下的 agent 重新能正常收发消息

#### Scenario: 网络中断后恢复
- **GIVEN** 节点处于 online
- **WHEN** Gateway 所在机器网络中断一段时间后恢复
- **THEN** 中断期间该节点在 IM 显示离线，网络恢复后节点自动回 online，全程无需人工干预

#### Scenario: IM 服务重启
- **GIVEN** 节点处于 online
- **WHEN** IM 服务重启（短暂不可达后恢复）
- **THEN** IM 恢复后节点自动重新注册并回 online，agent 重新可用

### Requirement: 启动顺序不敏感

#### Scenario: Gateway 先于 IM 启动 / 启动时 IM 不可达
- **WHEN** 在 IM 尚未就绪时启动 Gateway
- **THEN** Gateway 正常启动、不崩溃、不变僵尸，进入重试等待；IM 一就绪即自动连上、节点变 online

### Requirement: 连接层故障永不致 Gateway 僵尸

#### Scenario: 出现超出已知范围的连接故障
- **GIVEN** 节点运行中
- **WHEN** 维持 IM 连接的过程中发生任意瞬态故障（含未预料到的故障）
- **THEN** Gateway 不会停在"既不重连也不退出"的僵尸态——最终自动恢复 online，用户无需手动重启

## 范围与非目标

本期做：
- 让 Gateway 在断网/休眠/IM 重启/启动早于 IM 等瞬态故障下都能自动恢复 online。
- 兜底保证：即便维持连接的后台过程意外退出，也能被重新拉起，不留僵尸。

非目标：
- **离线期间消息补发**——断连窗口内的消息恢复后是否补收，取决于 IM 投递可靠性，属另一机制，另立 unit。
- **IM 侧的节点状态展示/超时阈值改动**——本单元只动 Gateway 侧连接行为，不改 IM 的判定逻辑。
- **缩短恢复窗口到"零中断"**——恢复存在几秒至一个退避周期的窗口，期间节点显示离线属正常，不追求无缝。

## 根因分析（RCA）

### 原始设计意图与必须保住的不变量

连接层 `run_forever` 由 M102（`feat-340-agent-native-im`）引入。设计意图写在 `im_connection.py` 的类 docstring：套接字断开时，管理器**只更新本地状态并稍后重试**，**不打断 gateway 的本地 IM/channel 执行**（local-autonomy 不变量）。即：连接故障被定义为"可恢复的瞬态故障，永不致命"。

修复必须保住的不变量：连接层的任何故障都不得拖垮 Gateway 进程或其本地执行；恢复必须是自动的。这条不变量本就是原设计承诺，bug 在于实现没有完整兑现。

### 技术根因

`run_forever` 内部的重连循环（指数退避、断连检测）设计是对的，但它的**保护圈之外**存在多条未捕获异常逃逸路径，以及一个结构性兜底缺口：

1. 主启动流程里首次 `connect_once()` 为裸调用，启动时网络不通/唤醒后首连失败的异常直接逃逸。
2. `_post_im_connect` 只捕获 `GatewayStartupError`，`OSError`/HTTP 错误（token 落盘、node binding）会逃逸。
3. `_run_until_shutdown` 的 `finally` 清理块内对后台任务的等待会重新抛出任务里存的异常，使清理流程自身炸穿。
4. 心跳调度 `_scheduler.tick()` 为裸 await，异常会让心跳子系统静默死亡且 Gateway 不自知。
5. `run_forever` 的 except 只接 `Exception`，`CancelledError`（`BaseException`）会逃逸并跳过断连清理。
6. **（结构性缺口，issue 已列 6 条之外更关键的一条）维持连接的后台任务没有 watchdog**：一旦它返回或死亡，没有任何东西重启它，主进程仍阻塞在 shutdown 等待上——连接永不恢复，但进程也不退出。这是用户所说"僵尸"的最常见形态。

（issue 另列的 `set_exception` TOCTOU 一条，经核对本项目为单事件循环、入站经 `run_coroutine_threadsafe` 串行回同一 loop，check 与 set 间无 await，经典竞态实际不成立——可作零成本防御，但非真实致命路径，优先级最低。）

### 为什么这种错能进来

- 重连循环在单元层被验证过，但**集成层的"宿主级瞬态故障"端到端场景（休眠/断网/IM 重启/启动早于 IM）从未被真栈 e2e 覆盖**，所以保护圈外的逃逸路径无人触发。
- 这些逃逸路径分散在 startup / finally / 主循环编排（`main.py`），与构建重连循环的 unit（M102，`im_connection.py`）不在同一处，是随功能迭代逐步累积的，没有一处统一的"任何瞬态故障都不得致命"守门。
- watchdog 缺口属设计盲点：原设计假定 `run_forever` 永不退出，未为"它万一退出了"留兜底。

### 回归引入点

非回归。该僵尸行为不是某次变更把"原本能用"改坏的，而是连接层自 M102 引入起就存在的兜底缺口——逃逸路径与 watchdog 缺口一直在，只是依赖宿主级瞬态故障才暴露。`git blame` 对应路径均落在 M102（`f2019a8f`）及其后续增量，无单一"引入坏行为"的回归点。

## 修复方向

高层方案（行级实现留给 milestone）：核心原则——连接层的所有异常都是可恢复的瞬态故障，永不致 Gateway 死亡或僵尸。

- 让首次连接与启动期故障进入与重连循环同策略的退避重试，不逃逸。
- 把启动/清理/主循环编排上的异常逃逸路径全部收敛（catch 范围扩到能兜住瞬态故障，清理块吞掉异常，`CancelledError` 显式处理后仍走清理）。
- 给维持连接的后台过程加 watchdog：意外退出即被观测并重新拉起，杜绝"既不重连也不退出"的僵尸态。
- 长青契约层 `docs/specs/gateway/spec.md` 补"断网/休眠/IM 重启恢复"场景。
- 回归矩阵覆盖四类场景（休眠唤醒 / 断网恢复 / IM 重启 / 启动早于 IM），经真 Gateway 进程验证，并登记到 `docs/e2e-critical-paths.md`。
