export interface GridChoice {
  cols: number;
  rows: number;
}

/** The cols x rows that gives the footage the most on-screen area for the container size and the
 *  typical aspect ratio (width / height) of the video. A portrait feed in a landscape cell wastes
 *  space, so wide containers with portrait footage get more columns. */
export function bestGrid(count: number, width: number, height: number, aspect: number, gap = 8): GridChoice {
  if (count <= 1 || width <= 0 || height <= 0 || !(aspect > 0)) return { cols: 1, rows: 1 };
  const side = Math.ceil(Math.sqrt(count));
  let best: GridChoice = { cols: side, rows: Math.ceil(count / side) };
  let bestArea = -1;
  for (let cols = 1; cols <= count; cols++) {
    const rows = Math.ceil(count / cols);
    const cellW = (width - gap * (cols - 1)) / cols;
    const cellH = (height - gap * (rows - 1)) / rows;
    if (cellW < 150 || cellH < 110) continue; // too small to read
    const h = Math.min(cellW / aspect, cellH); // the footage is aspect*h wide and h tall
    const area = h * h * aspect;
    if (area > bestArea + 1) {
      bestArea = area;
      best = { cols, rows };
    }
  }
  return best;
}
