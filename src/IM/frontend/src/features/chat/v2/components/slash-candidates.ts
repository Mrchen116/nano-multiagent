import type { AgentAllowlistOption } from "../../../settings/agents/im-agent-config-api";

/**
 * feat-430: slash picker candidate model + pure assembly helpers.
 *
 * A candidate is either a built-in command (`/stop`) or an agent skill. The
 * picker补 `/name ` for commands and `/skill:name ` for skills (决策 6); group
 * skills are deduped by SKILL.md `location` and carry their source agents (Q7).
 */

export interface SlashCommandCandidate {
  kind: "command";
  name: string;
  description: string;
}

export interface SlashSkillCandidate {
  kind: "skill";
  name: string;
  description: string;
  /** SKILL.md path; null when the Gateway payload omitted it (degraded). */
  location: string | null;
  /** Display names of the agents that expose this skill (group source labels). */
  fromAgents: string[];
}

export type SlashCandidate = SlashCommandCandidate | SlashSkillCandidate;

/**
 * One conversation agent's enabled skills, ready for union/dedup.
 */
export interface AgentEnabledSkills {
  agentDisplayName: string;
  skills: AgentAllowlistOption[];
}

/**
 * Resolve an agent's *enabled* skills = config whitelist ∩ capabilities (决策 2).
 *
 * The config whitelist (`agent.skills`) is the real enablement判据; capabilities
 * supplies description/location. An empty whitelist means "all discovered skills"
 * — runtime parity (`session.skills` unset → all available). capabilities skill
 * options have no `default_on`, so it is never used as an enablement判据.
 */
export function resolveEnabledSkills(
  whitelist: string[],
  capabilitySkills: AgentAllowlistOption[]
): AgentAllowlistOption[] {
  if (whitelist.length === 0) return capabilitySkills;
  const allow = new Set(whitelist);
  return capabilitySkills.filter((s) => allow.has(s.name));
}

/**
 * Build the deduped skill candidate list across one or more agents (决策 3 / Q7).
 *
 * Same `location` → merged into one row whose `fromAgents` lists every source;
 * different `location` (even same name) → separate rows. When `location` is null
 * (degraded payload), fall back to the name as the dedup key so the picker still
 * renders without crashing — same-named skills then collapse (documented降级).
 * Result is sorted by name for a stable picker order.
 */
export function buildSlashSkills(perAgent: AgentEnabledSkills[]): SlashSkillCandidate[] {
  const byKey = new Map<string, SlashSkillCandidate>();
  for (const { agentDisplayName, skills } of perAgent) {
    for (const skill of skills) {
      const location = skill.location ?? null;
      const key = location ?? `name:${skill.name}`;
      const existing = byKey.get(key);
      if (existing) {
        if (!existing.fromAgents.includes(agentDisplayName)) {
          existing.fromAgents.push(agentDisplayName);
        }
        // Prefer a non-empty description if the first source lacked one.
        if (!existing.description && skill.description) {
          existing.description = skill.description;
        }
        continue;
      }
      byKey.set(key, {
        kind: "skill",
        name: skill.name,
        description: skill.description ?? "",
        location,
        fromAgents: [agentDisplayName],
      });
    }
  }
  return [...byKey.values()].sort((a, b) => a.name.localeCompare(b.name));
}

/** Parsed slash trigger: bare `/<prefix>` (commands+skills) vs `/skill:<prefix>`. */
export interface SlashMatch {
  /** True when already in the `/skill:` namespace → filter skills only. */
  skillMode: boolean;
  /** The prefix after `/` or `/skill:`. */
  prefix: string;
}

const SLASH_TRIGGER_RE = /^\/(skill:)?([^\s/]*)$/;

/**
 * Detect a slash trigger at the START of the composer (决策 6 / 原型).
 *
 * Only fires when `/` is the first character (no preceding non-empty text), so a
 * `/` in the middle of a message does not trigger. `/skill:<prefix>` enters
 * skill-only filtering and supports editing already-inserted `/skill:doc` → `/skill:d`.
 */
export function matchSlashTrigger(text: string): SlashMatch | null {
  const m = SLASH_TRIGGER_RE.exec(text);
  if (!m) return null;
  return { skillMode: Boolean(m[1]), prefix: m[2] ?? "" };
}
