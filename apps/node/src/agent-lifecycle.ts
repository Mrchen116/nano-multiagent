import type { AgentLifecycleSnapshot, AgentLifecycleReport } from '@nano/product-contracts';

interface Proof { boot: string; processInstanceId: string | null; stopped: boolean }
interface Host {
  readonly available: boolean;
  readonly processInstanceId?: string;
  enable(): void;
  disable(): Promise<{confirmed: boolean; processInstanceId?: string; errorDetail?: string}>;
}
interface Options {
  nodeId: string;
  boot: string;
  snapshot(agentId: string): AgentLifecycleSnapshot | undefined;
  save(state: AgentLifecycleSnapshot): void;
  proof(agentId: string): Proof | undefined;
  saveProof(agentId: string, proof: Proof): void;
  host(agentId: string): Host;
  start(agentId: string): Promise<void>;
  cancel(agentId: string): void;
  resetHeartbeat(agentId: string): void;
  report(value: AgentLifecycleReport): Promise<void>;
}

/** Applies authoritative intent before any asynchronous runtime work. */
export class NodeAgentLifecycle {
  private readonly applying = new Map<string, {revision:number; task:Promise<void>}>();
  synchronized = false;
  constructor(private readonly options: Options) {}
  allowed(agentId: string): boolean { return this.synchronized && this.options.snapshot(agentId)?.desired === 'enabled'; }
  async synchronize(states: AgentLifecycleSnapshot[]): Promise<void> {
    // Persist the complete barrier before any host starts or restores input.
    const previous = new Map(states.map(state => [state.agent_id, this.options.snapshot(state.agent_id)]));
    for (const state of states) this.options.save(state);
    this.synchronized = true;
    await Promise.all(states.map(state => this.applyKnown(state, previous.get(state.agent_id))));
  }
  apply(state: AgentLifecycleSnapshot): Promise<void> { return this.applyKnown(state, this.options.snapshot(state.agent_id)); }
  private applyKnown(state: AgentLifecycleSnapshot, prior: AgentLifecycleSnapshot | undefined): Promise<void> {
    if (prior && prior.revision > state.revision) return Promise.resolve();
    this.options.save(state);
    const active = this.applying.get(state.agent_id);
    if (active?.revision === state.revision) return active.task;
    const host = this.options.host(state.agent_id);
    let task: Promise<void>;
    if (state.desired === 'disabled') {
      this.options.cancel(state.agent_id);
      this.options.resetHeartbeat(state.agent_id);
      // disable closes automatic restart synchronously, before reporting or drains.
      const stopping = host.disable();
      task = this.stop(state, stopping);
    } else {
      if (state.disabled_through_revision > 0 && (prior?.revision ?? 1) <= state.disabled_through_revision) {
        this.options.cancel(state.agent_id);
        this.options.resetHeartbeat(state.agent_id);
      }
      host.enable();
      task = this.options.start(state.agent_id);
    }
    this.applying.set(state.agent_id, {revision:state.revision, task});
    void task.finally(() => { if (this.applying.get(state.agent_id)?.task === task) this.applying.delete(state.agent_id); }).catch(() => {});
    return task;
  }
  /** Record ownership before product initialization can restore native agents. */
  async launching(agentId: string, processInstanceId: string): Promise<void> {
    const state = this.options.snapshot(agentId)!;
    if (!this.allowed(agentId)) throw new Error('agent_disabled');
    this.options.saveProof(agentId, {boot:this.options.boot, processInstanceId, stopped:false});
    await this.publish(state, 'enabling', processInstanceId);
  }
  async ready(agentId: string, processInstanceId: string): Promise<void> {
    const state = this.options.snapshot(agentId)!;
    if (!this.allowed(agentId)) throw new Error('agent_disabled');
    await this.publish(state, 'enabled', processInstanceId);
  }
  /** Preserve completed graceful cleanup so an offline disable can be confirmed on restart. */
  recordStopped(agentId: string): void {
    // A node shutdown is not new evidence for an earlier unconfirmed disable.
    if (this.options.snapshot(agentId)?.desired === 'disabled') return;
    const proof=this.options.proof(agentId);
    if(proof)this.options.saveProof(agentId,{...proof,stopped:true});
  }
  private async stop(state: AgentLifecycleSnapshot, stopping: Promise<{confirmed:boolean;processInstanceId?:string;errorDetail?:string}>): Promise<void> {
    const proof = this.options.proof(state.agent_id);
    const result = await stopping;
    const processId = result.processInstanceId ?? proof?.processInstanceId ?? state.process_instance_id;
    const confirmed = result.processInstanceId ? result.confirmed : proof ? proof.stopped || proof.boot !== this.options.boot : !state.process_instance_id;
    if (confirmed) this.options.saveProof(state.agent_id, {boot:this.options.boot, processInstanceId:processId, stopped:true});
    await this.publish(state, confirmed ? 'disabled' : 'stop_unconfirmed', processId,
      confirmed ? undefined : 'managed_cleanup_unconfirmed', confirmed ? undefined : result.errorDetail ?? 'Previous runtime cleanup is still unconfirmed on this machine boot.');
  }
  private async publish(state: AgentLifecycleSnapshot, observed: AgentLifecycleSnapshot['observed'], processId: string | null, errorCode?: string, errorDetail?: string): Promise<void> {
    if (this.options.snapshot(state.agent_id)?.revision !== state.revision) return;
    const next = {...state, observed, process_instance_id:processId, error_code:errorCode ?? null, error_detail:errorDetail ?? null,
      applied_revision: observed === 'enabled' || observed === 'disabled' ? state.revision : state.applied_revision};
    this.options.save(next);
    await this.options.report({node_id:this.options.nodeId, agent_id:state.agent_id, revision:state.revision,
      observed, process_instance_id:processId, error_code:errorCode ?? null,error_detail:errorDetail ?? null});
  }
}
