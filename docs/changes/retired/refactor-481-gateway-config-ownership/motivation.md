# refactor-481: 重建 Gateway 本地配置所有权

> 状态：v3（2026-07-25）

## Relations

- Depends on: 无
- Blocks: 无
- Related: refactor-478、refactor-480

## 原始诉求

> 再看看当前代码仓中有多少巨石代码
>
> 我希望你能明确当前所有的重要的架构问题，如果和CC有类似的概念则和CC的源码的架构做对比，然后用change-spec-author，change-design-author skill（不需要跟我逐个进行对齐），帮我创建独立的几个unit。我要逐个进行重构，完善架构。我最终做一次确认后，再开始按可并行性开始做各个unit的实现。
>
> 中途你全程负责。我只做最终的确认。

## 澄清记录

- Q1: 是否逐个确认拆分？
  A: “中途你全程负责。我只做最终的确认。”
- Q2: 是否仅因 `local_store.py` 超过千行而拆文件？
  A: 否；拆分依据是 schema/codec/durable write/runtime owner/workspace bootstrap/model policy/Feishu provisioning 有独立变化轴和所有权。
- Q3: `--im-service-url` 是否继续在后续 token/Agent 写回时污染 YAML？
  A: 否；这是当前实现 drift。本 unit 把 override 明确为 process-only overlay，并提供
  gateway delta-spec。

## 现状痛点

`personal_assistant/config/local_store.py` 同时定义全部配置 dataclass、YAML parser、序列化、backup/atomic save、运行时快照 owner、启动组合、默认 workspace 文件、模型选择，以及 Feishu identity 探测、owner 绑定和 skill provisioning。

通用配置 codec 因此知道特定 channel 的远端身份与 skill 安装，运行时策略又与持久化细节共处。修改 Feishu 接入、模型策略或 YAML schema 都需要理解整份文件，测试难以围绕稳定接口隔离。

后台启动器与前台 Gateway 子进程还会各自执行一次“加载 + Feishu probe/provision”，因此
重复 `start` 可能在已有 Gateway 之外引入第二个短命 writer。静态 YAML Feishu 与 IM 托管
Feishu 又使用不同持久化权威，却被同一个大模块的 helper 名称掩盖。当前两种 writer 的
backup/secret 安全语义也由调用方选择，配置 owner 并没有真正拥有落盘策略。

显式 `--foreground` 还会绕过 background lifecycle command lock 直接进入 runtime；所以只把
background parent 改成只读仍不足以保证唯一 writer。IM refresh 则有另一个 commit point：
服务端返回新 token pair 前已撤销旧 refresh token，本地 YAML 只是远端事实的 durable mirror，
不能在本地写失败时把进程回退到已撤销的旧 pair。Agent 配置写回后的 reporter/cron 又是
durable/live publication 的 follower；当前 cron 只在 create callback 注册，首次失败后重连
全量对账不会补齐。

## 目标状态

建立清晰的本地配置子系统：

- schema/codec 负责类型、验证与 YAML 投影；
- read-only document 保留完整 raw preimage bytes/hash/tree，typed model 只承载 deep-frozen
  semantic snapshot；
- durable store 负责语义 no-op、external divergence 检测、基于真实 old/new document 的自动
  安全分类、串行化 snapshot mutation、备份、原子保存、commit-point 诊断与唯一发布，不再
  叠一层独立 `RuntimeConfigOwner`；
- background launcher 只做 read-only decode；background child 与 direct `--foreground`
  必须竞争同一 config-scoped lifetime writer lease，只有 winner 能打开可写 store 和执行
  workspace/Feishu 副作用；
- runtime IM endpoint overlay 与远端已提交的 rotating credential state 分离；后者先发布到
  当前进程，再异步/重试镜像到本地 store，本地失败不得回退远端事实；
- workspace bootstrap 负责默认目录和文件；
- 模型选择归产品运行策略；
- static Feishu identity/provisioning 写 LocalConfigStore；managed Feishu 继续以
  ChannelManifestStore 与 IM agent profile 为权威。
- Agent durable/catalog/reporter/cron follower 按 desired state 幂等收敛；相同配置不重写
  YAML、不增加 catalog revision，但仍补齐缺失 follower。

消费者直接迁移到新 owner，不保留 `local_store.py` 大一统兼容 façade。

## 用户侧验收标准

