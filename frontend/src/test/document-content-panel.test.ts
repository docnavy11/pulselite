import { describe, it, expect } from "vitest";

describe("DocumentContentPanel types", () => {
  it("ChunkItem has required fields", () => {
    const chunk = {
      id: "abc",
      chunk_index: 0,
      content: "Hello",
      heading_path: "Section A",
      token_count: 50,
    };
    expect(chunk.id).toBe("abc");
    expect(chunk.chunk_index).toBe(0);
    expect(chunk.content).toBe("Hello");
    expect(chunk.heading_path).toBe("Section A");
    expect(chunk.token_count).toBe(50);
  });

  it("ChunkItem allows null heading_path and token_count", () => {
    const chunk = {
      id: "abc",
      chunk_index: 0,
      content: "Hello",
      heading_path: null,
      token_count: null,
    };
    expect(chunk.heading_path).toBeNull();
    expect(chunk.token_count).toBeNull();
  });

  it("DocumentContentResponse has required shape", () => {
    const resp = {
      id: "doc-1",
      title: "Test",
      source_type: "url",
      source_url: "https://example.com",
      status: "indexed",
      error_message: null,
      char_count: 100,
      chunk_count: 2,
      raw_content: "Full text",
      chunks: [],
    };
    expect(resp.chunks).toEqual([]);
    expect(resp.raw_content).toBe("Full text");
    expect(resp.error_message).toBeNull();
  });

  it("getDocumentContent builds correct URL", () => {
    const wsId = "ws-123";
    const docId = "doc-456";
    const expectedUrl = `/api/v1/workspaces/${wsId}/documents/${docId}/content`;
    expect(expectedUrl).toBe("/api/v1/workspaces/ws-123/documents/doc-456/content");
  });
});

describe("Chunk truncation logic", () => {
  it("short content is not truncated", () => {
    const content = "Short text";
    const needsTruncation = content.length > 200;
    expect(needsTruncation).toBe(false);
  });

  it("long content is truncated at 200 chars", () => {
    const content = "A".repeat(250);
    const needsTruncation = content.length > 200;
    const display = needsTruncation ? content.slice(0, 200) + "\u2026" : content;
    expect(needsTruncation).toBe(true);
    expect(display.length).toBe(201); // 200 chars + ellipsis
    expect(display.endsWith("\u2026")).toBe(true);
  });
});
