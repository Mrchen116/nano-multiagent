import { Graph, layout, type Point } from "@dagrejs/dagre";
import type { TaskDependency, TaskGraph, TaskNode } from "./task-graphs-api";

const CARD_WIDTH = 204;
const CARD_HEIGHT = 136;

/** Round only the bends chosen by the layout, keeping each edge in its own corridor. */
function roundedPath(points: Point[]) {
  let path = `M${points[0].x} ${points[0].y}`;
  for (let index = 1; index < points.length - 1; index++) {
    const previous = points[index - 1], current = points[index], next = points[index + 1];
    const before = Math.hypot(current.x - previous.x, current.y - previous.y);
    const after = Math.hypot(next.x - current.x, next.y - current.y);
    if (!before || !after) continue;
    const radius = Math.min(12, before / 2, after / 2);
    const start = { x: current.x + (previous.x - current.x) * radius / before, y: current.y + (previous.y - current.y) * radius / before };
    const end = { x: current.x + (next.x - current.x) * radius / after, y: current.y + (next.y - current.y) * radius / after };
    path += ` L${start.x} ${start.y} Q${current.x} ${current.y} ${end.x} ${end.y}`;
  }
  const last = points[points.length - 1];
  return `${path} L${last.x} ${last.y}`;
}

/** Arrange one scope in dependency columns, reducing crossings without changing any recorded edge. */
export function layoutTaskScope(graph: TaskGraph, scope: TaskNode) {
  const nodes = graph.nodes.filter(node => node.container_id === scope.id)
    .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
  const ids = new Set(nodes.map(node => node.id));
  const edges: TaskDependency[] = scope.mode === "dag"
    ? graph.dependencies.filter(edge => ids.has(edge.from) && ids.has(edge.to))
    : nodes.filter(node => node.derived_from_id).map(node => ({ from: node.derived_from_id!, to: node.id }));
  const drawing = new Graph().setGraph({
    rankdir: "RL", ranker: "longest-path", nodesep: 38, edgesep: 24, ranksep: 80, marginx: 16, marginy: 48
  });
  nodes.forEach(node => drawing.setNode(node.id, { width: CARD_WIDTH, height: CARD_HEIGHT }));
  // Dagre ranks longest paths from sinks. Reverse only its layout input so every task
  // stays in its earliest prerequisite column, including disconnected tasks.
  edges.forEach(edge => drawing.setEdge(edge.to, edge.from, {}));
  if (nodes.length) layout(drawing);
  const positions = new Map(nodes.map(node => {
    const placed = drawing.node(node.id);
    return [node.id, { x: placed.x - CARD_WIDTH / 2, y: placed.y - CARD_HEIGHT / 2 }] as const;
  }));
  const routes = edges.map(edge => {
    const points: Point[] = [...drawing.edge(edge.to, edge.from).points].reverse();
    const middle = points[Math.floor(points.length / 2)];
    return { ...edge, path: roundedPath(points), labelX: middle.x, labelY: middle.y - 12 };
  });
  const columns = [...new Set([...positions.values()].map(position => position.x))].sort((a, b) => a - b)
    .map(x => ({ x, count: [...positions.values()].filter(position => position.x === x).length }));
  return {
    nodes, routes, positions, columns,
    width: Math.max(500, drawing.graph().width ?? 0),
    height: Math.max(300, drawing.graph().height ?? 0)
  };
}
