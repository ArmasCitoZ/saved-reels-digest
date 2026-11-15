import { describe, expect, it } from "vitest";
import { EMPTY_VIEW, readView, writeView } from "../src/view";

describe("the view in the URL", () => {
  it("round-trips every filter, with accents and spaces", () => {
    const view = {
      q: "revisión pide", category: "Herramientas & IA", status: "tried" as const, platform: "tiktok", sort: "recent" as const,
    };
    const hash = writeView(view);
    expect(hash).toContain("plataforma=tiktok");
    expect(hash).toContain("estado=tried");
    expect(hash).toContain("orden=recent");
    expect(readView(`#${hash}`)).toEqual(view);
  });

  it("leaves out what is not filtered", () => {
    expect(writeView(EMPTY_VIEW)).toBe("");
    expect(writeView({ ...EMPTY_VIEW, q: "  ", platform: "youtube" })).toBe("plataforma=youtube");
  });

  it("reads an empty or foreign fragment as no filter", () => {
    expect(readView("")).toEqual(EMPTY_VIEW);
    expect(readView("#claude-md-corto")).toEqual(EMPTY_VIEW); // a link to one idea's card
    expect(readView("#estado=nonsense&otra=1")).toEqual(EMPTY_VIEW);
    expect(readView("#orden=digest")).toEqual(EMPTY_VIEW); // the default is never written
    expect(readView("#orden=random")).toEqual(EMPTY_VIEW);
  });

  it("accepts the fragment with or without #", () => {
    expect(readView("q=agentes").q).toBe("agentes");
    expect(readView("#q=agentes").q).toBe("agentes");
  });
});
