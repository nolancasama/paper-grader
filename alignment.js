export const DEFAULT_ALIGNMENT_OPTIONS = {
  workingWidth: 420,
  sampleLimit: 850,
  minReferenceDarkness: 34,
  maxAngleDeg: 2,
  coarseScaleDelta: 0.015,
  localShift: 0.014,
  reviewThreshold: 0.78,
};

export const DEFAULT_DIFFERENCE_OPTIONS = {
  workingWidth: 1100,
  minDarkening: 30,
  minColorDistance: 52,
  minSaturation: 0.16,
  speckArea: 0.000003,
  joinRadius: 0.006,
  minRegionArea: 0.000022,
  padding: 0.007,
  matchingPadding: 0.032,
};

const clamp = (value, low = 0, high = 1) => Math.max(low, Math.min(high, value));

function validateImage(image) {
  if (!image || !Number.isInteger(image.width) || !Number.isInteger(image.height)
      || image.width < 1 || image.height < 1 || !image.data
      || image.data.length < image.width * image.height * 4) {
    throw new TypeError('Expected an RGBA ImageData-like object');
  }
}

function resample(image, width, height) {
  validateImage(image);
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++) {
    const sy = Math.min(image.height - 1, Math.floor((y + 0.5) * image.height / height));
    for (let x = 0; x < width; x++) {
      const sx = Math.min(image.width - 1, Math.floor((x + 0.5) * image.width / width));
      const source = (sy * image.width + sx) * 4;
      const target = (y * width + x) * 4;
      data[target] = image.data[source];
      data[target + 1] = image.data[source + 1];
      data[target + 2] = image.data[source + 2];
      data[target + 3] = image.data[source + 3] ?? 255;
    }
  }
  return { width, height, data };
}

function lumaData(image) {
  const out = new Float32Array(image.width * image.height);
  for (let p = 0, i = 0; p < out.length; p++, i += 4) {
    const alpha = (image.data[i + 3] ?? 255) / 255;
    const r = 255 - (255 - image.data[i]) * alpha;
    const g = 255 - (255 - image.data[i + 1]) * alpha;
    const b = 255 - (255 - image.data[i + 2]) * alpha;
    out[p] = 0.299 * r + 0.587 * g + 0.114 * b;
  }
  return out;
}

function darknessData(image) {
  const luma = lumaData(image);
  for (let i = 0; i < luma.length; i++) luma[i] = 255 - luma[i];
  return luma;
}

function maxFilter(values, width, height, radius = 1) {
  const out = new Float32Array(values.length);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    let best = 0;
    for (let dy = -radius; dy <= radius; dy++) {
      const yy = y + dy;
      if (yy < 0 || yy >= height) continue;
      for (let dx = -radius; dx <= radius; dx++) {
        const xx = x + dx;
        if (xx >= 0 && xx < width) best = Math.max(best, values[yy * width + xx]);
      }
    }
    out[y * width + x] = best;
  }
  return out;
}

function minFilter(values, width, height, radius = 1) {
  const out = new Float32Array(values.length);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    let best = 255;
    for (let dy = -radius; dy <= radius; dy++) {
      const yy = y + dy;
      if (yy < 0 || yy >= height) continue;
      for (let dx = -radius; dx <= radius; dx++) {
        const xx = x + dx;
        if (xx >= 0 && xx < width) best = Math.min(best, values[yy * width + xx]);
      }
    }
    out[y * width + x] = best;
  }
  return out;
}

function weightedCentroid(values, width, height, threshold) {
  let sx = 0, sy = 0, total = 0;
  for (let y = 1; y < height - 1; y++) for (let x = 1; x < width - 1; x++) {
    const value = values[y * width + x];
    if (value < threshold) continue;
    const weight = Math.min(2, value / threshold);
    sx += x * weight;
    sy += y * weight;
    total += weight;
  }
  return total ? { x: sx / total, y: sy / total } : { x: width / 2, y: height / 2 };
}

function referenceSamples(dark, width, height, options) {
  const candidates = [];
  const marginX = Math.max(2, Math.round(width * 0.025));
  const marginY = Math.max(2, Math.round(height * 0.02));
  for (let y = marginY; y < height - marginY; y++) for (let x = marginX; x < width - marginX; x++) {
    const p = y * width + x;
    if (dark[p] < options.minReferenceDarkness) continue;
    const gradient = Math.abs(dark[p + 1] - dark[p - 1]) + Math.abs(dark[p + width] - dark[p - width]);
    if (gradient < 20) continue;
    candidates.push({ x, y, darkness: dark[p], weight: Math.min(2, 0.5 + gradient / 80) });
  }
  if (!candidates.length) return [];
  const stride = Math.max(1, Math.ceil(candidates.length / options.sampleLimit));
  return candidates.filter((_, index) => index % stride === 0).slice(0, options.sampleLimit);
}

