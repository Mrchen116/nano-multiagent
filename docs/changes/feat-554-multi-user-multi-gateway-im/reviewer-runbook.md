# feat-554 — Runbook for Reviewer

这是实施后真人浏览器验收的起停与前置说明，设计阶段不把这里的命令视为已经执行过的产品旅程。隔离规范以 [worktree-runtime](../../development/worktree-runtime.md) 为准。账号为本地测试账号，不需外部企业租户或第三方通讯权限。Q10 指定旧数据转换由正式部署 agent 按 [migration-prompt.md](migration-prompt.md)执行；本 Runbook 的开发验收只使用目标格式数据，不要求实现迁移程序。

## 前置与拓扑

- 从实施 unit worktree 执行，Python 使用主仓 `.venv`；需 PyYAML、curl、前端依赖以及真实浏览器。
- 模型取 `config/e2e/gateway.yaml` 的本机代理及模型；2026-09-13 已核实本机 `127.0.0.1:4000/health` 返回 200、项目 Python 可 import yaml。运行时再次检查代理及模型可调用，以真实问答作为模型就绪证明，不能以健康码冒充模型执行成功。凭据取现有 E2E 配置／本机代理，不复制生产 Gateway 配置。
- A=`nano`，管理主栈 Gateway A1 和额外 Gateway A2；B=`feat554_b`，不绑定设备；C=`feat554_c`，管理 Gateway C1。三台 Gateway 可运行在同一物理机器，拥有独立 node_id、配置目录、状态目录及 Agent workspace，共享同一隔离 IM。
- A1 上 `e2e` 为 single_thread，`e2e-peer` 为 global；A2 和 C1 使用不同 Agent ID。不开 Feishu channel。批准验证使用 single_thread 的 manual 授权模式和沙盒 workspace 内无害命令。

## 创建隔离栈

以下代码块在同一个持久终端执行，`UNIT_ROOT` 是实施 worktree 的绝对路径。首个步骤保留现有脚本的退出清理能力；额外 Gateway 由此终端拥有。

执行启动命令前，核对实际 global Skill 根：当前为运行用户的 `~/.nanoassistant/skills`，三个同机同用户 Gateway 共享它，`RUNTIME_ROOT` 和 Agent workspace 不隔离该目录。为两种 scope 的创建选择本轮唯一的 `feat554-review-<随机后缀>` 名称，确认两个目标根均无同名项，并记录实际创建路径。

Gateway 启动还会把 package 声明的 builtin 目录同步到这个根。启动前记录这些目录的存在状态、内容快照和哈希，保存到本轮运行目录；结束按下文恢复。若该用户根正在被日常 Gateway 或其他验收共用，使用现成独立测试用户／运行环境再执行以下步骤，不在共用运行根覆盖 builtin；本 unit 不新增产品路径配置或隔离框架。

```bash
UNIT_ROOT="$(git rev-parse --show-toplevel)"
export UNIT_ROOT
export PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH"
RUNTIME_ROOT="$(mktemp -d "$UNIT_ROOT/.feat554-review.XXXXXX")"
export RUNTIME_ROOT

python - <<'PY'
import os, pathlib, yaml
root = pathlib.Path(os.environ['UNIT_ROOT'])
target = pathlib.Path(os.environ['RUNTIME_ROOT'])
cfg = yaml.safe_load((root / 'config/e2e/gateway.yaml').read_text())
cfg['agents'][0]['work_mode'] = 'single_thread'
cfg['agents'][1]['work_mode'] = 'global'
(target / 'a1-source.yaml').write_text(yaml.safe_dump(cfg, allow_unicode=True))
PY

cleanup_feat554() {
  for role in a2 c1; do
    if test -f "$RUNTIME_ROOT/$role/gateway.pid"; then
      kill -TERM "$(cat "$RUNTIME_ROOT/$role/gateway.pid")" 2>/dev/null || true
    fi
  done
  wait "$A2_PID" "$C1_PID" 2>/dev/null || true
  "$UNIT_ROOT/scripts/e2e-down.sh" --wt "$UNIT_ROOT"
}
trap cleanup_feat554 EXIT INT TERM
"$UNIT_ROOT/scripts/e2e-up.sh" --wt "$UNIT_ROOT" --main-config "$RUNTIME_ROOT/a1-source.yaml"
source "$UNIT_ROOT/.e2e-ports.env"
export IM_URL
curl -fsS "$IM_URL/openapi.json" >/dev/null

python - <<'PY'
import copy, json, os, pathlib, urllib.request, uuid, yaml
root = pathlib.Path(os.environ['UNIT_ROOT'])
runtime = pathlib.Path(os.environ['RUNTIME_ROOT'])
url = os.environ['IM_URL']
for username in ('feat554_b', 'feat554_c'):
    body = json.dumps(dict(username=username, password='feat554_test_password', display_name=username)).encode()
    req = urllib.request.Request(url + '/im/v1/auth/register', data=body, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req) as response:
        assert response.status == 201
source = yaml.safe_load((root / 'config/e2e/gateway.yaml').read_text())
for role, username, password, mode in [('a2','nano','nano1234','global'), ('c1','feat554_c','feat554_test_password','single_thread')]:
    target = runtime / role
    target.mkdir()
    cfg = copy.deepcopy(source)
    cfg['node'] = dict(node_id='feat554-' + role + '-' + uuid.uuid4().hex[:10], workspace_base=str(target / 'workspace'))
    cfg['im_service'] = dict(url=url, username=username, password=password)
    agent = copy.deepcopy(source['agents'][0])
    agent.update(agent_id='feat554-' + role, title='Review ' + role, work_mode=mode, workspace_root=str(target / 'workspace' / role))
    cfg['agents'] = [agent]
    path = target / 'gateway.yaml'
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True))
    path.chmod(0o600)
PY

cd "$RUNTIME_ROOT/a2"
PYTHONPATH="$UNIT_ROOT/src" python -m personal_assistant.main --config "$RUNTIME_ROOT/a2/gateway.yaml" --im-service-url "$IM_URL" --foreground --auto-bind >gateway.log 2>&1 &
A2_PID=$!
echo "$A2_PID" >gateway.pid
cd "$RUNTIME_ROOT/c1"
PYTHONPATH="$UNIT_ROOT/src" python -m personal_assistant.main --config "$RUNTIME_ROOT/c1/gateway.yaml" --im-service-url "$IM_URL" --foreground --auto-bind >gateway.log 2>&1 &
C1_PID=$!
echo "$C1_PID" >gateway.pid
cd "$UNIT_ROOT"
```

