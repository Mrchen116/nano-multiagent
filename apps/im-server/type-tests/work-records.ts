import type { WorkItemRecord, WorkItemView, WorkTurnRecord, WorkTurnView } from '../src/work-record-types.js';
import { WorkRecords } from '../src/work-records.js';

function workContracts(item: WorkItemRecord, turn: WorkTurnRecord, view: WorkItemView, records: WorkRecords) {
  // @ts-expect-error Stored JSON is not a public decoded payload.
  const publicItem: WorkItemView = item;
  // @ts-expect-error A raw turn row lacks status, usage, scope and public items.
  const publicTurn: WorkTurnView = turn;
  // @ts-expect-error Public items do not expose storage session/turn columns.
  view.session_id;
  // @ts-expect-error Persistence cannot reach gateway delivery or the service container.
  records.ctx.gateway;
  return [publicItem, publicTurn];
}
void workContracts;
