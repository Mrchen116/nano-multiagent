export interface AgentWorkspaceWitness {
  path: string;
  witness: string;
}

export type AgentDeletionState = 'waiting_node' | 'deleting' | 'failed' | 'deleted';

export interface AgentDeletionIntent {
  agent_id: string;
  operation_id: string;
  revision: number;
  workspace?: AgentWorkspaceWitness;
}

export interface AgentDeletionView {
  agent_id: string;
  eligible: boolean;
  reason?: string;
  revision: number;
  profile_version: number;
  workspace?: AgentWorkspaceWitness;
  operation?: {
    operation_id: string;
    state: AgentDeletionState;
    error_detail?: string;
    delete_workspace: boolean;
  };
}
