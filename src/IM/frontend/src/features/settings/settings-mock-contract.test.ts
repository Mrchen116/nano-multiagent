import { describe, expect, it } from "vitest";

import {
  getInitialAccount,
  getInitialAgents,
  getInitialNodes,
  getInitialPolicies
} from "./mock-settings-api";

describe("settings mock contract", () => {
  it("contains required fields for all pages", () => {
    const agent = getInitialAgents()[0];
    const node = getInitialNodes()[0];
    const policy = getInitialPolicies();
    const account = getInitialAccount();

    expect(agent).toMatchObject({
      agent_id: expect.any(String),
      display_name: expect.any(String),
      profile_version: expect.any(String),
      group_reply_policy: expect.any(String)
    });
    expect(node).toMatchObject({
      node_id: expect.any(String),
      node_name: expect.any(String),
      desired_config_version: expect.any(String),
      relay_enabled: expect.any(Boolean),
      report_enabled: expect.any(Boolean)
    });
    expect(policy).toMatchObject({
      default_model: expect.any(String),
      max_turn_per_run: expect.any(Number),
      rate_limit_per_min: expect.any(Number)
    });
    expect(account).toMatchObject({
      user_id: expect.any(String),
      display_name: expect.any(String),
      owned_node_ids: expect.any(Array)
    });
  });
});