构建前端后使用 IM 服务页面，或按 worktree-runtime 启动独立 Vite；不得打开生产 `:8011`。浏览器建立 A/B/C 三个独立 context，分别登录上述账号；A 的设备列表确认两个节点在线、C 一个、B 零个，再向三节点各发一次真实模型消息确认回复与发送身份。global 与 single_thread 以页面实际模式为准。

## 验收与重启

按 spec 全部 18 Scenario 对账，实施期验收 design 的 R1–R7、W1–W4 产品行为；“原用户继续使用”的真实存量转换与保真由部署 agent 按迁移文档验收，不能在实施报告中提前标记已完成。重点串联：B 私聊 A 的 Agent、三账号建群并加入 A/C 的 Agent、真实跨节点交办、C1 的批准由 B 操作、A/C 查看 B 私聊在全局 Work 中已记录的完整内容但不能打开原聊天、成员移除后在线与重连同步、一个人的已读／置顶／免打扰不改变另一个人。

中英文、附件／消息操作、工具轨迹、fork、无设备及离线场景沿用真实产品，不能用原型示意代替。批准目标和重复决定还需针对同一请求验证并发 HTTP 与重连，核实真实工具副作用只发生一次；终端日志只是辅助证据。

按 design 的既有能力承接矩阵逐项验证 R7：在管理者自己的 single_thread Agent 上准备至少两段 idle 聊天，测试侧栏底部／右键选择、同 Gateway 锁定、执行 Agent、agent/global 两种 Skill 写入范围、成功后新建并原样预填但不自动发送；缺 distiller／skill_view、离线或路径失败不得创建空聊天。global Agent 聊天蒸馏不是本次验收能力。对 B 私聊 A 的 Agent 及多 Gateway 群，验证 B 的 `/` 已启用命令／技能、@ 和头部在线状态、合格 direct 回复 fork 均可使用，同时 B 无法读取完整管理配置。补回菜单的复制／长按、私聊改名、草稿、Agent 新建／Channels／Skills、账号／设备／Policies／退出沿用真实页面逐项回归。

蒸馏还要核对 Gateway 实际同步到运行根的 builtin 输入说明已为 `agent/global`。在隔离 workspace 为两个范围各准备有效来源和不同 Skill 名，分别手动发送预填 prompt，确认 `skill_manage` 返回成功并写入所选 Agent 目录／该 Gateway 全局目录；确认未落到另一个 scope，也不依赖 `pa` 别名。不能以 UI 选项、preflight 或预填成功代替实际创建结果。

