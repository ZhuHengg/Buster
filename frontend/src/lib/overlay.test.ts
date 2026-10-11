import { describe, expect, it } from "vitest";

import { expectedPts, fitTransform, nearestDetections } from "./overlay";
import type { DetectionsMsg, SyncMsg } from "./types";

const det = (pts: number): DetectionsMsg => ({
  type: "detections", camera_id: "C", loop: 0, pts, frame_w: 100, frame_h: 100, tracks: [],
});

describe("fitTransform", () => {
  it("letterboxes wide video in square box", () => {
    const t = fitTransform(1600, 800, 400, 400);
    expect(t.scale).toBeCloseTo(0.25);
    expect(t.offsetX).toBeCloseTo(0);
    expect(t.offsetY).toBeCloseTo(100);
  });

  it("pillarboxes tall video in wide box", () => {
    const t = fitTransform(938, 1074, 600, 300);
    expect(t.scale).toBeCloseTo(300 / 1074);
    expect(t.offsetY).toBeCloseTo(0);
    expect(t.offsetX).toBeCloseTo((600 - 938 * (300 / 1074)) / 2);
  });

  it("maps a frame corner to the letterboxed position", () => {
    const { scale, offsetX, offsetY } = fitTransform(200, 100, 400, 400);
    expect(200 * scale + offsetX).toBeCloseTo(400);
    expect(100 * scale + offsetY).toBeCloseTo(300);
  });

  it("is safe for degenerate sizes", () => {
    expect(fitTransform(0, 0, 400, 400)).toEqual({ scale: 0, offsetX: 0, offsetY: 0 });
    expect(fitTransform(100, 100, 0, 0).scale).toBe(0);
  });
});

describe("nearestDetections", () => {
  it("returns the closest frame within maxGap", () => {
    const list = [det(1.0), det(1.1), det(1.2)];
    expect(nearestDetections(list, 1.12)?.pts).toBe(1.1);
  });

  it("returns null beyond maxGap", () => {
    expect(nearestDetections([det(1.0), det(1.1)], 2.0)).toBeNull();
    expect(nearestDetections([det(1.0)], 1.3, 0.25)).toBeNull();
    expect(nearestDetections([det(1.0)], 1.2, 0.25)?.pts).toBe(1.0);
  });

  it("returns null for an empty list (e.g. just after the clip looped)", () => {
    expect(nearestDetections([], 3)).toBeNull();
  });
});

describe("expectedPts", () => {
  const sync: SyncMsg = { type: "camera.sync", camera_id: "C", loop: 0, pts: 9, wall_time: 100 };

  it("advances with the wall clock", () => {
    expect(expectedPts(sync, 100.5, 20)).toBeCloseTo(9.5);
  });

  it("wraps at duration", () => {
    expect(expectedPts(sync, 103, 10)).toBeCloseTo(2);
  });

  it("never returns a negative value when the clocks disagree slightly", () => {
    expect(expectedPts({ ...sync, pts: 0 }, 99.9, 10)).toBeCloseTo(9.9);
  });
});
