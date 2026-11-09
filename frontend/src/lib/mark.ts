// Geometry of the Wings mark: seven strokes, one per phase.
// Read in order they trace a V, like the V-model: P1 to P3 descend the left wing,
// P4 (code generation) is the body, P5 to P7 climb the right wing.
export type Stroke = readonly [x1: number, y1: number, x2: number, y2: number];

const LEFT: Stroke[] = [
  [12.6, 12, 1.8, 8.1],
  [12.6, 17, 4.15, 13.9],
  [12.6, 22, 6.5, 19.8],
];
const BODY: Stroke = [16, 12, 16, 24];
const mirror = ([x1, y1, x2, y2]: Stroke): Stroke => [32 - x1, y1, 32 - x2, y2];

export const MARK_STROKES: Stroke[] = [...LEFT, BODY, ...LEFT.map(mirror).reverse()];
