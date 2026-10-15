# 私有服务与局部监听

先 `describe_api(topic: service)`；涉及事件时再查 `events`。服务是插件内部复用状态或能力，不是第二个 Agent Loop。模板以一次成功工具调用的计数演示隔离服务、consumer 与被动事件；计数在内存中，重启/重新挂载清零，不是持久数据库。

## 服务隔离

普通 `ctx.provide` 不会因为代码装在 workspace 就自动成为私有服务。provider 和 consumer 必须位于同一隔离 group：

```yaml
- insert:
    - id: my-plugin-group
      name: cordis:group
      group: true
      isolate:
        myService: true
      config:
        - id: my-provider
          name: ./provider.mjs
        - id: my-consumer
          name: ./consumer.mjs
```

provider `ctx.provide('myService', value)`，consumer `inject = ['myService', ...]` 后通过 `ctx.myService` 使用。服务名、isolate 名和 inject 必须一致。根服务泄漏会被拒绝；不要靠 `ctx.root` 逃离隔离范围。

持久索引/业务状态使用明确的 workspace 数据目录，通过插件 config 或工具当前 workspace 指定。实例按 Agent preset 挂载，不是假设整个 workspace 只有一个进程内对象；同目录共享写入要考虑实际多实例行为。用户数据与安装产物分开，关闭插件不能悄悄删除业务资料。

## 局部观察

首版支持的运行时被动观察点是 `tools/result`：

```js
ctx.on('tools/result', (exec, result) => {
  if (exec.name !== 'my_plugin_search' || result.isError) return;
  // 这里只更新自己拥有的统计，不复制用户输入或敏感结果。
});
```

它按执行 Agent 的 scope 分发，preset 内监听覆盖其后代 scope。参数名和事件模式以当前 types 为准。结果被冻结，不能修改；该 emit listener 不返回替换值，也不接收 waterfall 的 next。不要在 observer 中触发新工具、另起 Agent 或改变审批结果。

`tools/change` 和 `system-prompt/change` 是全局通知，不是局部业务事件；不要因名字看起来合适就用它们监听当前 workspace。其他公开事件不在本入口推荐支持面，先核实具体作用域与产品责任，不猜。

## 文件变化与 cleanup

索引可以监听用户指定的数据目录。文件 watcher 属于你自己的资源，不会因为存在于 apply 中就自动关闭：

```js
ctx.effect(() => {
  const watcher = watch(config.dataDir, () => { /* 标记索引需要刷新 */ });
  return () => watcher.close();
});
```

在适当位置 import Node 的 `watch`，先建立初始索引；变化只做必要刷新，删除文件时也更新索引。停用后 watcher 必须关闭；timer、连接、后台任务同样由 effect cleanup 终止并等待退出。长任务用已有 Workflow/Cron 管理，避免卸载后仍运行。

验证包含：更新资料后查询看到新内容、另一 workspace 的事件不计入本插件、关闭后不再观察变化。实际出现文件监听边界问题再修复，不先造通用同步框架。
