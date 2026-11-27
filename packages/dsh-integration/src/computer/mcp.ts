import type { ComputerContent } from './backend.js';

/** Connect one seat to a host-selected stdio server with a minimal child environment. */
export async function openMcp(command: string, args: string[], env?: Record<string, string>, cwd?: string) {
  const [{ Client }, { StdioClientTransport }] = await Promise.all([
    import('@modelcontextprotocol/client'),
    import('@modelcontextprotocol/client/stdio'),
  ]);
  const client = new Client({ name: 'nano-computer', version: '1' });
  const transport = new StdioClientTransport({ command, args, env, cwd, stderr: 'ignore' });
  try {
    await client.connect(transport);
    await client.listTools();
  } catch (error) {
    await transport.close();
    throw error;
  }
  async function request(name: string, input: Record<string, unknown>, signal: AbortSignal) {
    signal.throwIfAborted();
    const result = await client.callTool({ name, arguments: input }, { signal });
    if (result.isError) {
      const detail = result.content.find((block) => block.type === 'text');
      throw new Error(detail?.type === 'text' ? detail.text.slice(0, 600) : 'Computer backend refused the operation');
    }
    return result;
  }
  return {
    async call(name: string, input: Record<string, unknown>, signal: AbortSignal): Promise<ComputerContent[]> {
      const result = await request(name, input, signal);
      const content: ComputerContent[] = [];
      for (const block of result.content) {
        if (block.type === 'text') content.push({ type: 'text', text: block.text });
        if (block.type === 'image') content.push({ type: 'image', data: block.data, mimeType: block.mimeType });
      }
      return content;
    },
    async callStructured(
      name: string,
      input: Record<string, unknown>,
      signal: AbortSignal,
    ): Promise<Record<string, unknown>> {
      const value = (await request(name, input, signal)).structuredContent;
      if (!value || typeof value !== 'object' || Array.isArray(value))
        throw new Error('Computer backend returned no structured state');
      return value as Record<string, unknown>;
    },
    close: () => client.close(),
  };
}
