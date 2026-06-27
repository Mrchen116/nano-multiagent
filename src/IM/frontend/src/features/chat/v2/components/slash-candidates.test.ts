import { describe, expect, it } from "vitest";

import type { AgentAllowlistOption } from "../../../settings/agents/im-agent-config-api";
import {
  buildSlashSkills,
  matchSlashTrigger,
  resolveEnabledSkills,
} from "./slash-candidates";

const skill = (name: string, location: string | null, description = ""): AgentAllowlistOption => ({
  name,
  description,
  location,
});

describe("resolveEnabledSkills (config whitelist ∩ capabilities)", () => {
  const caps = [skill("pr-review", "/a"), skill("doc", "/b"), skill("log", "/c")];

  it("intersects capabilities with a non-empty whitelist by name", () => {
    const out = resolveEnabledSkills(["pr-review", "doc"], caps);
    expect(out.map((s) => s.name)).toEqual(["pr-review", "doc"]);
  });

  it("excludes capabilities skills not in the whitelist", () => {
    const out = resolveEnabledSkills(["doc"], caps);
    expect(out.map((s) => s.name)).toEqual(["doc"]);
    expect(out.some((s) => s.name === "pr-review")).toBe(false);
  });

  it("empty whitelist means all discovered skills (runtime parity)", () => {
    const out = resolveEnabledSkills([], caps);
    expect(out.map((s) => s.name)).toEqual(["pr-review", "doc", "log"]);
  });
});

describe("buildSlashSkills (group union + location dedup)", () => {
  it("merges same-location skills from two agents into one row with both sources", () => {
    const out = buildSlashSkills([
      { agentDisplayName: "code-reviewer", skills: [skill("pr-review", "/shared/pr/SKILL.md")] },
      { agentDisplayName: "test-writer", skills: [skill("pr-review", "/shared/pr/SKILL.md")] },
    ]);
    expect(out).toHaveLength(1);
    expect(out[0]!.name).toBe("pr-review");
    expect(out[0]!.fromAgents).toEqual(["code-reviewer", "test-writer"]);
  });

  it("keeps same-named skills at different locations as separate rows", () => {
    const out = buildSlashSkills([
      { agentDisplayName: "code-reviewer", skills: [skill("doc", "/cr/doc/SKILL.md")] },
      { agentDisplayName: "test-writer", skills: [skill("doc", "/tw/doc/SKILL.md")] },
    ]);
    expect(out).toHaveLength(2);
    expect(out.every((s) => s.name === "doc")).toBe(true);
    expect(out[0]!.fromAgents).toEqual(["code-reviewer"]);
    expect(out[1]!.fromAgents).toEqual(["test-writer"]);
  });

  it("degrades to name dedup when location is null", () => {
    const out = buildSlashSkills([
      { agentDisplayName: "a", skills: [skill("doc", null)] },
      { agentDisplayName: "b", skills: [skill("doc", null)] },
    ]);
    expect(out).toHaveLength(1);
    expect(out[0]!.fromAgents).toEqual(["a", "b"]);
  });

  it("sorts skills by name", () => {
    const out = buildSlashSkills([
      { agentDisplayName: "a", skills: [skill("zeta", "/z"), skill("alpha", "/a")] },
    ]);
    expect(out.map((s) => s.name)).toEqual(["alpha", "zeta"]);
  });
});

describe("matchSlashTrigger", () => {
  it("matches a bare slash at the start", () => {
    expect(matchSlashTrigger("/")).toEqual({ skillMode: false, prefix: "" });
    expect(matchSlashTrigger("/pr")).toEqual({ skillMode: false, prefix: "pr" });
  });

  it("matches the /skill: namespace and supports prefix editing", () => {
    expect(matchSlashTrigger("/skill:d")).toEqual({ skillMode: true, prefix: "d" });
    expect(matchSlashTrigger("/skill:")).toEqual({ skillMode: true, prefix: "" });
  });

  it("does not trigger when text precedes the slash", () => {
    expect(matchSlashTrigger("hello /world")).toBeNull();
  });

  it("does not trigger once a space follows the prefix", () => {
    expect(matchSlashTrigger("/skill:doc ")).toBeNull();
    expect(matchSlashTrigger("/stop ")).toBeNull();
  });
});