用户仍用同一 `~/.nano-assistant/config.yaml` 启动 Gateway；IM 新建 Agent 的配置仍写回；重启不丢失 agent；Feishu 首次接入、模型选择和 workspace 初始化保持既有行为。

### Requirement: 配置加载和持久化保持

#### Scenario: 使用现有配置启动并重启
- **WHEN** 用户以既有 YAML 配置启动、停止并再次启动 Gateway
- **THEN** 校验、默认值、agent/channel/LLM 配置和持久化结果与变更前一致

#### Scenario: IM 修改 Agent 配置
- **WHEN** 用户在 IM 创建或编辑 Agent
- **THEN** Gateway runtime snapshot 与 YAML 写回保持一致，重启后配置仍存在

#### Scenario: 同一 config 的所有启动模式只产生一个 writer
- **GIVEN** background child 或 direct `--foreground` Gateway 已经持有并可能更新配置
- **WHEN** 运维者以 background 或 direct `--foreground` 对同一 resolved config 并发启动
- **THEN** 只有一个 Gateway 进入 runtime；其余启动报告实例已运行，YAML bytes/mtime 与
  workspace 文件树不变，也不发起 Feishu probe/provision

#### Scenario: runtime IM URL override 不持久化
- **GIVEN** YAML 保存 URL A
- **WHEN** 运维者以 `--im-service-url B` 启动并发生 token 或 Agent 配置写回
- **THEN** 本进程连接 B，但 YAML 仍保存 A；下次不带 override 启动仍连接 A

#### Scenario: 远端 token rotation 已提交但本地镜像失败
- **GIVEN** IM refresh 已返回新 access/refresh pair，并已撤销旧 refresh token
- **WHEN** Gateway 把新 pair 写回本地 YAML 时发生 pre-commit failure
- **THEN** 当前进程继续持有并使用新 pair 完成 reconnect，不回退到旧 durable pair；Gateway
  明确记录 pending mirror 并在存活期间重试
- **AND** 若进程在镜像成功前退出，username/password 配置可通过重新 login 恢复；token-only
  配置在下次启动时明确要求重新认证，不把已撤销 pair 误报为可回滚状态

### Requirement: 产品策略保持

#### Scenario: 选择运行模型并初始化 workspace
- **WHEN** Gateway 为 Agent 创建运行并首次准备 workspace
- **THEN** 模型解析、目录和默认文件与变更前一致

#### Scenario: Feishu 首次接入
- **WHEN** 用户启用既有 Feishu channel 配置
- **THEN** identity 探测、owner 绑定与所需 skill provisioning 和变更前一致

#### Scenario: static 与 managed Feishu 保持各自权威
- **WHEN** static YAML channel 与 IM 托管 channel 分别发生 identity、owner 或 skill 更新
- **THEN** static 路径只更新本地 YAML；managed metadata 只更新 generation-scoped
  manifest，managed skill 先更新 IM profile 再镜像本地，不互相覆盖

#### Scenario: Agent follower 在同连接与重连时幂等补齐
- **GIVEN** Agent 配置已提交到 YAML/catalog，但 cron follower 首次收敛失败
- **WHEN** 同一活连接再次同步相同 profile，或 Gateway 重连后执行全量对账
- **THEN** 该 Agent 的 cron 调度恢复可用；已正常工作的 Agent 不因重复对账产生重复 cron
  执行或重复状态上报

## 影响范围

- `src/personal_assistant/config/local_store.py` 及新配置子模块
- Gateway 启动/组合、agent 配置写回和 model resolution
- Feishu channel bootstrap/provisioning
- 配置、启动与 channel 测试
- `specs/gateway/service-lifecycle.md`：single-writer repeated-start、process-only IM URL
  override、remote-committed token rotation delta
- 不改变 YAML 外部 schema、默认路径或 CLI 参数形态

## 迁移与回滚策略

先建立 fixture round-trip、deep-freeze/raw preimage、语义 no-op、安全写盘矩阵、三组
foreground/background lease 竞争、remote rotation mirror failure、runtime mutation/live follower
收敛、workspace 与 static/managed Feishu 行为测试；再按 owner 迁移直接消费者；最后删除旧聚合
模块。保持单一 durable snapshot 与单一 config-scoped foreground writer，不做新旧格式双写。
失败时整体回滚，既有 YAML 无需数据迁移。
