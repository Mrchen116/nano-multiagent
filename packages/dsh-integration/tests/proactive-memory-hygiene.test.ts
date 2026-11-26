import { execFileSync } from 'node:child_process';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { Context } from '@deepseek-ai/cordis';
import { LocalFileSystem } from '@deepseek-ai/dsh-fs-local';
import { MemoryDocuments, proactivitySignalsLimit } from '../src/knowledge/memory-documents.js';
import { qualifiedEvents } from '../src/knowledge/memory-source-view.js';
import { MemorySources } from '../src/knowledge/memory-sources.js';

const fs = new LocalFileSystem(new Context(), { cwd: process.cwd(), diffBasisMaxBytes: 10485760 });
const cleanups: Array<() => Promise<void>> = [];
afterEach(async () => {
  for (const cleanup of cleanups.splice(0).reverse()) await cleanup();
});

async function openMemory(role: 'personal' | 'expert') {
  const workspace = await mkdtemp(join(tmpdir(), `nano-proactive-hygiene-${role}-`));
  cleanups.push(() => rm(workspace, { recursive: true, force: true }));
  const documents = await MemoryDocuments.open(workspace, role, fs);
  cleanups.push(() => documents.close());
  return { documents, root: documents.root, workspace };
}

function commitAll(root: string) {
  execFileSync('git', ['add', '-A'], { cwd: root });
  execFileSync('git', ['-c', 'user.name=Test', '-c', 'user.email=test@localhost', 'commit', '-qm', 'test'], { cwd: root });
}

