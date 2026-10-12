import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createServer } from "node:http";
import { expect, it } from "vitest";
import { prepareProfile, RuntimeClient } from "../lib/client.js";

it("uses the configured search backend and preserves fetch prompt extraction and raw fallback through native tools", async () => {
  const requests: string[] = [];
  const server = createServer((req, res) => {
    requests.push(req.url!);
    res.setHeader("content-type", "application/json");
    res.end(
      JSON.stringify({
        results: [
          {
            url: "https://example.com/second",
            title: "Second",
            content: "B",
            score: 1,
          },
          {
            url: "https://example.com/first",
            title: "First",
            content: "A",
            score: 9,
          },
        ],
      }),
    );
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const home = await mkdtemp(join(tmpdir(), "nano-web-"));
  let client: RuntimeClient | undefined;
  let logs = "";
  try {
    await writeFile(
      join(home, "fixture.mjs"),
      `import { writeFile } from 'node:fs/promises';
export const name = 'web-fixture'; export const inject = ['web', 'llm', 'tools'];
export function apply(ctx) {
 ctx.web.registerFetchProvider({ id: 'fixture', available: () => true, async fetch({url}, signal) { signal?.throwIfAborted(); return {url, statusCode: 200, body: {kind: 'html', content: '<h1>Raw Page</h1><p>VALUE_581</p>'}, truncated: false}; } });
 const seen = new Set();
 ctx.on('llm/stream', async function* (o) {
   const text = JSON.stringify(o);
   const extraction = text.includes('Nano web extraction');
   const input = extraction ? o.messages.findLast(m => m.role === 'user') : o.messages.findLast(m => m.role === 'user' && ['search', 'raw', 'extract', 'fallback'].includes(m.content[0]?.text));
   if (extraction) {
     await writeFile(process.env.DSH_HOME + '/extraction.json', JSON.stringify(o));
     if (text.includes('EXTRACT_FAIL')) { yield {type: 'finish', reason: {kind: 'error', error: {name: 'FixtureError', code: 'FIXTURE', message: 'extraction unavailable'}}}; return; }
     yield {type: 'block-end', index: 0, block: {type: 'text', text: 'Extracted VALUE_581'}}; yield {type: 'finish', reason: {kind: 'stop'}}; return;
   }
   if (seen.has(input.id)) { yield {type: 'block-end', index: 0, block: {type: 'text', text: 'done'}}; yield {type: 'finish', reason: {kind: 'stop'}}; return; }
   seen.add(input.id); const action = input.content[0].text;
   const args = action === 'search' ? {queries: ['nano native web']} : {url: 'https://example.com', ...(action === 'raw' ? {} : {prompt: action === 'extract' ? 'EXTRACT_VALUE' : 'EXTRACT_FAIL'})};
   yield {type: 'block-end', index: 0, block: {type: 'tool-call', id: action + '-call', name: action === 'search' ? 'web_search' : 'web_fetch', arguments: JSON.stringify(args)}}; yield {type: 'finish', reason: {kind: 'tool-calls'}};
 });
 ctx.on('tools/result', (exec, result) => { void writeFile(process.env.DSH_HOME + '/' + exec.callId + '.json', JSON.stringify(result)); });
}`,
    );
    await prepareProfile(home, [
      {
        id: "web",
        config: { searchProvider: "searxng", fetchProvider: "fixture" },
      },
      { id: "tool-web", config: { searchMaxResults: 1, fetch: false } },
      { insert: [{ id: "web-fixture", name: join(home, "fixture.mjs") }] },
    ]);
    client = new RuntimeClient({
      home,
      cwd: home,
      env: {
        SEARXNG_URL: `http://127.0.0.1:${(server.address() as { port: number }).port}`,
        DSH_WEB_SEARCH_PROVIDER: "searxng",
        DSH_WEB_FETCH_PROVIDER: "fixture",
      },
      onLog: (text) => {
        logs += text;
      },
    });
    await client.rpc.request("initialize", {
      protocol: 1,
      agents: [
        {
          agentId: "a",
          revision: "1",
          provider: "deepseek-official",
          model: "deepseek-flash",
          toolAllowlist: ["web_search", "web_fetch"],
        },
      ],
      bindings: [],
    });
    await client.rpc.request("session.ensure", {
      sessionId: "web",
      agentId: "a",
      revision: "1",
      ownerId: "owner",
      cwd: home,
    });
    for (const action of ["search", "raw", "extract", "fallback"]) {
      await client.rpc.request("session.submit", {
        sessionId: "web",
        inputId: action,
        mode: "followup",
        content: [{ type: "text", text: action }],
        source: {
          kind: "human",
          actorId: "owner",
          channel: "test",
          messageId: action,
        },
      });
      await expect
        .poll(
          async () =>
            (
              (await client!.rpc.request("session.lookup", {
                sessionId: "web",
                inputId: action,
              })) as { terminal?: { kind: string } }
            ).terminal?.kind,
        )
        .toBe("completed");
      const result = await readFile(join(home, action + "-call.json"), "utf8");
      expect(JSON.parse(result).isError, result).not.toBe(true);
      if (action === "search") {
        expect(result).toContain("https://example.com/first");
        expect(result).not.toContain("https://example.com/second");
      } else if (action === "extract") {
        expect(result).toContain("Extracted VALUE_581");
        expect(result).not.toContain("Raw Page");
      } else expect(result).toContain("Raw Page");
    }
    expect(requests).toHaveLength(1);
    expect(requests[0]).toContain("q=nano+native+web");
    expect(requests[0]).toContain("format=json");
    const extraction = JSON.parse(
      await readFile(join(home, "extraction.json"), "utf8"),
    );
    expect(extraction.provider).toBe("deepseek-official");
    expect(JSON.stringify(extraction)).toContain("untrusted");
    await client.shutdown();
    client = undefined;
  } catch (error) {
    throw new Error(`${String(error)}\n${logs}`, { cause: error });
  } finally {
    if (client) {
      client.process.kill("SIGKILL");
      await client.exited;
    }
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
    await rm(home, { recursive: true, force: true });
  }
}, 20_000);

it("keeps DuckDuckGo and Brave backend wire formats and propagates network failures", async () => {
  const { vi } = await import("vitest");
  const { searchProviders } = await import("../lib/web.js");
  const fetch = vi.fn(async (url: URL, options?: RequestInit) => {
    options?.signal?.throwIfAborted();
    if (url.hostname === "html.duckduckgo.com")
      return new Response(
        '<div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Ftarget">Example title</a><div class="result__snippet">Some evidence</div></div>',
      );
    return new Response(
      JSON.stringify({
        web: {
          results: [
            {
              url: "https://example.com/brave",
              title: "Brave title",
              description: "Brave evidence",
            },
          ],
        },
      }),
    );
  });
  vi.stubGlobal("fetch", fetch);
  try {
    const providers = searchProviders({ BRAVE_API_KEY: "fixture-key" });
    const ddg = await providers
      .find((p) => p.id === "duckduckgo")!
      .search({ query: "a & b" });
    expect(ddg.sources).toEqual([
      {
        url: "https://example.com/target",
        title: "Example title",
        snippet: "Some evidence",
      },
    ]);
    expect(fetch.mock.calls[0]![0].searchParams.get("q")).toBe("a & b");
    const brave = await providers
      .find((p) => p.id === "brave")!
      .search({ query: "query", maxResults: 3 });
    expect(brave.sources[0]!.snippet).toBe("Brave evidence");
    expect(fetch.mock.calls[1]![0].searchParams.get("count")).toBe("3");
    expect(fetch.mock.calls[1]![1]!.headers).toEqual({
      "X-Subscription-Token": "fixture-key",
    });
    fetch.mockRejectedValueOnce(new Error("network failed"));
    await expect(providers[1]!.search({ query: "query" })).rejects.toThrow(
      "network failed",
    );
    await expect(
      providers[1]!.search({ query: "query" }, AbortSignal.abort()),
    ).rejects.toThrow();
  } finally {
    vi.unstubAllGlobals();
  }
});
