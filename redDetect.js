export const DEFAULT_RED_OPTIONS = {
  workingWidth: 1200,
  minSaturation: 0.28,
  minRedness: 42,
  minValue: 0.16,
  maxHueDeg: 35,
  joinRadius: 0.006,
  minComponentArea: 0.000004,
  minRegionArea: 0.000025,
  padding: 0.006,
  matchingPadding: 0.035
};

function mergedOptions(options) {
  return { ...DEFAULT_RED_OPTIONS, ...options };
}

function scaled(value, width, area) {
  if (value > 1) return Math.round(value);
  return Math.max(1, Math.round(value * (area ? width * width : width)));
}

export function isRedPixel(r, g, b, options = DEFAULT_RED_OPTIONS) {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  if (!max || max / 255 < options.minValue || max - Math.max(g, b) < options.minRedness) return false;
  const saturation = (max - min) / max;
  if (saturation < options.minSaturation) return false;
  let hue;
  if (max === r) hue = 60 * (((g - b) / (max - min)) % 6);
  else if (max === g) hue = 60 * ((b - r) / (max - min) + 2);
  else hue = 60 * ((r - g) / (max - min) + 4);
  if (hue < 0) hue += 360;
  return Math.min(hue, 360 - hue) <= options.maxHueDeg;
}

export function redMask(imageData, options = DEFAULT_RED_OPTIONS) {
  const { width, height, data } = imageData;
  const mask = new Uint8Array(width * height);
  for (let i = 0, p = 0; p < mask.length; p++, i += 4) {
    mask[p] = isRedPixel(data[i], data[i + 1], data[i + 2], options) ? 1 : 0;
  }
  return mask;
}

function downsample(imageData, targetWidth) {
  if (imageData.width <= targetWidth * 1.25) return imageData;
  const scale = targetWidth / imageData.width;
  const width = Math.max(1, Math.round(imageData.width * scale));
  const height = Math.max(1, Math.round(imageData.height * scale));
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++) {
    const y0 = Math.floor(y * imageData.height / height);
    const y1 = Math.max(y0 + 1, Math.floor((y + 1) * imageData.height / height));
    for (let x = 0; x < width; x++) {
      const x0 = Math.floor(x * imageData.width / width);
      const x1 = Math.max(x0 + 1, Math.floor((x + 1) * imageData.width / width));
      const count = (x1 - x0) * (y1 - y0);
      const out = (y * width + x) * 4;
      for (let c = 0; c < 4; c++) {
        let sum = 0;
        for (let sy = y0; sy < y1; sy++) for (let sx = x0; sx < x1; sx++) sum += imageData.data[(sy * imageData.width + sx) * 4 + c];
        data[out + c] = sum / count;
      }
    }
  }
  return { width, height, data };
}

function walkComponent(mask, width, height, start, queue, visit) {
  let head = 0;
  let tail = 0;
  queue[tail++] = start;
  mask[start] = 0;
  let count = 0;
  let minX = width, minY = height, maxX = 0, maxY = 0;
  while (head < tail) {
    const index = queue[head++];
    const x = index % width;
    const y = (index - x) / width;
    count++;
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
    if (visit) visit(index);
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      if (!dx && !dy) continue;
      const nx = x + dx;
      const ny = y + dy;
      const next = ny * width + nx;
      if (nx >= 0 && nx < width && ny >= 0 && ny < height && mask[next]) {
        mask[next] = 0;
        queue[tail++] = next;
      }
    }
  }
  return { count, minX, minY, maxX, maxY, tail };
}

function removeSpecks(mask, width, height, minArea) {
  const queue = new Int32Array(mask.length);
  for (let i = 0; i < mask.length; i++) {
    if (!mask[i]) continue;
    const component = walkComponent(mask, width, height, i, queue);
    if (component.count >= minArea) for (let q = 0; q < component.tail; q++) mask[queue[q]] = 1;
  }
}

function dilate(mask, width, height, horizontalRadius, verticalRadius) {
  const horizontal = new Uint8Array(mask.length);
  const output = new Uint8Array(mask.length);
  for (let y = 0; y < height; y++) {
    let last = -1;
    const row = y * width;
    for (let x = 0; x < width; x++) {
      if (mask[row + x]) last = x + horizontalRadius;
      if (last >= x) horizontal[row + x] = 1;
    }
    last = width;
    for (let x = width - 1; x >= 0; x--) {
      if (mask[row + x]) last = x - horizontalRadius;
      if (last <= x) horizontal[row + x] = 1;
    }
  }
  for (let x = 0; x < width; x++) {
    let last = -1;
    for (let y = 0; y < height; y++) {
      if (horizontal[y * width + x]) last = y + verticalRadius;
      if (last >= y) output[y * width + x] = 1;
    }
    last = height;
    for (let y = height - 1; y >= 0; y--) {
      if (horizontal[y * width + x]) last = y - verticalRadius;
      if (last <= y) output[y * width + x] = 1;
    }
  }
  return output;
}

