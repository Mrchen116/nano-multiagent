# Private services and local observation

Query `service`, and `events` when observing calls. Follow the public Cordis interfaces. These are DSH composition rules: scope controls contributions and event visibility; `isolate` controls service instances. A preset plugin that provides a service isolates its provider and all consumers together.

```yaml
- insert:
    - id: library-group
      name: cordis:group
      group: true
      isolate:
        libraryIndex: true
      config:
        - id: library-provider
          name: ./provider.mjs
        - id: library-consumer
          name: ./consumer.mjs
```

Use the same service name in `provide`, `inject` and `isolate`. Registrations are effects owned by a context: release a file watcher, connection or timer through `ctx.effect` cleanup. Unloading a plugin does not automatically dispose registrations made on another context; retain that disposer too. Do not provide a root service or escape through `ctx.root`.

Nano mounts an instance per Agent preset while installation state is shared. Use an explicit workspace data directory for persistent state; do not assume one in-memory object per workspace. A file index can watch its own data directory, build an initial index and close the watcher on disposal. Existing Workflow/Cron owns long-running scheduled business work.

For runtime observation, Nano supports passive `tools/result`: filter your own tool names, observe the frozen result and do not dispatch tools or replace results from the listener. `tools/change` and `system-prompt/change` are global notifications, not workspace-local business events. The service template demonstrates a private counter; it is in memory and resets on remount/restart.
