import { readFile, mkdtemp, writeFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { runInContext } from 'node:vm';
import { JSDOM } from 'jsdom';
import { expect, it } from 'vitest';
import { catalog, root } from './catalog.js';
it('discovers all coordination cases and resolves full report bodies from the replay definitions', async () => {
    const suites = await catalog();
    expect(suites[2].cases).toHaveLength(8);
    expect(suites[0].cases).toHaveLength(1);
    const cases = suites[3].cases;
    expect(cases.map(c => c.id)).toEqual(['gc01', 'gc02']);
    const graph = cases[0].graph!;
    expect(graph.nodes).toHaveLength(78);
    expect(graph.nodes.find(n => n.id === 'S11')!.content!.text).toContain('713');
    expect(graph.nodes.find(n => n.id === 'U07')!.after).toContain('Q-docs');
    expect(graph.nodes.find(n => n.id === 'U09e')!.attachments).toEqual(['U09e']);
    expect(Object.keys(cases[0].primitives!)).toHaveLength(5);
});
it('keeps graph selection, task filtering and full message details together', async () => {
    const suites = await catalog();
    const c = suites[3].cases[0];
    const source = (await readFile(new URL('./dag.js', import.meta.url), 'utf8')).replace('export function mountDag', 'function mountDag');
    const dom = new JSDOM('<main id="content"></main>', { url: 'http://localhost/token/', runScripts: 'outside-only' });
    try {
        Object.assign(dom.getInternalVMContext(), { testCase: c });
        runInContext(source + ';mountDag(document.querySelector("main"),testCase)', dom.getInternalVMContext());
        const doc = dom.window.document;
        expect(doc.querySelectorAll('[data-node]')).toHaveLength(78);
        (doc.querySelector('[data-node="S11"]') as HTMLButtonElement).click();
        expect(doc.querySelector('.coord-detail')!.textContent).toContain('三条症状');
        expect(doc.querySelector('.coord-detail')!.textContent).toContain('未修改仓库');
        (doc.querySelector('[data-node="U09e"]') as HTMLButtonElement).click();
        expect(doc.querySelector('.coord-detail')!.textContent).toContain('新建群聊原图');
        const select = doc.querySelector('[aria-label="按任务筛选"]') as HTMLSelectElement;
        select.value = 'desktop';
        select.dispatchEvent(new dom.window.Event('change'));
        expect([...doc.querySelectorAll('[data-node]')].every(n => c.graph!.nodes.find(x => x.id === n.getAttribute('data-node'))!.task === 'desktop')).toBe(true);
        expect(doc.querySelector('.coord-detail')!.textContent).not.toContain('新建群聊原图');
    }
    finally {
        dom.window.close();
    }
});
it('discovers a new case from data without adding a dedicated page', async () => {
    const folder = await mkdtemp(join(root, 'evals/agent_coordination/cases/new-'));
    try {
        await writeFile(join(folder, 'case.json'), JSON.stringify({ version: 1, id: 'new-data-case', title: 'New case', description: 'Data only', context: 'Fresh', tasks: { one: 'One' }, attachments: {}, nodes: [{ id: 'U', type: 'user_message', task: 'one', title: 'Ask', after: [], content: { text: 'A new request' } }] }));
        const suites = await catalog();
        const c = suites[3].cases.find(c => c.id === 'new-data-case')!;
        expect(c.graph!.nodes[0].content!.text).toBe('A new request');
        expect(c.stages).toEqual([]);
    }
    finally {
        await rm(folder, { recursive: true, force: true });
    }
});