describe('MemoryDocuments.consolidationIssues structure and link hygiene gate', () => {
  it('seeds personal MEMORY.md with a valid proactive section and keeps repositoryIssues decoupled from structural checks', async () => {
    const { documents, root } = await openMemory('personal');
    expect((await documents.context()).entry).toContain('## 主动性与介入偏好');
    expect(await documents.repositoryIssues()).toEqual([]);
    expect(await documents.consolidationIssues()).toEqual([]);

    // Legacy PA MEMORY.md without proactive section does NOT trigger idle repositoryIssues, only consolidationIssues!
    await writeFile(join(root, 'MEMORY.md'), '# Personal memory\n\nLegacy content without proactive section.\n');
    commitAll(root);
    expect(await documents.repositoryIssues()).toEqual([]);
    expect(await documents.consolidationIssues()).toEqual([
      expect.objectContaining({ path: 'MEMORY.md', reason: expect.stringContaining('主动性与介入偏好') }),
    ]);
  });

  it('enforces canonical top-level directories per role', async () => {
    const personal = await openMemory('personal');
    await mkdir(join(personal.root, 'projects'), { recursive: true });
    await writeFile(join(personal.root, 'projects/p1.md'), '# Wrong dir for PA\n');
    expect(await personal.documents.consolidationIssues()).toContainEqual(
      expect.objectContaining({ path: 'projects', reason: expect.stringContaining('outside the allowed personal layout') }),
    );

    const expert = await openMemory('expert');
    await mkdir(join(expert.root, 'workstreams'), { recursive: true });
    await writeFile(join(expert.root, 'workstreams/w1.md'), '# Wrong dir for expert\n');
    expect(await expert.documents.consolidationIssues()).toContainEqual(
      expect.objectContaining({ path: 'workstreams', reason: expect.stringContaining('outside the allowed expert layout') }),
    );
  });

  it('validates PA MEMORY.md proactive H2/H3 buckets and forbids referencing proactivity-signals.md', async () => {
    const { documents, root } = await openMemory('personal');
    await mkdir(join(root, 'workstreams'), { recursive: true });
    await writeFile(join(root, 'workstreams/launch.md'), '# Launch SOP\n');

    // Valid four-bucket Chinese structure with relative link to workstream passes.
    await writeFile(
      join(root, 'MEMORY.md'),
      [
        '# Personal memory',
        '',
        '## 主动性与介入偏好',
        '',
        '### 积极盯紧与提前备料',
        '- 发布会排期变动时主动核对清单（详见 [Launch SOP](workstreams/launch.md)）。',
        '',
        '### 低打扰挂卡与静默跟进',
        '- 长期读书笔记只提待拍板卡，不发消息打断。',
        '',
        '### 免打扰禁区',
        '- 家庭日常反思与健身打卡零提卡、零追问。',
        '',
        '### 触达时机与汇总方式',
        '- 21:30–08:30 保持静默，早间 09:00 合并一条消息汇报。',
        '',
      ].join('\n'),
    );
    expect(await documents.consolidationIssues()).toEqual([]);

    // Invalid H3 bucket, H4 subheading, duplicate bilingual bucket, and proactivity-signals.md reference are all caught.
    await mkdir(join(root, 'knowledge'), { recursive: true });
    await writeFile(join(root, 'knowledge/proactivity-signals.md'), '# Signals\n\n- [2026-11-26] Seen 1\n');
    await writeFile(
      join(root, 'MEMORY.md'),
      [
        '# Personal memory',
        '',
        '## 主动性与介入偏好',
        '',
        '### 免打扰禁区',
        '- 家庭话题不建卡。',
        '',
        '### No-Intrusion Boundaries',
        '- Duplicate bilingual bucket.',
        '',
        '### 自创随意分栏',
        '- Unsupported bucket.',
        '',
        '#### 四级子标题',
        '- Deeper heading.',
        '',
        'See [signals](knowledge/proactivity-signals.md).',
      ].join('\n'),
    );
    const issues = await documents.consolidationIssues();
    expect(issues.filter(item => item.path === 'MEMORY.md').map(item => item.reason)).toEqual(
      expect.arrayContaining([
        expect.stringContaining('never link to or reference knowledge/proactivity-signals.md'),
        expect.stringContaining('Duplicate proactive H3 bucket'),
        expect.stringContaining('Unsupported proactive H3 bucket'),
        expect.stringContaining('only allows H3'),
      ]),
    );
  });

  it('enforces proactivity-signals.md top-level list structure, <= 20 items, and <= 4,000 UTF-16 code units', async () => {
    const { documents, root } = await openMemory('personal');
    await mkdir(join(root, 'knowledge'), { recursive: true });
    const signalsPath = join(root, 'knowledge/proactivity-signals.md');

    // Valid list with brief header line passes.
    await writeFile(
      signalsPath,
      '# 主动性隐式信号观察池\n\n仅由 Dreaming 维护的单次观察记录。\n\n- **健康打卡**（seen: 1，2026-11-26，未采纳待拍板卡 tg_1/n1）\n',
    );
    expect(await documents.consolidationIssues()).toEqual([]);

    // 21 items + H3 heading + prose after list fails.
    const twentyOneItems = Array.from({ length: 21 }, (_, idx) => `- Signal item ${idx + 1}`).join('\n');
    await writeFile(signalsPath, `# Signals\n\n### Bad Subheading\n\n${twentyOneItems}\n\nTrailing prose paragraph bypass.\n`);
    const structIssues = await documents.consolidationIssues();
    expect(structIssues.map(item => item.reason)).toEqual(
      expect.arrayContaining([
        expect.stringContaining('without H3+ subheadings'),
        expect.stringContaining('top-level list items (with at most one brief header/empty-state line)'),
        expect.stringContaining('has 21 top-level list items; limit is 20'),
      ]),
    );

    // > 4,000 UTF-16 code units fails.
    await writeFile(signalsPath, `# Signals\n\n- ${'长'.repeat(proactivitySignalsLimit)}\n`);
    expect(await documents.consolidationIssues()).toContainEqual(
      expect.objectContaining({ path: 'knowledge/proactivity-signals.md', reason: expect.stringContaining(`limit is ${proactivitySignalsLimit}`) }),
    );
  });

  it('checks AST relative .md links with URI decoding and route exemptions while ignoring code blocks', async () => {
    const { documents, root } = await openMemory('personal');
    await mkdir(join(root, 'knowledge'), { recursive: true });
    await writeFile(join(root, 'knowledge/中文主题.md'), '# 中文主题\n');
    await writeFile(
      join(root, 'knowledge/valid-links.md'),
      [
        '# Valid links',
        '',
        '- Encoded Chinese relative link: [中文主题](%E4%B8%AD%E6%96%87%E4%B8%BB%E9%A2%98.md#overview)',
        '- External URL: [Docs](https://example.com/missing.md)',
        '- Mailto: [Mail](mailto:test@example.com)',
        '- Anchor only: [Section](#local)',
        '- Task route: [Card](/tasks/tg_123?scope=n1&node=n2)',
        '- IM attachment route: [File](/im/v1/conversations/c_1/attachments/att_1)',
        '',
        '```markdown',
        '[Ignored broken link inside fenced code](nonexistent-in-code.md)',
        '```',
      ].join('\n'),
    );
    expect(await documents.consolidationIssues()).toEqual([]);

    await writeFile(
      join(root, 'knowledge/broken-links.md'),
      [
        '# Broken links',
        '',
        '- Missing page: [Missing](missing-page.md)',
        '- Escape root: [Escape](../../outside.md)',
        '- Malformed URI: [Bad](%E0%A4%A.md)',
        '- Non-markdown file: [Txt](notes.txt)',
        '- Unsupported root path: [Root](/etc/passwd)',
      ].join('\n'),
    );
    const broken = (await documents.consolidationIssues()).filter(item => item.path === 'knowledge/broken-links.md').map(item => item.reason);
    expect(broken).toEqual(
      expect.arrayContaining([
        expect.stringContaining('Broken relative link "missing-page.md"'),
        expect.stringContaining('escapes the formal memory repository'),
        expect.stringContaining('Malformed percent-encoded link'),
        expect.stringContaining('must point to a .md document'),
        expect.stringContaining('Unsupported root-relative link "/etc/passwd"'),
      ]),
    );
  });
});

