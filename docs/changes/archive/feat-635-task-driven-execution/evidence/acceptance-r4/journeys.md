# Round 4 — Goal 工具逐项选择 Web 复验

- validated_at / executed_base：30a53c2047ea391adba6399a35234883d6c1e8fd；2026-10-22 16:57–17:02 CST。caller交接此版本真实IM/Node/Web，reviewer核对HEAD。隔离入口127.0.0.1:55870，节点wt-nano-feat635-tools-runtime-66207，专用nano用户。
- 独占headless会话feat635-r4-review；1280×900、390×844。完成即close，不碰caller浏览器或服务，不启动模拟器。

## J23 新建默认与三个工具分别保存

Web Agents→New创建review-tools635（工具独立选择验收635）。新建表单与创建后详情，get_goal/create_goal/update_goal均未选；Features没有Goal选项。普通工具默认选择仍在。现有Peer/Global配置mirror也均无Goal工具、无dsh_goal字段。

| 步骤 | 真实页面操作后保存、reload | 确认结果 |
|---|---|---|
| 默认创建 | 不选择Goal三工具 | 三项均不pressed，profile1 |
| 桌面选择create_goal | 单点create_goal，Save Agent，reload | 仅create_goal pressed，profile2 |
| 取消create并选择update | 各自单点，Save Agent，reload | 仅update_goal pressed，profile3 |
| 390窄屏取消update并选get | 各自单点，Save Agent，reload | 仅get_goal pressed，profile4 |
| 390窄屏取消get | Save Agent，reload | 三项均未选，profile5；mirror tools无Goal |

保存完成后页面No changes、Save Agent disabled；重开后的选择与配置镜像一致。桌面浅灰未选与青绿已选胶囊沿用整个Tool Allowlist语言；窄屏自动换行，三项文字完整，不需横向滚动或猜测总开关。两个代表性画面已实际查看，图片仅在仓外/tmp/feat635-r4-default1280.png及/tmp/feat635-r4-update390.png，不入库。

## J24 真实只读调用与收缩

通过Web New chat选择新建Agent，聊天c_4izl9965。profile4仅选get_goal时发送b5b05855691c4d3f9993149189033671：实际调用get_goal，只读，不创建/更新Goal、不改Task、不建Schedule。真实回复1df1c5d7aa0f4057bb023a753f342806 completed；工具call_00_YDLAc2sF7VwgiB9NoPRr8159 completed，返回{"goal":null}。

reviewer独立读取该会话provider请求的工具名：session3455dd25-01f3-423e-9951-203d5c7383ad，17-00-30_526和17-00-32_258两请求的Goal集合均严格为[get_goal]，不依据模型自述推断兄弟工具隐藏。原始请求留在本机LLM_PROXY，不复制入repo。

取消get_goal并保存profile5后，从Web发送普通确认834bbb3e5c6346b8822b13de28a72d7e；回复df6329d76a984380ab7f1b7d349af899完成且可见“已收到配置核验”。17-01-40_029真实provider请求Goal集合为空。没有创建持久Goal，也没有修改Task/Schedule。此Agent最终三项均取消；未更改caller已设置的e2e。
