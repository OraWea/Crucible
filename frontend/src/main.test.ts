import { describe, expect, it } from "vitest";
import { displayMeta, formatDuration, normalizeUrlInput, previewCacheKey, sourceKind } from "./utils";

describe("frontend helpers", () => {
  it("normalizes URL input", () => {
    expect(normalizeUrlInput("example.com/video")).toBe("https://example.com/video");
    expect(normalizeUrlInput("https://example.com")).toBe("https://example.com");
    expect(normalizeUrlInput("not a url")).toBe("not a url");
  });

  it("formats source kind and duration", () => {
    expect(sourceKind("audio/mp3")).toBe("audio");
    expect(sourceKind("document/pdf")).toBe("document");
    expect(sourceKind("video")).toBe("video");
    expect(formatDuration(3723)).toBe("01:02:03");
  });

  it("formats metadata safely", () => {
    expect(displayMeta(undefined)).toBe("未知");
    expect(displayMeta(["a", "b"])).toBe("a, b");
    expect(displayMeta({ width: 1920 })).toBe("{\"width\":1920}");
  });

  it("builds stable preview cache keys", () => {
    expect(previewCacheKey("A.md", "# Title")).toBe(previewCacheKey("A.md", "# Title"));
    expect(previewCacheKey("A.md", "# Title")).not.toBe(previewCacheKey("B.md", "# Title"));
    expect(previewCacheKey("A.md", "# Title")).not.toBe(previewCacheKey("A.md", "# Other"));
  });
});
