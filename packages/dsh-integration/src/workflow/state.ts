import {
  defineDomain,
  domainTable,
  type DomainSpec,
  type DomainTableSpec,
} from "@deepseek-ai/dsh-storage-domain";
import type { WorkflowMeta, WorkflowResult } from "@deepseek-ai/dsh-workflow";
import type { ModelRoute } from "../model-policy.js";
import type { WorkflowCall } from "./control.js";
import { z } from "zod";
export interface WorkflowRecord {
  id: string;
  parentSessionId: string;
  inputIds: string[];
  budgetId: string;
  guideline: string;
  script: string;
  args: unknown;
  meta: WorkflowMeta;
  route: ModelRoute;
  state:
    | "running"
    | "paused"
    | "completed"
    | "cancelled"
    | "error"
    | "interrupted";
  startedAt: number;
  endedAt?: number;
  revision: number;
  resumedFrom?: string;
  calls: WorkflowCall[];
  logs: { at: number; text: string; phase?: string }[];
  result?: WorkflowResult;
  delivered?: boolean;
}
export interface BudgetRecord {
  id: string;
  parentSessionId: string;
  target: number | null;
  sources: Record<string, { turns?: number[]; output: number }>;
}
export interface WorkflowDomain extends DomainSpec {
  tables: {
    runs: DomainTableSpec<string, WorkflowRecord>;
    budgets: DomainTableSpec<string, BudgetRecord>;
    commands: DomainTableSpec<
      string,
      { sessionId: string; argument: string; text?: string }
    >;
  };
}
export const workflowDomain: WorkflowDomain = defineDomain({
  name: "nano_workflow",
  version: 1,
  layout: "per-record",
  tables: {
    runs: domainTable(z.custom<WorkflowRecord>()),
    budgets: domainTable(z.custom<BudgetRecord>()),
    commands: domainTable(
      z.object({
        sessionId: z.string(),
        argument: z.string(),
        text: z.string().optional(),
      }),
    ),
  },
});
