export interface WorkerPermissionAction {
  name: string;
  input: unknown;
  summary: Record<string, unknown>;
}
interface WorkerDecision {
  allow: boolean;
  reason: string;
  report?: boolean;
}
export type WorkerPermissionHandler = (
  action: WorkerPermissionAction,
  signal: AbortSignal,
) => Promise<WorkerDecision>;

type RpcId = string | number;

/** Bind an asynchronous decision to one live request on this process and turn. */
export class WorkerPermissions {
  private readonly pending = new Map<RpcId, { call: string; controller: AbortController }>();
  private readonly seen = new Set<RpcId>();
  open = false;

  constructor(private readonly decide?: WorkerPermissionHandler) {}

  begin() {
    this.stop();
    this.open = true;
    this.seen.clear();
  }

  stop() {
    this.open = false;
    for (const id of this.pending.keys()) this.cancel(id);
  }

  cancel(id: RpcId) {
    this.pending.get(id)?.controller.abort();
  }

  cancelCall(call: string) {
    for (const [id, entry] of this.pending) if (entry.call === call) this.cancel(id);
  }

  request(
    id: RpcId,
    call: string,
    action: WorkerPermissionAction,
    respond: (decision: WorkerDecision) => void,
  ) {
    if (!this.open || !this.decide) {
      respond({ allow: false, reason: 'No live worker approval is available.' });
      return;
    }
    if (this.seen.has(id)) {
      if (this.pending.has(id)) this.cancel(id);
      else respond({ allow: false, reason: 'This request has already ended.' });
      return;
    }
    this.seen.add(id);
    const controller = new AbortController();
    this.pending.set(id, { call, controller });
    const finish = (decision: WorkerDecision) => {
      if (!this.pending.delete(id)) return;
      respond(decision);
    };
    controller.signal.addEventListener(
      'abort',
      () => finish({ allow: false, reason: 'Worker request cancelled.' }),
      { once: true },
    );
    void this.decide(structuredClone(action), controller.signal).then(
      (decision) => {
        if (!controller.signal.aborted) finish(decision);
      },
      () => {
        if (!controller.signal.aborted) finish({ allow: false, reason: 'Worker approval failed.' });
      },
    );
  }
}

export type WorkerMcpLaunch = { command: string; args: string[]; env: Record<string, string> };

/** Only host-launched servers with their own authorization belong in this registration. */
export function hostedWorkerMcp(parent: WorkerMcpLaunch) {
  return [{ server: 'nano-parent', launch: parent, tools: ['send_message'] }];
}

/** ACP uses both native tool names and fixed direct/proxy titles, depending on the CLI build. */
export function identifyHostedAcpTool(
  hosted: ReturnType<typeof hostedWorkerMcp>,
  names: string[],
  titles: string[],
  kind: string | undefined,
  input: Record<string, unknown>,
): 'bound' | 'conflict' | 'ordinary' {
  for (const { server, tools } of hosted) {
    for (const tool of tools) {
      const direct = `mcp_${server}_${tool}`;
      const directTitle = `Run ${direct}`;
      const proxyTarget = input.ServerName === server && input.ToolName === tool;
      if (!names.includes(direct) && !titles.includes(directTitle) && !proxyTarget) continue;

      const incompatible =
        (kind && kind !== 'other') ||
        ['command', 'commandLine', 'command_line', 'CommandLine'].some((key) => key in input) ||
        (input.ServerName != null && input.ServerName !== server) ||
        (input.ToolName != null && input.ToolName !== tool);
      if (incompatible || (!names.length && !titles.length)) return 'conflict';
      if (names.every((name) => name === direct) && titles.every((title) => title === directTitle))
        return 'bound';
      if (
        proxyTarget &&
        names.every((name) => name === 'invoke_mcp_tool') &&
        titles.every(
          (title) => title === `MCP Tool ${tool}` || (names.length > 0 && title === 'Run invoke_mcp_tool'),
        )
      )
        return 'bound';
      return 'conflict';
    }
  }
  return 'ordinary';
}
