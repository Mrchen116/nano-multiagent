# feat-503: 可复用 Feishu E2E runtime

## Relations

- Related: feat-501

## 原始需求

> 这次不单单要完成这个pr，而且要把飞书通道的测试打通，后续unit都能复用的模式。

> 考虑，当前流程中e2e测试是拷贝本机的全局配置？然后全局配置一直配置飞书channel，然后文档不完善，导致不知道怎么连，连哪个，导致的问题对不对。
> 然后用lark-cli发送消息给测试agent又遇到了问题，导致你必须computer use来控制飞书，对吧。
>
> 我们盘点下整个e2e的卡点。

> 那我们改变模式。e2e-up.sh不从本机复制，而是固定本仓中维护一套测试用的config，里面某个agent就配好了飞书channel。并把lark-cli用测试agent登录好。是不是就顺了

> 原来.env要是错的话，也要清理了

> 把这次对e2e的改造，我们专门搞一个pr

> 目标是后续不会再卡在飞书的问题上

> 按个毛，直接改，改完补spec就完了

## 澄清记录

- Q1: E2E 是否继续从每台开发机的个人 Gateway config 继承 agent、模型和 Feishu channel？
  A(原话): 那我们改变模式。e2e-up.sh不从本机复制，而是固定本仓中维护一套测试用的config，里面某个agent就配好了飞书channel。并把lark-cli用测试agent登录好。是不是就顺了
  Agent 解读: 仓库维护无密钥的固定测试拓扑；真实 App 凭据和用户授权仍仅留在本机私有位置。
- Q2: 测试环境的最终目标是否是一次性通过，还是后续 change unit 可直接复用？
  A(原话): 目标是后续不会再卡在飞书的问题上
  Agent 解读: 启动、身份校验、发送入口和失败信息都必须脚本化，不能依赖当前操作者记住历史排障结论。
- Q3: 该改造如何交付？
  A(原话): 把这次对e2e的改造，我们专门搞一个pr
  Agent 解读: 与 feat-501 的产品功能实现分离为独立 PR。

## 用户场景

开发者为任何需要真实 Feishu channel 的 change unit 做验收时，先在干净 worktree 调用统一的启动命令。普通 E2E 不会接触该开发者的个人 Gateway 或生产 Bot；需要 Feishu 时，启动命令明确选择专用测试 agent。测试消息经已经验证身份的测试 App 和命名 CLI profile 发出，开发者能够看到探针通过，或在真正发送前得到明确的身份/配置错误，而不是转去 Computer Use 猜测当前连的是哪个 Bot。

## 验收标准

### Requirement: 仓库拥有稳定的隔离 E2E 起点

#### Scenario: 开发者运行默认真栈

- **WHEN** 开发者在任一 worktree 启动 `scripts/e2e-up.sh`
- **THEN** 栈使用仓库维护的测试 agent 与模型目录启动
- **AND** 不读取个人 Gateway config

#### Scenario: 开发者需要不同的受控 config

- **WHEN** 开发者显式传入 `--main-config`
- **THEN** 栈只使用该指定 config 的 worktree 副本

### Requirement: 专用 Feishu 测试通道可安全复用

#### Scenario: 专用测试配置与 CLI profile 正确

- **GIVEN** 本机已配置专用 Feishu App/Bot 凭据和命名测试 CLI profile
- **WHEN** 开发者启动 Feishu profile 并运行 nonce 探针
- **THEN** 探针通过专用测试 Bot 发送消息并确认隔离 Gateway 收到该消息

#### Scenario: 凭据或 CLI profile 指向错误身份

- **WHEN** 开发者启动 Feishu profile 或运行探针
- **THEN** 命令在启动 listener 或发送消息前失败，并说明是测试 Bot/App/profile 身份不匹配

## 范围与非目标

- 在范围：仓库无密钥 E2E profile、专用 Feishu profile 的运行时注入、Bot identity 与 CLI profile 校验、真实 nonce ingress 探针、现有真栈测试去除个人 config 依赖，以及对应开发文档。
- 非目标：提交 App secret、CLI token 或运行数据库；修改生产 `nano` Bot；把外部 Feishu 凭据加入默认 CI；把 feat-501 的 `/new`、`/compact` 产品实现并入本 PR。