function scoreTransform(samples, targetDark, width, height, transform) {
  if (!samples.length) return 0;
  const angle = transform.angleDeg * Math.PI / 180;
  const cos = Math.cos(angle), sin = Math.sin(angle);
  const cx = width / 2, cy = height / 2;
  const dx = transform.dx * width, dy = transform.dy * height;
  let score = 0, total = 0;
  for (const sample of samples) {
    const px = sample.x - cx, py = sample.y - cy;
    const x = Math.round(cx + transform.scale * (cos * px - sin * py) + dx);
    const y = Math.round(cy + transform.scale * (sin * px + cos * py) + dy);
    total += sample.weight;
    if (x < 0 || x >= width || y < 0 || y >= height) continue;
    const target = targetDark[y * width + x];
    const required = Math.max(24, sample.darkness * 0.32);
    score += sample.weight * clamp(target / required);
  }
  return total ? score / total : 0;
}

function transformedCentroid(point, width, height, angleDeg, scale) {
  const angle = angleDeg * Math.PI / 180;
  const cos = Math.cos(angle), sin = Math.sin(angle);
  const cx = width / 2, cy = height / 2;
  const x = point.x - cx, y = point.y - cy;
  return {
    x: cx + scale * (cos * x - sin * y),
    y: cy + scale * (sin * x + cos * y),
  };
}

export function estimateAlignment(referenceImage, targetImage, options = {}) {
  validateImage(referenceImage);
  validateImage(targetImage);
  const settings = { ...DEFAULT_ALIGNMENT_OPTIONS, ...options };
  const width = Math.min(settings.workingWidth, referenceImage.width);
  const height = Math.max(1, Math.round(referenceImage.height * width / referenceImage.width));
  const reference = resample(referenceImage, width, height);
  const target = resample(targetImage, width, height);
  const referenceDark = darknessData(reference);
  const targetDarkRaw = darknessData(target);
  const targetDark = maxFilter(targetDarkRaw, width, height, 1);
  const samples = referenceSamples(referenceDark, width, height, settings);
  if (samples.length < 25) {
    return { angleDeg: 0, scale: 1, dx: 0, dy: 0, quality: 0, confidence: 0, sampleCount: samples.length };
  }
  const refCenter = weightedCentroid(referenceDark, width, height, settings.minReferenceDarkness);
  const targetCenter = weightedCentroid(targetDarkRaw, width, height, settings.minReferenceDarkness);
  const angles = [-settings.maxAngleDeg, -settings.maxAngleDeg / 2, 0, settings.maxAngleDeg / 2, settings.maxAngleDeg];
  const scales = [1 - settings.coarseScaleDelta, 1, 1 + settings.coarseScaleDelta];
  const local = Math.max(2, Math.round(width * settings.localShift));
  const offsets = [-local, -Math.round(local / 2), 0, Math.round(local / 2), local];
  let best = { score: -1, angleDeg: 0, scale: 1, dx: 0, dy: 0 };
  for (const angleDeg of angles) for (const scale of scales) {
    const mapped = transformedCentroid(refCenter, width, height, angleDeg, scale);
    const baseDx = targetCenter.x - mapped.x;
    const baseDy = targetCenter.y - mapped.y;
    for (const ox of offsets) for (const oy of offsets) {
      const transform = { angleDeg, scale, dx: (baseDx + ox) / width, dy: (baseDy + oy) / height };
      const score = scoreTransform(samples, targetDark, width, height, transform)
        - Math.abs(angleDeg) * 0.001 - Math.abs(scale - 1) * 0.08;
      if (score > best.score) best = { ...transform, score };
    }
  }
  const refineAngles = [best.angleDeg - 0.5, best.angleDeg, best.angleDeg + 0.5]
    .filter(value => Math.abs(value) <= settings.maxAngleDeg + 0.5);
  const refineScales = [best.scale - 0.005, best.scale, best.scale + 0.005];
  const refineShift = Math.max(1, Math.round(width * 0.004));
  for (const angleDeg of refineAngles) for (const scale of refineScales)
    for (const ox of [-refineShift, 0, refineShift]) for (const oy of [-refineShift, 0, refineShift]) {
      const transform = { angleDeg, scale, dx: best.dx + ox / width, dy: best.dy + oy / height };
      const score = scoreTransform(samples, targetDark, width, height, transform)
        - Math.abs(angleDeg) * 0.001 - Math.abs(scale - 1) * 0.08;
      if (score > best.score) best = { ...transform, score };
    }
  const quality = clamp(best.score);
  const confidence = clamp((quality - 0.48) / 0.42);
  return {
    angleDeg: best.angleDeg,
    scale: best.scale,
    dx: best.dx,
    dy: best.dy,
    quality,
    confidence,
    sampleCount: samples.length,
  };
}

