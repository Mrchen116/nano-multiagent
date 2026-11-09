import type { AgentLifecycleSnapshot, AgentLifecycleReport } from '@nano/product-contracts';

interface Proof { boot: string; processInstanceId: string | null; stopped: boolean; cleanupRevision?: number }
interface Host {
  readonly available: boolean;
  readonly processInstanceId?: string;
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
    const reconciled = states.flatMap(state => {
      const prior = this.options.snapshot(state.agent_id);
      if (prior && prior.revision > state.revision) return [];
      return [{state:this.reconcileStop(state, prior), prior}];
    });
    for (const {state} of reconciled) this.options.save(state);
    this.synchronized = true;
    await Promise.all(reconciled.map(({state,prior}) => this.applyKnown(state, prior)));
  }
  apply(state: AgentLifecycleSnapshot): Promise<void> {
    const prior = this.options.snapshot(state.agent_id);
    return this.applyKnown(this.reconcileStop(state, prior), prior);
  }
  private reconcileStop(state: AgentLifecycleSnapshot, prior: AgentLifecycleSnapshot | undefined): AgentLifecycleSnapshot {
    if (state.desired !== 'disabled') return state;
    const proof = this.options.proof(state.agent_id);
    const confirmed = proof?.stopped && [state, prior].find(candidate =>
      candidate?.desired === 'disabled' && candidate.revision === state.revision &&
      candidate.observed === 'disabled' && candidate.applied_revision === state.revision &&
      candidate.process_instance_id === proof.processInstanceId &&
      (state.process_instance_id === null || state.process_instance_id === candidate.process_instance_id));
    if (confirmed) {
      return {...state, observed:'disabled', applied_revision:state.revision, process_instance_id:confirmed.process_instance_id,
        confirmed_at:confirmed.confirmed_at, error_code:null, error_detail:null};
    }
    // A center acknowledgment alone cannot open the local deletion gate.
    return state.observed === 'disabled' ? {...state, observed:'stopping', confirmed_at:null} : state;
  }
  private applyKnown(state: AgentLifecycleSnapshot, prior: AgentLifecycleSnapshot | undefined): Promise<void> {
    if (prior && prior.revision > state.revision) return Promise.resolve();
    const active = this.applying.get(state.agent_id);
    if (active?.revision === state.revision) return active.task;
    this.options.save(state);
    let task: Promise<void>;
    if (state.desired === 'disabled') {
      this.options.cancel(state.agent_id);
      this.options.resetHeartbeat(state.agent_id);
      // Product admission is already closed; native cleanup is scoped to this Agent.
      task = state.observed === 'disabled'
        ? this.publish(state, 'disabled', state.process_instance_id)
        : this.stop(state, this.options.host(state.agent_id).disable());
    } else {
      if (state.disabled_through_revision > 0 && (prior?.revision ?? 1) <= state.disabled_through_revision) {
        this.options.cancel(state.agent_id);
        this.options.resetHeartbeat(state.agent_id);
      }
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
  /** Persist cleanup from the original process before pulling final Work pages. */
  recordCleanup(agentId: string, revision: number, processInstanceId?: string): void {
    const state = this.options.snapshot(agentId), proof = this.options.proof(agentId);
    if (state?.desired==='disabled' && state.revision===revision && proof?.processInstanceId===processInstanceId && proof)
      this.options.saveProof(agentId,{...proof,cleanupRevision:revision});
  }

  /** Retry an unconfirmed stop after its replacement runtime has finished starting. */
  async recoverStop(agentId: string): Promise<void> {
    await this.applying.get(agentId)?.task.catch(() => {});
    const state = this.options.snapshot(agentId);
    if (state?.desired==='disabled' && state.observed!=='disabled') await this.apply(state);
  }

  private async stop(state: AgentLifecycleSnapshot, stopping: Promise<{confirmed:boolean;processInstanceId?:string;errorDetail?:string}>): Promise<void> {
    const proof = this.options.proof(state.agent_id);
    const result = await stopping.catch(error => ({confirmed:false, processInstanceId:this.options.host(state.agent_id).processInstanceId, errorDetail:String(error)}));
    if (this.options.snapshot(state.agent_id)?.revision !== state.revision) return;
    const processId = result.processInstanceId ?? proof?.processInstanceId ?? state.process_instance_id;
    const priorSettled = proof ? proof.stopped || proof.cleanupRevision === state.revision || proof.boot !== this.options.boot || proof.processInstanceId === result.processInstanceId : !state.process_instance_id || state.process_instance_id === result.processInstanceId;
    const confirmed = result.processInstanceId ? result.confirmed && priorSettled : proof ? proof.stopped || proof.boot !== this.options.boot : !state.process_instance_id;
    // Disabled intent still names the last execution host at the center. A new
    // shared management host cannot replace that identity via an enabling report.
    const executionId = state.process_instance_id ?? processId;
    if (confirmed) this.options.saveProof(state.agent_id, {boot:this.options.boot, processInstanceId:executionId, stopped:true});
    await this.publish(state, confirmed ? 'disabled' : 'stop_unconfirmed', executionId,
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