// Counts separate vertical runs of a group's red pixels inside its left or right edge band (a circle has one, a web of lines several).
function edgeRuns(mask, labels, label, width, group, side) {
  const band = Math.max(2, Math.round((group.maxX - group.minX + 1) * 0.12));
  const x0 = side === 'left' ? group.minX : group.maxX - band + 1;
  const gap = Math.max(3, Math.round(width * 0.012));
  let runs = 0, lastHit = -Infinity;
  for (let y = group.minY; y <= group.maxY; y++) {
    let hit = false;
    for (let x = x0; x < x0 + band && !hit; x++) {
      const index = y * width + x;
      hit = mask[index] === 1 && labels[index] === label;
    }
    if (!hit) continue;
    if (y - lastHit > gap) runs++;
    lastHit = y;
  }
  return runs;
}

// Rows are identified by substantial vertical overlap, so two-column worksheets read left then right within each aligned row.
export function sortReadingOrder(regions) {
  const pending = [...regions].sort((a, b) => a.y - b.y || a.x - b.x);
  const rows = [];
  for (const region of pending) {
    const row = rows.find((candidate) => {
      const probe = candidate[0];
      const overlap = Math.max(0, Math.min(region.y + region.h, probe.y + probe.h) - Math.max(region.y, probe.y));
      return overlap >= Math.min(region.h, probe.h) * 0.5;
    });
    if (row) row.push(region);
    else rows.push([region]);
  }
  return rows.flatMap((row) => row.sort((a, b) => a.x - b.x));
}

export function detectRedRegions(imageData, options = {}) {
  const settings = mergedOptions(options);
  const source = downsample(imageData, settings.workingWidth);
  const { width, height } = source;
  const clean = redMask(source, settings);
  removeSpecks(clean, width, height, scaled(settings.minComponentArea, width, true));
  let redPixelCount = 0;
  for (const value of clean) redPixelCount += value;
  const radius = scaled(settings.joinRadius, width, false);
  const joined = dilate(clean, width, height, radius, Math.max(1, Math.round(radius * 0.55)));
  const labels = new Int32Array(clean.length);
  const groups = [];
  const queue = new Int32Array(clean.length);
  let label = 0;
  for (let i = 0; i < joined.length; i++) {
    if (!joined[i]) continue;
    label++;
    const component = walkComponent(joined, width, height, i, queue, (index) => { labels[index] = label; });
    groups[label] = { pixels: 0, strokes: 0, longStrokes: 0, minX: width, minY: height, maxX: -1, maxY: -1 };
    void component;
  }
  const strokes = new Uint8Array(clean);
  for (let i = 0; i < strokes.length; i++) {
    if (!strokes[i]) continue;
    const component = walkComponent(strokes, width, height, i, queue);
    const group = groups[labels[i]];
    if (!group) continue;
    group.strokes++;
    group.pixels += component.count;
    group.minX = Math.min(group.minX, component.minX);
    group.minY = Math.min(group.minY, component.minY);
    group.maxX = Math.max(group.maxX, component.maxX);
    group.maxY = Math.max(group.maxY, component.maxY);
    const strokeW = component.maxX - component.minX + 1;
    const strokeH = component.maxY - component.minY + 1;
    const fill = component.count / (strokeW * strokeH);
    if (strokeW >= width * 0.08 && strokeW / strokeH >= 1.5 && fill < 0.45) group.longStrokes++;
  }
  const minRegion = scaled(settings.minRegionArea, width, true);
  const regions = [];
  for (let i = 1; i < groups.length; i++) {
    const group = groups[i];
    if (!group || group.pixels < minRegion) continue;
    const boxW = group.maxX - group.minX + 1;
    const boxH = group.maxY - group.minY + 1;
    const fill = group.pixels / (boxW * boxH);
    // Crossing lines collapse into one stroke component, so also look for a sparse web with several ends on both sides.
    const web = boxW >= width * 0.12 && boxH >= width * 0.04 && fill < 0.14
      && edgeRuns(clean, labels, i, width, group, 'left') >= 2 && edgeRuns(clean, labels, i, width, group, 'right') >= 2;
    const isMatching = web || group.longStrokes >= 2;
    // Matching lines stop at printed dots/labels, so give the grader and reviewer room to see the endpoints.
    const padX = (isMatching ? settings.matchingPadding : settings.padding) * width;
    const padY = (isMatching ? settings.matchingPadding * 0.5 : settings.padding) * width;
    const x = Math.max(0, (group.minX - padX) / width);
    const y = Math.max(0, (group.minY - padY) / height);
    const right = Math.min(width, group.maxX + 1 + padX) / width;
    const bottom = Math.min(height, group.maxY + 1 + padY) / height;
    const large = boxW * boxH > width * height * 0.25;
    let confidence = Math.min(0.96, 0.45 + Math.min(0.35, group.pixels / (minRegion * 16)) + Math.min(0.16, group.strokes * 0.025));
    if (group.pixels < minRegion * 2 || fill < 0.012 || large) confidence = Math.min(confidence, 0.55);
    regions.push({ x, y, w: right - x, h: bottom - y, pixelCount: group.pixels, strokeCount: group.strokes, confidence, uncertain: confidence < 0.6, kind: isMatching ? 'matching' : 'answer' });
  }
  const ordered = sortReadingOrder(regions);
  for (let i = 0; i < ordered.length; i++) for (let j = i + 1; j < ordered.length; j++) {
    const a = ordered[i], b = ordered[j];
    if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) {
      a.confidence = Math.min(a.confidence, 0.55); b.confidence = Math.min(b.confidence, 0.55); a.uncertain = b.uncertain = true;
    }
  }
  return { width: imageData.width, height: imageData.height, redPixelCount, regions: ordered };
}