export function inverseCanvasTransform(alignment, width, height) {
  const scale = Number.isFinite(alignment?.scale) && alignment.scale > 0 ? alignment.scale : 1;
  const angle = -(Number(alignment?.angleDeg) || 0) * Math.PI / 180;
  const cos = Math.cos(angle) / scale;
  const sin = Math.sin(angle) / scale;
  const a = cos, b = sin, c = -sin, d = cos;
  const cx = width / 2, cy = height / 2;
  const tx = cx + (Number(alignment?.dx) || 0) * width;
  const ty = cy + (Number(alignment?.dy) || 0) * height;
  return {
    a, b, c, d,
    e: cx - a * tx - c * ty,
    f: cy - b * tx - d * ty,
  };
}

// Maps template coordinates onto the (size-normalized) raw page, e.g. for printing marks on the physical sheet.
export function forwardCanvasTransform(alignment, width, height) {
  const scale = Number.isFinite(alignment?.scale) && alignment.scale > 0 ? alignment.scale : 1;
  const angle = (Number(alignment?.angleDeg) || 0) * Math.PI / 180;
  const a = scale * Math.cos(angle), b = scale * Math.sin(angle), c = -b, d = a;
  const cx = width / 2, cy = height / 2;
  return {
    a, b, c, d,
    e: cx + (Number(alignment?.dx) || 0) * width - a * cx - c * cy,
    f: cy + (Number(alignment?.dy) || 0) * height - b * cx - d * cy,
  };
}

function walk(mask, width, height, start, queue) {
  let head = 0, tail = 0;
  queue[tail++] = start;
  mask[start] = 0;
  let count = 0, minX = width, minY = height, maxX = 0, maxY = 0;
  while (head < tail) {
    const index = queue[head++];
    const x = index % width, y = Math.floor(index / width);
    count++;
    minX = Math.min(minX, x); minY = Math.min(minY, y);
    maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
    for (let yy = y - 1; yy <= y + 1; yy++) for (let xx = x - 1; xx <= x + 1; xx++) {
      if (xx < 0 || xx >= width || yy < 0 || yy >= height || (xx === x && yy === y)) continue;
      const next = yy * width + xx;
      if (mask[next]) {
        mask[next] = 0;
        queue[tail++] = next;
      }
    }
  }
  return { count, minX, minY, maxX, maxY, tail };
}

function removeSpecks(mask, width, height, minimum) {
  const queue = new Int32Array(mask.length);
  for (let i = 0; i < mask.length; i++) {
    if (!mask[i]) continue;
    const component = walk(mask, width, height, i, queue);
    if (component.count >= minimum) for (let q = 0; q < component.tail; q++) mask[queue[q]] = 1;
  }
}

function dilate(mask, width, height, rx, ry) {
  const temp = new Uint8Array(mask.length), out = new Uint8Array(mask.length);
  for (let y = 0; y < height; y++) {
    let until = -1;
    for (let x = 0; x < width; x++) {
      if (mask[y * width + x]) until = x + rx;
      if (until >= x) temp[y * width + x] = 1;
    }
    until = width;
    for (let x = width - 1; x >= 0; x--) {
      if (mask[y * width + x]) until = x - rx;
      if (until <= x) temp[y * width + x] = 1;
    }
  }
  for (let x = 0; x < width; x++) {
    let until = -1;
    for (let y = 0; y < height; y++) {
      if (temp[y * width + x]) until = y + ry;
      if (until >= y) out[y * width + x] = 1;
    }
    until = height;
    for (let y = height - 1; y >= 0; y--) {
      if (temp[y * width + x]) until = y - ry;
      if (until <= y) out[y * width + x] = 1;
    }
  }
  return out;
}

function scaled(value, width, area = false) {
  if (value > 1) return Math.max(1, Math.round(value));
  return Math.max(1, Math.round(value * (area ? width * width : width)));
}

function saturation(r, g, b) {
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  return max ? (max - min) / max : 0;
}

