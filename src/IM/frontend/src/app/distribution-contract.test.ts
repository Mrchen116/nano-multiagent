import { describe, expect, it } from "vitest";
import frontendGitignore from "../../.gitignore?raw";

describe("frontend distribution contract", () => {
  it("keeps the built dist tree available for the IM-hosted entry", () => {
    expect(frontendGitignore).not.toContain("dist/");
  });
});
