// The same graph is consumed by the replay engine. This module only presents it.
const labels = { pending: '未运行', waiting: '等待前置', sending: '发送中', passed: '已触发', failed: '失败', blocked: '被前置阻断', untriggered: '前置未触发', uncertain: '发送结果待核对' };
const el = (tag, value, cls) => { const e = document.createElement(tag); if (value !== undefined)
    e.textContent = value; if (cls)
    e.className = cls; return e; };
export function mountDag(container, c) {
    const graph = c.graph, nodes = graph.nodes, byId = new Map(nodes.map(n => [n.id, n]));
    let selected = nodes[0].id, task = '', zoom = 1, mode = window.innerWidth < 800 ? 'list' : 'graph', arm = Object.keys(c.runs ?? {})[0] ?? '';
    const root = el('section', undefined, 'coord-case'), toolbar = el('div', undefined, 'coord-toolbar');
    const selector = el('select');
    selector.setAttribute('aria-label', '按任务筛选');
    selector.append(new Option('全部任务', ''));
    Object.entries(graph.tasks).forEach(([key, name]) => selector.append(new Option(name, key)));
    const modeButton = el('button'), zoomInput = el('input'), zoomLabel = el('span', '100%');
    zoomInput.type = 'range';
    zoomInput.min = '45';
    zoomInput.max = '130';
    zoomInput.value = '100';
    zoomInput.setAttribute('aria-label', 'DAG 缩放');
    const count = el('span', undefined, 'coord-count');
    toolbar.append(selector, modeButton, zoomInput, zoomLabel, count);
    if (Object.keys(c.runs ?? {}).length) {
        const run = el('select');
        run.setAttribute('aria-label', '实验组');
        Object.keys(c.runs).forEach(key => run.append(new Option(key + ' 组', key)));
        run.onchange = () => { arm = run.value; draw(); };
        toolbar.append(run);
    }
    const legend = el('p', '实线为必须成功的前置，虚线为只约束顺序。脚本投递消息，观察节点等待主 Agent 的真实动作。', 'coord-legend');
    const panel = el('div', undefined, 'coord-panel'), viewport = el('div', undefined, 'coord-viewport'), detail = el('article', undefined, 'coord-detail');
    detail.setAttribute('aria-label', '节点详情');
    panel.append(viewport, detail);
    root.append(toolbar, legend, panel);
    container.append(root);
    const status = n => c.runs?.[arm]?.nodes?.[n.id]?.status ?? 'pending';
    function link(id) { const b = el('button', id + ' · ' + byId.get(id).title, 'coord-dependency'); b.onclick = () => { selected = id; task = ''; selector.value = ''; draw(); viewport.querySelector(`[data-node="${CSS.escape(id)}"]`)?.scrollIntoView({ block: 'nearest', inline: 'nearest' }); }; return b; }
    function showDetail() {
        const n = byId.get(selected), p = c.primitives[n.type], state = c.runs?.[arm]?.nodes?.[n.id];
        detail.replaceChildren(el('small', n.id + ' · ' + graph.tasks[n.task]), el('h3', n.title));
        detail.append(el('p', p.from + ' → ' + (n.worker ? p.to + ' · ' + (graph.worker_titles?.[n.worker] ?? n.worker) : p.to), 'coord-direction'), el('span', labels[status(n)] ?? status(n), 'coord-state ' + status(n)));
        detail.append(el('p', p.scripted ? '脚本投递' : '观察主 Agent 的实际行为', 'coord-actor'));
        if (n.content?.text)
            detail.append(el('h4', '消息正文'), el('pre', state?.text ?? n.content.text));
        if (n.attachments?.length) {
            detail.append(el('h4', '附件'));
            for (const key of n.attachments) {
                const a = graph.attachments[key];
                detail.append(el('p', a.title + ' · ' + a.source + '\n原图由运行时从私有材料映射读取。', 'coord-attachment'));
            }
        }
        detail.append(el('h4', '必须成功的前置'));
        if (n.after.length)
            n.after.forEach(id => detail.append(link(id)));
        else
            detail.append(el('p', '无，可独立触发'));
        if (n.order_after?.length) {
            detail.append(el('h4', '顺序约束'));
            n.order_after.forEach(id => detail.append(link(id)));
        }
        if (n.fallback) {
            detail.append(el('h4', '缺少前文时的备用措辞'), el('pre', n.fallback.text));
        }
        if (n.matcher || n.when) {
            const d = el('details');
            d.append(el('summary', '查看触发条件'), el('pre', JSON.stringify(n.matcher ?? n.when, null, 2)));
            detail.append(d);
        }
        detail.append(el('h4', '这一类节点固定查什么'));
        const ul = el('ul');
        [...p.checks, ...n.checks ?? []].forEach(t => ul.append(el('li', t)));
        detail.append(ul);
        if (n.source)
            detail.append(el('h4', '来源与清洗说明'), el('p', n.source));
        if (state) {
            detail.append(el('h4', '运行证据'));
            if (state.reason)
                detail.append(el('p', state.reason));
            if (state.blocked_by)
                state.blocked_by.forEach(id => detail.append(link(id)));
            const d = el('details');
            d.append(el('summary', '展开原始收据'), el('pre', JSON.stringify(state, null, 2)));
            detail.append(d);
        }
        if (c.runs?.[arm]?.url) {
            const a = el('a', '打开这组 IM 会话 ↗');
            a.href = c.runs[arm].url;
            a.target = '_blank';
            a.rel = 'noopener';
            detail.append(a);
        }
    }
    function nodeButton(n) {
        const p = c.primitives[n.type], button = el('button', undefined, 'coord-node ' + n.type + ' ' + status(n) + (n.id === selected ? ' selected' : ''));
        button.dataset.node = n.id;
        button.setAttribute('aria-label', n.id + ' ' + n.title);
        button.setAttribute('aria-pressed', String(n.id === selected));
        button.append(el('small', n.id + ' · ' + p.title), el('strong', n.title), el('span', p.from + ' → ' + p.to + (n.worker ? ' · ' + (graph.worker_titles?.[n.worker] ?? n.worker) : ''), 'coord-node-flow'));
        if (arm)
            button.append(el('span', labels[status(n)] ?? status(n), 'coord-node-status'));
        button.onclick = () => { selected = n.id; draw(false); };
        return button;
    }
    function draw(resetScroll = true) {
        const x = viewport.scrollLeft, y = viewport.scrollTop;
        viewport.replaceChildren();
        const shown = nodes.filter(n => !task || n.task === task);
        count.textContent = shown.length + ' / ' + nodes.length + ' 个节点';
        modeButton.textContent = mode === 'graph' ? '切换按序列表' : '切换 DAG';
        zoomInput.hidden = mode !== 'graph';
        zoomLabel.hidden = mode !== 'graph';
        if (!shown.some(n => n.id === selected))
            selected = shown[0].id;
        if (mode === 'list') {
            const list = el('div', undefined, 'coord-list');
            shown.forEach(n => { list.append(nodeButton(n)); const deps = [...n.after, ...n.order_after ?? []]; if (deps.length)
                list.append(el('p', '前置 ' + deps.join('、'), 'coord-list-refs')); });
            viewport.append(list);
        }
        else {
            const lanes = Object.keys(graph.tasks).filter(key => shown.some(n => n.task === key));
            const positions = new Map(), occupied = new Set();
            let pending = [...nodes];
            while (pending.length) {
                let moved = false;
                pending = pending.filter(n => { const deps = [...n.after, ...n.order_after ?? []]; if (deps.some(id => !positions.has(id)))
                    return true; let level = Math.max(-1, ...deps.map(id => positions.get(id).level)) + 1; while (occupied.has(n.task + ':' + level))
                    level++; occupied.add(n.task + ':' + level); positions.set(n.id, { level, x: lanes.indexOf(n.task) * 270 + 16, y: level * 146 + 48 }); moved = true; return false; });
                if (!moved) {
                    viewport.append(el('p', '图中存在无效依赖'));
                    return;
                }
            }
            // Rebase visible rows after task filtering while preserving each visible edge.
            if (task) {
                const levels = [...new Set(shown.map(n => positions.get(n.id).level))].sort((a, b) => a - b);
                shown.forEach(n => positions.get(n.id).y = levels.indexOf(positions.get(n.id).level) * 146 + 48);
            }
            const height = Math.max(...shown.map(n => positions.get(n.id).y)) + 145, width = lanes.length * 270 + 20;
            const frame = el('div', undefined, 'coord-frame');
            frame.style.width = width * zoom + 'px';
            frame.style.height = height * zoom + 'px';
            const canvas = el('div', undefined, 'coord-canvas');
            canvas.style.width = width + 'px';
            canvas.style.height = height + 'px';
            canvas.style.transform = `scale(${zoom})`;
            frame.append(canvas);
            viewport.append(frame);
            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('width', width);
            svg.setAttribute('height', height);
            svg.classList.add('coord-edges');
            svg.innerHTML = '<defs><marker id="coord-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" style="fill:#9bb0bd;stroke:none"/></marker></defs>';
            canvas.append(svg);
            lanes.forEach((key, i) => { const title = el('div', graph.tasks[key], 'coord-lane'); title.style.left = i * 270 + 16 + 'px'; canvas.append(title); });
            for (const n of shown) {
                const target = positions.get(n.id);
                for (const [style, deps] of [['hard', n.after], ['order', n.order_after ?? []]])
                    for (const id of deps) {
                        const source = byId.get(id);
                        if (!shown.includes(source))
                            continue;
                        const p = positions.get(id), line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                        const middle = (p.y + 122 + target.y) / 2;
                        line.setAttribute('d', `M${p.x + 118},${p.y + 122} C${p.x + 118},${middle} ${target.x + 118},${middle} ${target.x + 118},${target.y}`);
                        line.setAttribute('marker-end', 'url(#coord-arrow)');
                        line.setAttribute('class', style + (n.id === selected || id === selected ? ' focused' : ''));
                        svg.append(line);
                    }
                const b = nodeButton(n);
                b.style.left = target.x + 'px';
                b.style.top = target.y + 'px';
                canvas.append(b);
            }
        }
        if (!resetScroll) {
            viewport.scrollLeft = x;
            viewport.scrollTop = y;
        }
        showDetail();
    }
    selector.onchange = () => { task = selector.value; draw(); };
    modeButton.onclick = () => { mode = mode === 'graph' ? 'list' : 'graph'; draw(); };
    zoomInput.oninput = () => { zoom = Number(zoomInput.value) / 100; zoomLabel.textContent = zoomInput.value + '%'; draw(false); };
    draw();
}
