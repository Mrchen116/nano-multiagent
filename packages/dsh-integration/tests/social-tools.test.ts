import { mkdtemp, writeFile, readFile, rm, realpath } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, it } from "vitest";
import type { Context } from "@deepseek-ai/cordis";
import type { ToolDefinition, ToolRunContext } from "@deepseek-ai/dsh-tools";
import { apply } from "../src/assets/social-tools.js";

it("preserves the four existing fixed-command contracts and rejects invalid URLs before spawning", async () => {
  const home = await mkdtemp(join(tmpdir(), "nano-social-"));
  const tools = new Map<string, ToolDefinition>();
  try {
    const executable = join(home, "reader");
    await writeFile(
      executable,
      `#!${process.execPath}
const fs = require('node:fs'); const args = process.argv.slice(2); fs.appendFileSync('calls.jsonl', JSON.stringify(args) + '\\n');
if(args[0] === 'twitter') console.log(JSON.stringify([{id: '123', author: 'Owner', url: 'https://x.com/Owner/status/123', text: 'single X post', created_at: 'today'}]));
else if(args[0] === 'xiaohongshu') console.log(JSON.stringify([{field: 'title', value: 'Single note'}, {field: 'content', value: 'note body'}]));
else if(args[0] === 'download') { fs.writeFileSync('123.mp4', 'fixture'); console.log(JSON.stringify({ok: true, download: {path: process.cwd() + '/123.mp4', size_bytes: 7, sha256: 'a'.repeat(64)}})); }
else console.log(JSON.stringify({ok: true, work: {id: '123', canonical_url: args[1], author: {nickname: 'reader'}, media: {type: 'video', available: true}, text: 'video body'}}));
`,
      { mode: 0o755 },
    );
    apply(
      {
        tools: {
          register: (tool: ToolDefinition) => {
            tools.set(tool.name, tool);
          },
        },
      } as unknown as Context,
      {
        opencli: executable,
        douyin: executable,
        opencliCwd: home,
        douyinCwd: home,
        downloadDir: home,
      },
    );
    const execute = (
      name: string,
      url: string,
      signal = new AbortController().signal,
    ) =>
      tools
        .get(name)!
        .execute({ url }, { signal } as ToolRunContext) as Promise<any>;
    expect(
      await execute("read_x_post", "https://x.com/Owner/status/123"),
    ).toMatchObject({ ok: true, post: { text: "single X post" } });
    expect(
      await execute(
        "read_xiaohongshu_note",
        "https://www.xiaohongshu.com/explore/abcdef0123456789abcdef01?xsec_token=fixture",
      ),
    ).toMatchObject({
      ok: true,
      note: { title: "Single note", content: "note body" },
    });
    expect(
      await execute("read_douyin_video", "https://www.douyin.com/video/123"),
    ).toMatchObject({ ok: true, video: { text: "video body" } });
    expect(
      await execute(
        "download_douyin_video",
        "https://www.douyin.com/video/123",
      ),
    ).toMatchObject({
      ok: true,
      size_bytes: 7,
      path: join(await realpath(home), "123.mp4"),
    });
    for (const url of [
      "http://x.com/Owner/status/123",
      "https://x.com/Owner/status/123?search=all",
      "https://x.com:443/Owner/status/123",
      "https://x.com/Owner/status/123\n",
    ])
      expect(await execute("read_x_post", url)).toMatchObject({
        ok: false,
        error: { code: "invalid_input" },
      });
    const calls = (await readFile(join(home, "calls.jsonl"), "utf8"))
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    expect(calls).toHaveLength(4);
    expect(calls[0]).toEqual([
      "twitter",
      "thread",
      "https://x.com/Owner/status/123",
      "--limit",
      "1",
      "-f",
      "yaml",
    ]);
    expect(
      await execute("read_x_post", "https://x.com/Owner/status/456"),
    ).toMatchObject({ ok: false, error: { code: "item_mismatch" } });
    await writeFile(
      executable,
      `#!${process.execPath}\nrequire('node:fs').writeFileSync('reader.pid', String(process.pid)); setInterval(() => {}, 1000);\n`,
      { mode: 0o755 },
    );
    const abort = new AbortController();
    const pending = execute(
      "read_douyin_video",
      "https://www.douyin.com/video/123",
      abort.signal,
    );
    const rejected = expect(pending).rejects.toThrow();
    await expect
      .poll(async () =>
        readFile(join(home, "reader.pid"), "utf8").catch(() => ""),
      )
      .not.toBe("");
    const pid = Number(await readFile(join(home, "reader.pid"), "utf8"));
    abort.abort();
    await rejected;
    expect(() => process.kill(pid, 0)).toThrow();
  } finally {
    await rm(home, { recursive: true, force: true });
  }
});
