import assert from 'node:assert/strict';
import test from 'node:test';
import { detectDifferenceRegions, estimateAlignment, forwardCanvasTransform, inverseCanvasTransform } from '../alignment.js';

function image(width, height, fill = 255) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < data.length; i += 4) {
    data[i] = data[i + 1] = data[i + 2] = fill;
    data[i + 3] = 255;
  }
  return { width, height, data };
}

function rect(img, x0, y0, x1, y1, rgb = [20, 20, 20]) {
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
    const i = (y * img.width + x) * 4;
    img.data[i] = rgb[0];
    img.data[i + 1] = rgb[1];
    img.data[i + 2] = rgb[2];
  }
}

function template() {
  const img = image(240, 320);
  for (let y = 35; y < 285; y += 38) {
    rect(img, 25, y, 205, y + 3);
    rect(img, 30, y + 9, 95, y + 12);
    rect(img, 125, y + 9, 195, y + 12);
  }
  rect(img, 18, 20, 222, 23);
  rect(img, 18, 297, 222, 300);
  return img;
}

function shifted(source, dx, dy) {
  const out = image(source.width, source.height);
  for (let y = 0; y < source.height; y++) for (let x = 0; x < source.width; x++) {
    const tx = x + dx, ty = y + dy;
    if (tx < 0 || tx >= out.width || ty < 0 || ty >= out.height) continue;
    const s = (y * source.width + x) * 4;
    const d = (ty * out.width + tx) * 4;
    out.data[d] = source.data[s];
    out.data[d + 1] = source.data[s + 1];
    out.data[d + 2] = source.data[s + 2];
  }
  return out;
}

test('alignment recovers ordinary copier translation', () => {
  const blank = template();
  const scan = shifted(blank, 5, -4);
  const found = estimateAlignment(blank, scan, { maxAngleDeg: 0, coarseScaleDelta: 0 });
  assert.ok(found.confidence > 0.6, JSON.stringify(found));
  assert.ok(Math.abs(found.dx - 5 / blank.width) < 0.02, JSON.stringify(found));
  assert.ok(Math.abs(found.dy + 4 / blank.height) < 0.02, JSON.stringify(found));
});

test('difference detection ignores shared print and finds teacher additions', () => {
  const blank = template();
  const key = { width: blank.width, height: blank.height, data: new Uint8ClampedArray(blank.data) };
  rect(key, 72, 78, 130, 84, [10, 10, 10]);
  rect(key, 150, 188, 156, 230, [200, 20, 20]);
  const result = detectDifferenceRegions(blank, key);
  assert.ok(result.differencePixelCount > 100);
  assert.ok(result.regions.length >= 2, JSON.stringify(result.regions));
});

test('identical blank and key create no answer proposals', () => {
  const blank = template();
  const key = { width: blank.width, height: blank.height, data: new Uint8ClampedArray(blank.data) };
  const result = detectDifferenceRegions(blank, key);
  assert.equal(result.differencePixelCount, 0);
  assert.equal(result.regions.length, 0);
});

test('forward and inverse canvas transforms are exact inverses', () => {
  const alignment = { angleDeg: 1.5, scale: 1.012, dx: 0.02, dy: -0.015 };
  const f = forwardCanvasTransform(alignment, 800, 1100);
  const i = inverseCanvasTransform(alignment, 800, 1100);
  const apply = (m, [x, y]) => [m.a * x + m.c * y + m.e, m.b * x + m.d * y + m.f];
  for (const point of [[0, 0], [400, 550], [790, 20], [100, 1000]]) {
    const back = apply(i, apply(f, point));
    assert.ok(Math.abs(back[0] - point[0]) < 1e-6 && Math.abs(back[1] - point[1]) < 1e-6);
  }
});
