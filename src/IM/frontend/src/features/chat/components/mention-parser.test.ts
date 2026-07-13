/**
 * bugfix-358 R4: parseMentions utility — unit tests
 *
 * parseMentions(content) -> Array<Segment>
 * Segment = {kind:"text", text:string} | {kind:"mention", type:"agent"|"user", target_id:string}
 */

import { describe, expect, it } from "vitest";

// Import from the module we're about to create.
import { parseMentions } from "./mention-parser";

describe("parseMentions", () => {
  it("returns single text segment for content with no mention tags", () => {
    const result = parseMentions("hello world");
    expect(result).toEqual([{ kind: "text", text: "hello world" }]);
  });

  it("returns empty array for empty string", () => {
    const result = parseMentions("");
    expect(result).toEqual([]);
  });

  it("parses a single agent mention tag", () => {
    const content = '<mention type="agent" target_id="ArchA"/> 你怎么看？';
    const result = parseMentions(content);
    expect(result).toEqual([
      { kind: "mention", type: "agent", target_id: "ArchA" },
      { kind: "text", text: " 你怎么看？" },
    ]);
  });

  it("parses a single user mention tag", () => {
    const content = '<mention type="user" target_id="user-uuid-1"/> 你好';
    const result = parseMentions(content);
    expect(result).toEqual([
      { kind: "mention", type: "user", target_id: "user-uuid-1" },
      { kind: "text", text: " 你好" },
    ]);
  });

  it("parses multiple mention tags interspersed with text", () => {
    const content =
      'hello <mention type="agent" target_id="Arch"/> and <mention type="agent" target_id="ArchA"/> bye';
    const result = parseMentions(content);
    expect(result).toEqual([
      { kind: "text", text: "hello " },
      { kind: "mention", type: "agent", target_id: "Arch" },
      { kind: "text", text: " and " },
      { kind: "mention", type: "agent", target_id: "ArchA" },
      { kind: "text", text: " bye" },
    ]);
  });

  it("handles mention tag at the start of content", () => {
    const content = '<mention type="agent" target_id="Arch"/> 你好';
    const [first, second] = parseMentions(content);
    expect(first).toEqual({ kind: "mention", type: "agent", target_id: "Arch" });
    expect(second).toEqual({ kind: "text", text: " 你好" });
  });

  it("handles mention tag at the end of content", () => {
    const content = 'hello <mention type="agent" target_id="Arch"/>';
    const result = parseMentions(content);
    expect(result).toEqual([
      { kind: "text", text: "hello " },
      { kind: "mention", type: "agent", target_id: "Arch" },
    ]);
  });

  it("ignores old-style @display_name text — returns as plain text", () => {
    const result = parseMentions("@架构 你怎么看？");
    expect(result).toEqual([{ kind: "text", text: "@架构 你怎么看？" }]);
  });

  it("ignores malformed tags — returns as plain text", () => {
    // Missing target_id attribute
    const result = parseMentions('<mention type="agent"/> hello');
    // Should not produce a mention segment; either plain text or skipped
    const mentionSegments = result.filter((s) => s.kind === "mention");
    expect(mentionSegments).toHaveLength(0);
  });

  it("handles content that is only mention tags (no surrounding text)", () => {
    const content = '<mention type="agent" target_id="Arch"/>';
    const result = parseMentions(content);
    expect(result).toEqual([{ kind: "mention", type: "agent", target_id: "Arch" }]);
  });

  it("does not produce empty text segments", () => {
    const content = '<mention type="agent" target_id="A"/><mention type="agent" target_id="B"/>';
    const result = parseMentions(content);
    const textSegs = result.filter((s) => s.kind === "text");
    // No empty strings
    for (const seg of textSegs) {
      expect((seg as { kind: "text"; text: string }).text).not.toBe("");
    }
    expect(result.filter((s) => s.kind === "mention")).toHaveLength(2);
  });
});