function differenceMask(blank, key, options) {
  const blankLuma = lumaData(blank), keyLuma = lumaData(key);
  const nearbyBlank = minFilter(blankLuma, blank.width, blank.height, 1);
  const mask = new Uint8Array(blank.width * blank.height);
  for (let p = 0, i = 0; p < mask.length; p++, i += 4) {
    const kr = key.data[i], kg = key.data[i + 1], kb = key.data[i + 2];
    const br = blank.data[i], bg = blank.data[i + 1], bb = blank.data[i + 2];
    const darkening = nearbyBlank[p] - keyLuma[p];
    const colorDistance = Math.hypot(kr - br, kg - bg, kb - bb);
    const coloredAddition = colorDistance >= options.minColorDistance
      && saturation(kr, kg, kb) >= options.minSaturation
      && keyLuma[p] < 235 && blankLuma[p] - keyLuma[p] > 8;
    if (darkening >= options.minDarkening || coloredAddition) mask[p] = 1;
  }
  return mask;
}

export function detectDifferenceRegions(blankImage, keyImage, options = {}) {
  validateImage(blankImage);
  validateImage(keyImage);
  const settings = { ...DEFAULT_DIFFERENCE_OPTIONS, ...options };
  const width = Math.min(settings.workingWidth, blankImage.width);
  const height = Math.max(1, Math.round(blankImage.height * width / blankImage.width));
  const blank = resample(blankImage, width, height);
  const key = resample(keyImage, width, height);
  const clean = differenceMask(blank, key, settings);
  removeSpecks(clean, width, height, scaled(settings.speckArea, width, true));
  let differencePixelCount = 0;
  for (const value of clean) differencePixelCount += value;
  const radius = scaled(settings.joinRadius, width);
  const joined = dilate(clean, width, height, radius, Math.max(1, Math.round(radius * 0.55)));
  const queue = new Int32Array(clean.length);
  const joinedCopy = joined.slice();
  const groups = [];
  for (let i = 0; i < joinedCopy.length; i++) {
    if (!joinedCopy[i]) continue;
    const component = walk(joinedCopy, width, height, i, queue);
    groups.push({ ...component, pixels: 0, strokes: 0, longStrokes: 0 });
  }
  const strokeMask = clean.slice();
  for (let i = 0; i < strokeMask.length; i++) {
    if (!strokeMask[i]) continue;
    const stroke = walk(strokeMask, width, height, i, queue);
    const cx = (stroke.minX + stroke.maxX) / 2, cy = (stroke.minY + stroke.maxY) / 2;
    const group = groups.find(g => cx >= g.minX && cx <= g.maxX && cy >= g.minY && cy <= g.maxY);
    if (!group) continue;
    group.pixels += stroke.count;
    group.strokes++;
    const sw = stroke.maxX - stroke.minX + 1, sh = stroke.maxY - stroke.minY + 1;
    const fill = stroke.count / Math.max(1, sw * sh);
    if (sw >= width * 0.08 && sw / Math.max(1, sh) >= 1.5 && fill < 0.48) group.longStrokes++;
  }
  const minimum = scaled(settings.minRegionArea, width, true);
  const regions = [];
  for (const group of groups) {
    if (group.pixels < minimum) continue;
    const boxW = group.maxX - group.minX + 1, boxH = group.maxY - group.minY + 1;
    let inkPixels = 0;
    for (let y = group.minY; y <= group.maxY; y++) for (let x = group.minX; x <= group.maxX; x++)
      inkPixels += clean[y * width + x];
    const fill = inkPixels / Math.max(1, boxW * boxH);
    const matching = group.longStrokes >= 2 || (boxW >= width * 0.14 && boxH >= width * 0.05 && fill < 0.12 && group.strokes >= 2);
    const padX = (matching ? settings.matchingPadding : settings.padding) * width;
    const padY = (matching ? settings.matchingPadding * 0.5 : settings.padding) * width;
    const x = Math.max(0, (group.minX - padX) / width);
    const y = Math.max(0, (group.minY - padY) / height);
    const right = Math.min(width, group.maxX + 1 + padX) / width;
    const bottom = Math.min(height, group.maxY + 1 + padY) / height;
    let confidence = Math.min(0.97, 0.58 + Math.min(0.28, group.pixels / Math.max(1, minimum * 12)) + Math.min(0.1, group.strokes * 0.02));
    if (fill < 0.008 || boxW * boxH > width * height * 0.3) confidence = Math.min(confidence, 0.58);
    regions.push({
      x, y, w: right - x, h: bottom - y,
      pixelCount: group.pixels, strokeCount: group.strokes,
      confidence, uncertain: confidence < 0.65,
      kind: matching ? 'matching' : 'answer',
    });
  }
  return { width: blankImage.width, height: blankImage.height, differencePixelCount, regions };
}
