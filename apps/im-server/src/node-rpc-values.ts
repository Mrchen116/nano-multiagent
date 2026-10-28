import {parseAgentConfigurationFields} from '@nano/product-contracts';
import type { NodeCommand, NodeOutput } from './node-rpc-contracts.js';

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
const text = (value: unknown): value is string => typeof value === 'string';
const number = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const boolean = (value: unknown): value is boolean => typeof value === 'boolean';
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(text);
const nullableText = (value: unknown) => value === null || text(value);
function invalid(): never {
  throw Object.assign(new Error('invalid node response'), {statusCode: 502});
}
function field(value: Record<string, unknown>, key: string, valid: (value: unknown) => boolean): void {
  if (value[key] !== undefined && !valid(value[key])) invalid();
}
function record(value: unknown): Record<string, unknown> {
  if (!isRecord(value)) invalid();
  return value;
}

function capabilities(value: unknown): void {
  const p = record(value);
  for (const key of ['models','skills','tools','commands','features']) field(p, key, Array.isArray);
  field(p, 'fixed_tools', strings);
  for (const key of ['platform_default_model','default_workspace_template']) field(p, key, nullableText);
}
function usage(value: unknown): void {
  const p = record(value);
  field(p, 'skills', Array.isArray);
  field(p, 'heatmap_data', Array.isArray);
  field(p, 'health', isRecord);
}

/** Decode after connection/type correlation; business identity checks remain with the owner.
 *
 * Args:
 *   command: Original outbound command, never an untrusted response type.
 *   value: Raw payload from that command's expected response frame.
 * Returns:
 *   The original payload with its consumed fields checked; no projection changes bytes.
 * Raises:
 *   Error: 502 when the peer supplied a malformed consumed field.
 */
export function decodeNodeResult<K extends NodeCommand>(command: K, value: unknown): NodeOutput<K> {
  try { return decode(command, value); }
  catch { invalid(); }
}
function decode<K extends NodeCommand>(command: K, value: unknown): NodeOutput<K> {
  const p = record(value);
  switch (command) {
    case 'agent.create':
    case 'agent.config.apply':
    case 'agent.config.operation.status':
      for (const key of ['operation_id','candidate_fingerprint','status','error_code','message']) field(p, key, text);
      field(p, 'blocks', Array.isArray);
      if (p.agent != null) parseAgentConfigurationFields(p.agent);
      break;
    case 'agent.config.get':
      parseAgentConfigurationFields(p);
      if (p.agent != null) parseAgentConfigurationFields(p.agent);
      break;
    case 'agent.capabilities.resolve':
    case 'node.capabilities.resolve':
      capabilities(p);
      if (p.capabilities !== undefined) capabilities(p.capabilities);
      break;
    case 'agent.prompt.preview.request':
    case 'node.prompt.preview.request':
      if (p.preview !== undefined) {
        const preview = record(p.preview);
        field(preview, 'prompt', text); field(preview, 'section_count', number);
      }
      if (p.error !== undefined) {
        const error = record(p.error);
        if (!text(error.code)) invalid();
        field(error, 'detail', text);
      }
      field(p, 'error_code', text); field(p, 'message', text);
      break;
    case 'node.plugins.request':
      field(p, 'plugins', isRecord); field(p, 'error', text);
      break;
    case 'node.skills.usage.request':
      if (p.usage !== undefined) usage(p.usage);
      field(p, 'error', text);
      break;
    case 'agent.capability-usage.request':
      if (p.usage !== undefined) {
        const u = record(p.usage);
        if (!text(u.checked_at) || !Number.isInteger(u.active_schedules) || !Array.isArray(u.busy)
          || !u.busy.every(item => isRecord(item) && text(item.kind) && text(item.name))) invalid();
      }
      break;
    case 'node.heartbeat.md.request': field(p, 'content', text); break;
    case 'node.cron.jobs.request': field(p, 'jobs', Array.isArray); field(p, 'error', text); break;
    case 'node.cron.delete.request': field(p, 'deleted', boolean); break;
    case 'node.distill.prompt.request':
      for (const key of ['prompt','message','error_code']) field(p, key, text);
      break;
    case 'session.fork.request':
      field(p, 'id_map', value => isRecord(value) && Object.values(value).every(text));
      field(p, 'ok', boolean); field(p, 'error', text);
      break;
    case 'agent.work.permission': field(p, 'ok', boolean); field(p, 'error', text); break;
    case 'task.execution.state': field(p, 'state', text); break;
    case 'task.wait.validate':
      field(p, 'valid', boolean);
      for (const key of ['owner_agent_id','session_id','next_check_at','checked_at','reason_code','error']) field(p, key, text);
      break;
    case 'node.approval.resolve':
    case 'node.setup.request':
      // Provider-owned content is projected by its HTTP adapter, not interpreted here.
      break;
    default: {
      const exhaustive: never = command;
      throw new Error(`Unsupported node command: ${exhaustive}`);
    }
  }
  return p as NodeOutput<K>;
}
