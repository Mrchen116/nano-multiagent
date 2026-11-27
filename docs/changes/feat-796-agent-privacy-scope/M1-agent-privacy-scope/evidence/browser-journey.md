# feat-796 隔离真栈真实浏览器与多角色端到端验收记录

- **执行时间**：`2026-11-27T11:04:00+09:00`
- **工作树与分支**：`/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-796-agent-privacy-scope`（`unit/feat-796-agent-privacy-scope`）
- **运行栈入口**：`./scripts/e2e-up.sh --wt "$WT_ROOT"`（独立端口 `127.0.0.1:52014`、独立 SQLite `data/im_service.sqlite3`、独立节点身份 `wt-unit-feat-796-agent-privacy-scope-78507`）
- **本地截图存档（仓外保留，遵循 `docs/development/evidence.md`）**：
  `/Users/czj/.t3/userdata/providers/antigravity/ac0a3dfd6dddb20962cecff6ee5fe65e19d3923be20e52c5ab52ff877f7e4c32/antigravity-acp/brain/c4e14ce0-820d-45ae-bb2f-1dc7da963080/scratch/evidence/`（`01`–`09` 共 9 张 PNG + `journey-report.json`）
- **资源回收核实**：`./scripts/e2e-down.sh --wt "$WT_ROOT"` 已执行并清理临时运行文件；`ps aux | grep unit-feat-796-agent-privacy-scope` 核实残留进程数为 `0`。

## 场景与视口走查对照表

