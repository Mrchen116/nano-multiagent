// @vitest-environment node

import { describe, expect, it } from "vitest";

import config from "../vite.config";

describe("Vite development proxy", () => {
  it("forwards IM WebSocket connections as well as HTTP requests", () => {
    expect(config).toMatchObject({
      server: {
        proxy: {
          "/im": {
            ws: true
          }
        }
      }
    });
  });
});