补充资源旅程：B 向 A 的 Agent 发送图片，Agent 实际读图并回传 workspace 内生成的图片；A 本人无法用真人 JWT 读取该原聊天或附件。C 的 Agent 在 A 创建的群采用新配置后，所有成员看到配置边界。普通文件新上传、目标格式的历史资源和合法 fork 均能由成员读取，非成员和无凭据请求直接取新 URL 失败；旧 `/im/uploads` 不再服务文件，不得实现别名或重定向。Work 内已有记录仍完整可见。机器 HTTP 使用注册 ACK 的运行凭据，断开 C1 后旧值失效，重连后新值可用；不要把凭据写入验收文档或日志。shadow 生产 HTTP 消费者以受控外部来源输入做集成回归，核实富消息原位调和与发送者归因；本 unit 不要求向真实第三方聊天发消息。

shadow 身份回归需覆盖旧配置 owner 与认证 owner 不同的待同步 saga：先核实 owner JWT 的 `/me`、`/nodes` 查询和节点归属检查，再核实镜像及图片使用运行凭据；运行凭据请求账号／设备管理仍被拒。owner JWT 刷新和运行凭据轮换分别验证，身份校验失败后保留待同步记录并可在修正后恢复；不要记录任何凭据原值。

需要重启 C1 时，在上述终端执行：

```bash
kill -TERM "$C1_PID"
wait "$C1_PID" || true
cd "$RUNTIME_ROOT/c1"
PYTHONPATH="$UNIT_ROOT/src" python -m personal_assistant.main --config "$RUNTIME_ROOT/c1/gateway.yaml" --im-service-url "$IM_URL" --foreground --auto-bind >>gateway.log 2>&1 &
C1_PID=$!
echo "$C1_PID" >gateway.pid
cd "$UNIT_ROOT"
curl -fsS "$IM_URL/openapi.json" >/dev/null
kill -0 "$A2_PID"
kill -0 "$C1_PID"
```

在浏览器确认 C1 离线→在线和新的真实回复。完整栈重新启动先退出本终端完成清理，再用全新 RUNTIME_ROOT 执行创建段；e2e-up 会重置隔离 DB，不能用于保留数据的 IM 重启测试。需保留 DB 的 IM 重启直接停止 `.im.pid` 对应进程，保留 `.e2e-ports.env` 的 IM_PORT／IM_JWT_SECRET，以同一 cwd 重新执行 `IM_JWT_SECRET="$IM_JWT_SECRET" PYTHONPATH="$UNIT_ROOT/src" python -m uvicorn IM.app:app --host 127.0.0.1 --port "$IM_PORT"`，由持久终端记录新 `.im.pid` 并纳入 e2e-down。

## 迁移交接与退出

多人 slash 回归还需包含两个同名、不同实际位置的 Skill：候选保留两行及各自说明，复用同节点同一位置时合并来源 Agent；成员响应不暴露路径。生成 Skill 执行聊天或 fork 后，从 Agent 资料“发消息”仍进入普通私聊，不能把特殊聊天当成联系人私聊复用。

导航回归需覆盖 390／767／768px：手机聊天列表、Agents 列表／资料和“我的”仅有底部主导航；具体聊天隐藏底栏、返回恢复；桌面仅有顶栏。同步确认隐藏导航后没有残留空白、输入区不被底栏遮挡，手机语言设置仍从“我的”进入。

Agent 管理页逐个核对原六分区（single_thread 无 Work），Overview／Sessions 保留原空态；中英文切换后名称、选中状态及管理内容一致。Nodes 完整页面逐节点检查 ID／别名／Agent 数／版本／连接状态与 Heartbeat 快照，保存别名、从在线指定节点创建、离线保留末次心跳及最近错误、WS 推送后刷新可见状态；不要把连接 Heartbeat 与 Agent 的定时任务混为一项。

实施交付时核对 migration-prompt.md 与最终 schema、资源接口和真实启动路径相符；目标库的正常初始化及读写不依赖 conversations 旧共享偏好，也不包含为本次升级新增的迁移／backfill／双写／旧地址兼容路径。用目标格式 fixture 验证历史回看，不在仓库创建迁移脚本来制造测试数据。正式部署的停写、备份、副本转换、保真核对与失败回退只按该文档执行，结果由部署 agent 记录。

退出持久终端前记录本次端口并执行 cleanup_feat554；确认 A1/A2/C1/IM 的已记录 PID 均停止、端口释放。按本轮记录移除实际新建的测试 Skill，只清那些启动前不存在且确由本轮创建的路径。对启动同步的 builtin，恢复原有目录快照，原先不存在的只移除本轮同步项；恢复前核对仍是本轮同步后的内容，如有其他写入则保留现场，不覆盖。不得删除整个 global 根或其他已有 Skill。验证原有内容恢复后，才处理 RUNTIME_ROOT 内的快照。

额外 Gateway 的 yaml、日志、状态与 workspace 位于 RUNTIME_ROOT，不暂存或提交；检查 git status 时排除全部本机运行产物。失败时也执行同样的进程、测试 Skill 和 builtin 收尾，保留必要日志供定位。
