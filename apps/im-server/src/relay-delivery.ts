import { all, now, type ImContext, type Row } from './context.js';

/** Drain persisted relays through a bounded node window; socket writes are never acceptance. */
export class RelayDelivery {
  private readonly flights = new Map<string,Map<string,number>>();
  private readonly retries = new Map<string,{at:number;delay:number}>();
  private readonly lastAgents = new Map<string,string>();
  private timer?: ReturnType<typeof setInterval>;
  constructor(private readonly ctx:ImContext) {}
  start():void {
    if(this.timer)return;
    this.timer=setInterval(()=>this.drain(),250);this.timer.unref();
  }
  /** Release the current connection's window; durable rows remain recoverable. */
  disconnect(node:string):void {this.flights.delete(node);}
  /** Release an accepted relay immediately without replaying its remaining work. */
  receipt(node:string,id:string):void {this.flights.get(node)?.delete(id);this.retries.delete(id);this.drain(node);}
  stop():void {clearInterval(this.timer);this.flights.clear();this.retries.clear();}
  /** Nudge one node, or all live nodes, after a commit or registration. */
  drain(node?:string):boolean {
    let sent=false;
    for (const id of node?[node]:this.ctx.gateway.nodes.keys()) {
      if (!this.ctx.gateway.isOnline(id) || this.ctx.updates?.acceptingQueue(id)) continue;
      const flights=this.flights.get(id)??new Map<string,number>();this.flights.set(id,flights);
      const time=Date.now();
      for (const [key,at] of flights) if (time-at>=10000) {
        flights.delete(key);const delay=Math.min((this.retries.get(key)?.delay??500)*2,30000);this.retries.set(key,{at:time+delay,delay});
      }
      if (flights.size>=32) continue;
      // Pages keep reconnect recovery independent of total journal/message volume.
      const rows=all(this.ctx.db,"SELECT * FROM relay_tasks WHERE target_node_id=? AND status IN ('queued','sent','accepted') AND receipt_status IS NULL ORDER BY updated_at,created_at LIMIT 256",id);
      const candidates=rows.filter(row=>!flights.has(row.relay_task_id) && (this.retries.get(row.relay_task_id)?.at??0)<=time);
      while(candidates.length && flights.size<32) {
        let index=candidates.findIndex(row=>JSON.parse(row.payload_json).agent_id!==this.lastAgents.get(id));if(index<0)index=0;
        const task=candidates.splice(index,1)[0]!;
        if (!this.ctx.messaging.relayEligible(task)) {
          this.ctx.db.prepare("UPDATE relay_tasks SET status='cancelled',updated_at=? WHERE relay_task_id=?").run(now(),task.relay_task_id);this.retries.delete(task.relay_task_id);continue;
        }
        const payload=JSON.parse(task.payload_json) as Row;
        if(!this.ctx.gateway.send(id,{type:'relay.message',payload}))break;
        flights.set(task.relay_task_id,time);this.lastAgents.set(id,String(payload.agent_id));
        this.ctx.db.prepare("UPDATE relay_tasks SET status='sent',updated_at=? WHERE relay_task_id=?").run(now(),task.relay_task_id);sent=true;
      }
    }
    return sent;
  }
}
