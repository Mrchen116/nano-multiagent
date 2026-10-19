# 新建 Agent 预览工作目录修复

本记录属于开放 PR #366 的同一交付会话内验收反馈小修；不重开完整生命周期。pre-fix HEAD `8ac318506`，既有完整 OpenUI 结论保留；本次只做目录初始化回归和独立 patch code review。

## 原始报告与范围

用户截图显示 `/settings/agents/new` 一直 Loading，随后询问“之前是你特意断的，还是代码有bug断的？”，确认后要求“那把这个 bug 修了”。范围为新建 Agent 的能力与 prompt 预览，不改已有 Agent 的工具选择、workspace 归属、审批或用户聊天数据。

## 现象与根因

Node此前正常ready；打开新建页后 `node.capabilities.resolve` 以默认 `preview` 目录构造临时配置。已有 Agent 的目录会在 NodeConfiguration.read/persist 创建，但尚未保存的新 Agent 预览不经过这两条路径。`WorkspaceExtensions.attach` 对受信配置目录直接realpath，抛 ENOENT，DSH原生preset加载失败使整个子进程退出。运行日志记录该错误与 runtime unavailable；补目录重启只能恢复现场。

引入workspace插件的 `33ef0d76d`（feat-610）让该缺口成为fatal；插件挂载必须保持Node提供的受信workspace、原生DSH生命周期与真实能力发现，不能通过跳过插件或假造空catalog消除症状。现有能力测试使用已存在cwd、实际创建API会先建目录，因而没有覆盖创建页的先行预览。

## 修复与验证

在Node收到能力/预览请求、解析有效候选配置后，创建同一受信工作目录，再调用原有DSH能力/预览。扩展现有“经IM创建Agent并可聊”的关键路径，先经过缺省能力与新目录prompt预览；原创建、持久化及回复验证继续保留。实施、先红后绿结果和独立review在本节追加。


### 实施与回归

- `apps/node/src/main.ts`在解析有效candidate后、原native调用前执行recursive mkdir；不改变workspace选择、插件挂载或能力返回。
- 扩展已有`test_create_agent_via_im_lands_and_replies`，不建立同因平行测试。新建目录preview成功且未提前注册Agent，随后实际创建和模型回复仍通过。
- 修前：真实临时IM/Node/锁定DSH，GET node capabilities返回503；gateway.log记录`realpath .../.gateway-workspace/preview ENOENT`、fatal load failure与DSH退出。`/tmp/feat617-preview-red.log`，1 failed，19.10s。
- 修后：相同命令`NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 .../pytest tests/e2e/critical_paths/test_create_agent_via_im_critical_path.py -q -x`，1 passed，10.13s；`/tmp/feat617-preview-green.log`。两次fixture均创建独立pytest临时栈并由e2e-down清理，没有重置用户正在试用的58769现场。
- Node配置/能力投影与原生DSH能力专项3 suites/13 tests通过；Node build/typecheck、Ruff检查与格式通过。本次没有前端源改动，保留此前99/908 Web与完整backend/架构证据，远端CI将运行最终集成树全量。
- no spec delta：恢复已有新建Agent与能力读取契约；不改变可选工具、workspace归属、消息语义或审批。


### 最终收口

- 独立patch code review：`8ac318506..36e713cdb`，`gpt-6.1-sol/high`，无存活finding，结果见[preview-workspace-code-review.json](preview-workspace-code-review.json)。旧完整OpenUI结论按未改变的产品路径与原证据保留。
- 全后端96 suites/373 tests通过（95.11s），Python非E2E62通过/31 deselected，docs-check237/64及unit归档门禁通过。origin/main仍cc47abe3f，无同步增量；代码变更后的报告追加不改变验证语义。
- 用户现有58769测试栈仅重启Node加载修复，PID55288/DSH55328 ready=true。对全新随机id_hint调用真实capabilities与prompt-preview均200，目录由产品自动创建，含指定prompt；两次调用后PID未变、owner读取node状态online。真实新建页表单正常显示、节点online；未预先手工创建本轮验证目录。
- IM与数据库没有重置，原会话、草稿、配置和身份保留；仅更新隔离测试环境，未部署生产或修改feat-616。新建临时Agent并实际聊天的完整验证属于前述pytest临时栈，不冒充在用户现有会话里新建过Agent。
