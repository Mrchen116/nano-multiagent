# refactor-478: 深化 IM 与 Gateway 控制 RPC 边界

> 状态：Retired（2026-10-19）。退役原因与当前入口见[退役索引](../README.md)。以下内容保留历史，不再作为实施要求。

> 状态：v1（2026-07-25）

## Relations

- Depends on: 无
- Blocks: 无
- Related: refactor-480、refactor-481；历史 refactor-470、refactor-472

## 原始诉求

> 再看看当前代码仓中有多少巨石代码
>
> 我希望你能明确当前所有的重要的架构问题，如果和CC有类似的概念则和CC的源码的架构做对比，然后用change-spec-author，change-design-author skill（不需要跟我逐个进行对齐），帮我创建独立的几个unit。我要逐个进行重构，完善架构。我最终做一次确认后，再开始按可并行性开始做各个unit的实现。
>
> 中途你全程负责。我只做最终的确认。

## 澄清记录

- Q1: 是否逐个对齐边界方案？
  A: “中途你全程负责。我只做最终的确认。”
- Q2: 是否把每种 RPC 拆成一个类，或引入通用事件总线？
  A: 否；既有 refactor-470/472 已明确 wire/FIFO/ACK 与 waiter 的所有者，本 unit 在这两个深边界内收敛重复生命周期。

## 现状痛点

IM 侧 `GatewayControl` 为 11 种 RPC 维护 11 张 waiter map，request 方法和 result handler 重复 request-id、注册、发送、超时、清理、迟到响应处理。Gateway 侧 `IMConnectionManager` 既拥有连接、ACK、FIFO、重连，也在近两千行文件中解析并执行业务控制操作，甚至直接读写 heartbeat、cron、skill 等本地状态。

每新增一种控制操作，都要同时修改 HTTP route、IM waiter 样板、wire frame 分派、Gateway transport 大分支和响应构造，且依赖未显式化的发送前注册与 close/ACK 顺序。

## 目标状态

IM 侧仍由一个 `GatewayControl` 持有共享锁和全部关联状态，但通过统一的 typed request/result 描述执行相关生命周期；Gateway 侧 `IMConnectionManager` 继续唯一拥有连接、wire、FIFO、ACK、重连与同步关闭，业务含义交给一个明确的 typed control dispatcher。

本 unit 不新增 RPC、不改变帧名、payload、超时降级、鉴权、节点路由或响应语义。

## 用户侧验收标准（不变性）

用户在 IM 中读取 agent live 配置、预览 prompt、fork session、管理
heartbeat/cron/skills 等相关操作仍通过在线 Gateway 完成；配置保存仍先由 IM 本地持久化，
再沿既有单向 `config.sync` 同步 Gateway。Gateway 离线或相关 RPC 超时时仍返回既有降级
结果。

### Requirement: 在线控制操作保持

#### Scenario: 读取并更新 Agent 配置
- **WHEN** 用户通过 IM 打开 Agent 设置并保存配置
- **THEN** live read 到达绑定 Gateway；save 仍由 IM 本地持久化并单向同步，返回值、错误和持久化结果与变更前一致

#### Scenario: 执行其他控制操作
- **WHEN** 用户预览 prompt、fork session 或管理 heartbeat、cron、skills
- **THEN** 对应操作的响应结构和副作用与变更前一致

### Requirement: 离线和超时行为保持

#### Scenario: Gateway 不在线或未及时响应
- **WHEN** 用户发起需要 Gateway 的控制操作
- **THEN** HTTP 状态、空值或错误降级与变更前一致，迟到结果不会完成错误请求

## 影响范围

- `src/IM/ws/gateway/control.py` 与 Gateway runtime result dispatch
- `src/personal_assistant/ws/im_connection.py`
- 控制操作领域 provider/handler 的装配位置
- 对应 IM routes、协议和行为测试
- 不改变公开 HTTP 或 WebSocket wire contract

## 迁移与回滚策略

先以协议契约测试覆盖每个既有 operation 的 request/result、timeout、late-result 和 FIFO/ACK 顺序，再在 IM 内部统一相关生命周期，随后把 PA 业务分派迁至 typed dispatcher，最后删除重复分支。切换按 operation 成组完成但只保留一条权威路径；回滚整个 unit，不保留第二 queue、通用 event bus 或长期 compatibility dispatcher。
