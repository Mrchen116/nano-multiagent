# 列表标记真实渲染验证

受验内容：基于 origin/main `a103477ea`，仅补齐 global.css 三条列表规则。

在独立 worktree 的 Vite :18575 中，用临时 fixture 直接挂载产品 `MessagePane`、真实 `ReactMarkdown` 和 `global.css`，注入已完成 Agent 消息。未复制生产数据，未连接 IM/Gateway/LLM；这是实际产品组件的浏览器渲染验证，不是完整后端链路验收。截图顶部三个链接仅为 fixture 切换入口，不属于产品新增 UI。

- 390×844 修前：三项 `<ol>` 的计算样式为 `none`，截图无编号（before-mobile.png）。
- 修后：相同正文显示 1/2/3（after-mobile.png、after-desktop.png），桌面1440×1000。
- 非1起始显示7/8，无序与嵌套项目显示圆点，长文本在手机换行可读（nested-mobile.png）。
- GFM task-list-item 保留禁用复选框，无额外圆点；同一列表中的普通项目和任务项下的普通子项仍有圆点；嵌套有序列表仍有编号（mixed-mobile.png、mixed-desktop.png）。
- computed-styles.json：ol decimal、ul disc、任务项 none，fixture 外部 nav ul 仍 none，390px无横向溢出。

证据由主 Agent 使用 Cua 真浏览器获取并逐张目视检查；没有用 jsdom 或截图存在与否替代视觉判断。浏览器视口已恢复默认。临时 fixture 不提交，端口在验收后关闭。
