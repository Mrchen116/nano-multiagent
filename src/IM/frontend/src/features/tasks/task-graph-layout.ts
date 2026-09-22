import type { TaskDependency, TaskGraph, TaskNode } from "./task-graphs-api";

const CARD_WIDTH = 204;
const COLUMN = 272;
const ROW = 174;

/** Lay out one scope; direct edges retain distinct ports and skip edges travel above cards. */
export function layoutTaskScope(graph: TaskGraph, scope: TaskNode) {
  const nodes = graph.nodes.filter(node => node.container_id === scope.id)
    .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
  const ids = new Set(nodes.map(node => node.id));
  const edges: TaskDependency[] = scope.mode === "dag"
    ? graph.dependencies.filter(edge => ids.has(edge.from) && ids.has(edge.to))
    : nodes.filter(node => node.derived_from_id).map(node => ({ from: node.derived_from_id!, to: node.id }));
  const depth = new Map(nodes.map(node => [node.id, 0]));
  // The service guarantees acyclicity; topological traversal also handles the 500-node bound cheaply.
  const incoming = new Map(nodes.map(node => [node.id, 0]));
  const outgoing = new Map<string, TaskDependency[]>();
  edges.forEach(edge => {
    incoming.set(edge.to, incoming.get(edge.to)! + 1);
    outgoing.set(edge.from, [...(outgoing.get(edge.from) ?? []), edge]);
  });
  const queue = nodes.filter(node => incoming.get(node.id) === 0).map(node => node.id);
  for (let index = 0; index < queue.length; index++) {
    const id = queue[index];
    for (const edge of outgoing.get(id) ?? []) {
      depth.set(edge.to, Math.max(depth.get(edge.to)!, depth.get(id)! + 1));
      incoming.set(edge.to, incoming.get(edge.to)! - 1);
      if (incoming.get(edge.to) === 0) queue.push(edge.to);
    }
  }
  const columns = new Map<number, TaskNode[]>();
  nodes.forEach(node => columns.set(depth.get(node.id)!, [...(columns.get(depth.get(node.id)!) ?? []), node]));
  const longEdges = edges.filter(edge => depth.get(edge.to)! - depth.get(edge.from)! > 1);
  const extraTop = longEdges.length ? longEdges.length * 18 + 24 : 0;
  const maxRows = Math.max(1, ...[...columns.values()].map(column => column.length));
  const positions = new Map<string, { x: number; y: number }>();
  columns.forEach((column, level) => column.forEach((node, row) => positions.set(node.id, {
    x: 16 + level * COLUMN,
    y: 32 + extraTop + row * ROW + (maxRows - column.length) * ROW / 2
  })));
  function port(edge: TaskDependency, end: "from" | "to") {
    const siblings = edges.filter(candidate => candidate[end] === edge[end]);
    return siblings.length === 1 ? 67 : 28 + 78 * siblings.indexOf(edge) / (siblings.length - 1);
  }
  const routes = edges.map(edge => {
    const from = positions.get(edge.from)!;
    const to = positions.get(edge.to)!;
    const sy = from.y + port(edge, "from");
    const ty = to.y + port(edge, "to");
    const lane = longEdges.indexOf(edge);
    return {
      ...edge,
      path: lane < 0
        ? `M${from.x + CARD_WIDTH} ${sy} C${from.x + 240} ${sy},${to.x - 36} ${ty},${to.x - 5} ${ty}`
        : `M${from.x + CARD_WIDTH} ${sy} H${from.x + 220} V${18 + lane * 18} H${to.x - 20} V${ty} H${to.x - 5}`,
      labelX: (from.x + CARD_WIDTH + to.x) / 2,
      labelY: lane < 0 ? (sy + ty) / 2 - 14 : 10 + lane * 18
    };
  });
  return {
    nodes, routes, positions,
    width: Math.max(500, (Math.max(0, ...depth.values()) + 1) * COLUMN - 36),
    height: Math.max(300, maxRows * ROW + 62 + extraTop)
  };
}