describe('MemorySources task-context retention and cross-night deduplication', () => {
  it('retains task-context events labeled [task context] and skips messageIds in excludeTaskContextIds', async () => {
    const taskEvent = {
      seq: 0,
      time: 1700000000010,
      type: 'user/message',
      data: {
        id: 'msg-task-1',
        source: {
          kind: 'nano-system',
          channel: 'task-context',
          actorId: 'pa',
          messageId: 'msg-task-1',
          conversationId: 'c_owner',
        },
        content: [{ type: 'text', text: 'Task update: {"previous_status":"proposed","status":"closed"}' }],
      },
    };
    const stepEnd = { seq: 1, time: 1700000000020, type: 'step/end', data: {} };
    expect(qualifiedEvents([taskEvent as never])).toHaveLength(1);

    const ctx = {
      sessions: { get: () => undefined, flush: async () => true },
      sessionQuery: {
        observeSession: async () => ({
          source: 'prepared',
          revision: 'durable',
          header: { cwd: '/owner', origin: 'root' },
          inheritedEventCount: 0,
          events: structuredClone([taskEvent, stepEnd]),
          cursor: 1,
          [Symbol.dispose]: () => {},
        }),
      },
    };
    const binding = { agentId: 'pa', sessionId: 's', ownerId: 'owner', cwd: '/owner', revision: '1' };
    const sources = new MemorySources(ctx as never, new Map([['s', binding]]));
    const streams = { s: { baseline: -1, cursor: -1 } };

    const included = await sources.freeze('pa', streams, { maxInputTokens: 2000 });
    expect(included.units).toHaveLength(1);
    expect(included.conversations).toContain('c_owner');
    expect(included.text).toContain('[task context]');
    expect(included.text).toContain('"previous_status":"proposed"');

    const deduplicated = await sources.freeze('pa', streams, {
      maxInputTokens: 2000,
      excludeTaskContextIds: new Set(['msg-task-1']),
    });
    expect(deduplicated.units).toEqual([]);
    expect(deduplicated.filtered).toBeGreaterThanOrEqual(1);
    expect(deduplicated.ranges[0]?.through).toBe(1);
  });
});
