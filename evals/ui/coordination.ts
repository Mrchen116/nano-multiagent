import { createHash } from 'node:crypto';
import { readFile, readdir } from 'node:fs/promises';
import { join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
export interface GraphNode {
    id: string;
    type: string;
    task: string;
    title: string;
    after: string[];
    order_after?: string[];
    worker?: string;
    content?: {
        text?: string;
        file?: string;
    };
    fallback?: {
        text?: string;
        file?: string;
    };
    attachments?: string[];
    matcher?: unknown;
    when?: unknown;
    after_report?: string | string[];
    source?: string;
    checks?: string[];
    final?: boolean;
    timeout?: number;
}
export interface CaseGraph {
    version: number;
    id: string;
    title: string;
    description: string;
    context: string;
    tasks: Record<string, string>;
    attachments: Record<string, {
        title: string;
        source: string;
    }>;
    worker_titles?: Record<string, string>;
    nodes: GraphNode[];
    sha256?: string;
}
export interface CaseRun {
    url?: string;
    root?: string;
    simulation?: boolean;
    nodes: Record<string, {
        status: string;
        text?: string;
        reason?: string;
        chosen?: string;
        blocked_by?: string[];
        receipt?: unknown;
    }>;
}
export interface Primitive {
    title: string;
    from: string;
    to: string;
    scripted: boolean;
    checks: string[];
}
const suiteRoot = fileURLToPath(new URL('../agent_coordination', import.meta.url));
function sorted(value: unknown): unknown {
    if (Array.isArray(value))
        return value.map(sorted);
    if (value && typeof value === 'object')
        return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([k, v]) => [k, sorted(v)]));
    return value;
}
export async function coordination(runDir?: string) {
    const primitives: Record<string, Primitive> = JSON.parse(await readFile(join(suiteRoot, 'primitives.json'), 'utf8'));
    const cases = [];
    for (const dir of (await readdir(join(suiteRoot, 'cases'), { withFileTypes: true })).filter(d => d.isDirectory()).sort((a, b) => a.name.localeCompare(b.name))) {
        const base = join(suiteRoot, 'cases', dir.name);
        const graph: CaseGraph = JSON.parse(await readFile(join(base, 'case.json'), 'utf8'));
        const ids = new Set(graph.nodes.map(n => n.id));
        if (graph.version !== 1 || ids.size !== graph.nodes.length)
            throw new Error('Invalid coordination graph ' + graph.id);
        for (const node of graph.nodes) {
            if (!primitives[node.type] || [...node.after, ...node.order_after ?? []].some(id => !ids.has(id)))
                throw new Error('Invalid graph node ' + node.id);
            for (const key of ['content', 'fallback'] as const) {
                const content = node[key];
                if (content?.file) {
                    const path = resolve(base, content.file);
                    if (!path.startsWith(resolve(suiteRoot) + sep))
                        throw new Error('Material outside coordination suite');
                    content.text = (await readFile(path, 'utf8')).trim();
                }
            }
        }
        graph.sha256 = createHash('sha256').update(JSON.stringify(sorted(graph))).digest('hex');
        const runs: Record<string, CaseRun> = {};
        if (runDir) {
            const frozen: CaseGraph = JSON.parse(await readFile(join(runDir, 'case.json'), 'utf8'));
            if (frozen.id === graph.id) {
                if (frozen.sha256 !== graph.sha256)
                    throw new Error('Run uses a different case revision; preview its frozen definition separately');
                for (const arm of ['A', 'B']) {
                    try {
                        runs[arm] = JSON.parse(await readFile(join(runDir, `${graph.id}-${arm}.json`), 'utf8'));
                    }
                    catch (error) {
                        if ((error as NodeJS.ErrnoException).code !== 'ENOENT')
                            throw error;
                    }
                }
            }
        }
        cases.push({ id: graph.id, title: graph.title, context: graph.context, graph, primitives, runs,
            notice: Object.values(runs).some(r => r.simulation) ? '模拟状态，仅用于界面检查 · 没有运行模型评测。' : Object.keys(runs).length ? '挂接本地运行记录，节点状态与原始证据一起审查。' : 'Case 定义 · 尚未运行。图中的消息依赖来自同一份回放数据。', stages: [] });
    }
    return { id: 'agent-coordination', title: 'Agent 内部协作', description: 'DAG · 实际派工、同主题续派和授权问答', cases };
}