| 编号 | 视口与角色 | 验收场景与可复现入口 | 脱敏请求 / 状态摘要 | 画面与交互结论 |
|---|---|---|---|---|
| 01 | Mobile `390×844` · 主人 `nano` | `/onboarding` 第 3 步「给你的个人助手起个名字」首屏展示两档分段控件并切换为「私有（仅自己与名下助手）」 | `GET /im/v1/nodes/:id/setup` 已连接模型；读取主按钮 `创建个人助手` `boundingBox` | **PASS**：分段控件默认「团队公开」，切换「私有」后单行提示清晰说明“对团队同事隐藏且不对外发言；仍静默观察你允许查看的聊天。”；主按钮底边 `y + height = 782px <= 844px`，无需滚动即可首屏直达点击（存档 `01-mobile-onboarding-pa-scope.png`）。 |
| 02 | Desktop `1280×820` · 主人 `nano` | 从 `/chat` 点击「我的个人助手」进入创建页，直接选定「私有（仅自己与名下助手）」完成创建 | `POST /im/v1/personal-agent` `{ collaboration_scope: "owner_only" }` -> `201`，`GET /im/v1/personal-agent` 返回 `binding.collaboration_scope === "owner_only"` | **PASS**：创建瞬间即以 `owner_only` 落库并进入主人私聊，零公开窗口暴露（存档 `02-desktop-pa-setup-private-scope.png`）。 |
| 03 | Desktop `1280×820` · 主人 `nano` | `/settings/agents/new` 新建普通/全局 Agent，核查默认档位并创建公开与私有全局助手 | `#collaboration-scope` 默认 `"team"`；`POST /im/v1/nodes/:id/agents` 分别创建个人空间下的 `公开研发助手`（`team`）与 `私密调研员`（`owner_only`）-> `201` | **PASS**：由于主人已开启个人空间（创建了 PA），两个新建全局 Agent 的 `space_id` 均为 `personal:<owner_id>`，准确覆盖“个人空间团队成员公开/私有普通助手”真实场景（存档 `03-agent-create-scope-selector.png`）。 |
| 04 | Desktop `1280×820` · 同事 `linxia`（先个人注册后获批 `active`） | 同事打开 `/people` 一级同事目录查看团队成员与关联助手 | `GET /im/v1/contacts` 对 `linxia` 返回 `nano` 名下 `公开研发助手`，过滤 `私密调研员` 与私有 PA `小助理` | **PASS**：「同事」目录中 `Test User (@nano)` 卡片下方正常展示跨个人空间的 `公开研发助手 ↗` 芯片，彻底隐藏 `私密调研员` 与私有 PA `小助理`（存档 `04-colleague-people-directory-filtered.png`）。 |
| 05 | Desktop `1280×820` · 同事 `linxia` | 同事直接访问他人私有助手 URL `/settings/agents/nano_secret_research` | 联系人与公开资料查询未返回目标助手 | **PASS**：页面平稳呈现状态说明“该助手不存在或当前未对外开放。”及返回按钮，无报错崩溃或虚假网络重试引导（存档 `05-colleague-private-agent-unavailable.png`）。 |
| 06 | Desktop `1280×820` · 主人 `nano` | `/chat` 打开「新建群聊」勾选 `私密调研员`，核查外部同事互斥禁用并创建内部专属群 | 勾选 `私密调研员` 后可见范围自动锁定 `私密 · 仅成员`（`disabled`），同事 `林夏` 复选框禁用并提示“已选私有助手，暂不可与外部同事同群”；继续勾选 `公开研发助手` 提交创建《我的内部智囊团》-> `201` | **PASS**：勾选阶段即时防呆，且支持同一主人名下跨 `company:default` 与 `personal:<owner_id>` 多助手组建私密专属群（存档 `06-new-group-mutual-exclusion.png`）。 |
| 07 | Desktop `1280×820` · 主人 `nano` | `/settings/agents/nano_team_helper?view=config` 将已加入外人群《跨部门推进群》并与 `linxia` 有历史 1:1 的 `公开研发助手` 切换为「私有」 | 选择 `owner_only` 时展示提示“保存后将自动退出含外部同事的群聊，并将与同事的历史私聊冻结为只读。”；点击「保存 Agent」-> `PATCH /im/v1/agents/nano_team_helper/config` `200`，底部状态变为 `已保存` | **PASS**：事务提交后 `GET /im/v1/conversations/:extGroupId` 确认 `nano_team_helper` 已自动退出《跨部门推进群》，而内部专属群《我的内部智囊团》成员保持不变（存档 `07-owner-tighten-scope-config.png`）。 |
| 08 | Desktop `1280×820` & Mobile `390×844` · 同事 `linxia` | 同事打开与 `公开研发助手` 的历史 1:1 私聊并操作右上角「会话菜单」 | `GET /im/v1/conversations/:dmId` 返回 `can_write: false, write_blocked_reason: "agent_private"`；点击菜单「置顶聊天」-> `PATCH` `200` | **PASS**：双视口均保留历史消息 `你好，我们先对齐一下接口规范。` 可读，顶部暖色提示条显示“该助手当前设为私有，暂不对外接收或发送消息”，隐藏底部输入框与顶栏失效 `⚙` 配置按钮，且右上角「会话菜单」仅展示可用的「置顶聊天 / 消息免打扰」（存档 `08-colleague-frozen-dm-and-menu.png`、`09-mobile-colleague-frozen-dm.png`）。 |
| 09 | Desktop `1280×820` · 主人 `nano` & 同事 `linxia` | 主人将 `公开研发助手` 重新切回「团队公开」并保存，同事刷新原 1:1 私聊 | `PATCH /im/v1/agents/nano_team_helper/config` `{ collaboration_scope: "team" }` -> `200`；同事原会话 `can_write` 恢复 `true` | **PASS**：同事原 1:1 会话底部消息输入框立即自动恢复，无需重建会话。 |

## 实测发现并闭环的问题

1. **移动端 `390×844` 首次设置第 3 步首屏溢出**：初次真机尺寸渲染发现新增两档范围分段控件后，`onboarding-identity-preview` 与窄屏边距叠加导致「创建个人助手」按钮底边落在 `1009.8px`（超出 `844px` 首屏）。通过在 `onboarding.css` `@media (max-width: 767px)` 折叠与下方 `AvatarPicker` 重复的静态卡片预览并收紧窄屏行距，实测主按钮底边稳定落在 `782px`（距视口底边留白 `62px`），视觉层次更清爽。
