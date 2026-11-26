export type WorkerMcpLaunch = {command: string; args: string[]; env: Record<string, string>};

/** Register only the tools served by this activation's host-owned MCP processes. */
export function hostedWorkerMcp(parent: WorkerMcpLaunch, computer?: WorkerMcpLaunch) {
  const servers = [{server: 'nano-parent', launch: parent, tools: ['send_message']}];
  if (computer) servers.push({server: 'nano-computer', launch: computer, tools: ['computer_use']});
  return servers;
}

/** Match the ACP request and its preceding tool update to one registered MCP tool. */
export function boundAcpTool(
  servers: ReturnType<typeof hostedWorkerMcp>,
  names: string[],
  titles: string[],
  kinds: (string | undefined)[],
  inputs: Record<string, unknown>[],
): string | undefined {
  if (kinds.some(kind => kind && kind !== 'other')) return;
  if (inputs.some(input => ['command', 'CommandLine', 'commandLine', 'command_line'].some(key => key in input))) return;
  for (const {server, tools} of servers) {
    for (const tool of tools) {
      if (inputs.some(input => (input.ServerName != null && input.ServerName !== server) ||
          (input.ToolName != null && input.ToolName !== tool))) continue;
      const direct = `mcp_${server}_${tool}`;
      const directTitle = `Run ${direct}`;
      if (names.every(name => name === direct) && titles.every(title => title === directTitle) &&
          (names.length || (tool === 'send_message' && titles.includes(directTitle)))) return tool;
      if (inputs.some(input => input.ServerName === server && input.ToolName === tool) &&
          names.every(name => name === 'invoke_mcp_tool') &&
          titles.every(title => title === `MCP Tool ${tool}` || (names.length && title === 'Run invoke_mcp_tool')) &&
          (names.length || titles.length)) return tool;
    }
  }
  return undefined;
}
