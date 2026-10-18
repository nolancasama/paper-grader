import assert from 'node:assert/strict';
import test from 'node:test';
import { detectRedRegions, isRedPixel, sortReadingOrder } from '../redDetect.js';
import { createImage, drawEllipse, drawLine, drawPolyline, fillRect } from './helpers/synthImage.js';

const red = [200, 35, 35];
const darkRed = [139, 0, 0];
const pinkRed = [225, 55, 100];

function word(image, x, y, color = red) {
  drawPolyline(image, [[x, y + 16], [x + 5, y], [x + 10, y + 16], [x + 15, y]], color, 4);
  drawLine(image, x + 21, y, x + 21, y + 16, color, 4);
  drawLine(image, x + 21, y + 8, x + 31, y + 8, color, 4);
  drawEllipse(image, x + 42, y + 8, 7, 9, color, 4);
}

test('finds handwritten words, circles, and numbers while dropping specks', () => {
  const image = createImage(600, 400);
  word(image, 40, 40); word(image, 250, 40); drawEllipse(image, 100, 160, 22, 22, red, 4);
  drawPolyline(image, [[270, 150], [290, 142], [290, 180], [272, 180]], red, 4);
  fillRect(image, 10, 300, 1, 1, red); fillRect(image, 20, 300, 1, 1, red);
  const result = detectRedRegions(image);
  assert.equal(result.regions.length, 4);
  assert.ok(result.regions.every((region) => region.kind === 'answer'));
});

test('keeps nearby but clearly separated answers apart and orders two columns by row', () => {
  const image = createImage(800, 500);
  word(image, 40, 40); word(image, 250, 40); word(image, 40, 210); word(image, 250, 210);
  const regions = detectRedRegions(image).regions;
  assert.equal(regions.length, 4);
  assert.deepEqual(regions.map((r) => [r.x < 0.2, r.y < 0.3]), [[true, true], [false, true], [true, false], [false, false]]);
  assert.deepEqual(sortReadingOrder([...regions]), regions);
});

test('ignores black, blue, grey, paper, and detects dark/pink reds', () => {
  const image = createImage(500, 220);
  word(image, 20, 30, [0, 0, 0]); word(image, 120, 30, [20, 70, 200]); word(image, 220, 30, [110, 110, 110]);
  word(image, 20, 130, darkRed); word(image, 220, 130, pinkRed);
  const regions = detectRedRegions(image).regions;
  assert.equal(regions.length, 2);
  assert.ok(isRedPixel(...darkRed)); assert.ok(isRedPixel(...pinkRed)); assert.equal(isRedPixel(20, 70, 200), false);
});

test('groups crossing matching lines into one matching region', () => {
  const image = createImage(700, 350);
  drawLine(image, 80, 80, 500, 210, red, 4);
  drawLine(image, 80, 210, 500, 80, red, 4);
  const [region] = detectRedRegions(image).regions;
  assert.equal(region.kind, 'matching');
  assert.equal(region.strokeCount, 1);
});

test('a tall web of three crossing lines is matching, while large circles and two-line answers are not', () => {
  const image = createImage(1240, 1754);
  drawLine(image, 268, 990, 692, 1290, red, 4);
  drawLine(image, 268, 1140, 692, 990, red, 4);
  drawLine(image, 268, 1290, 692, 1140, red, 4);
  drawEllipse(image, 300, 300, 110, 70, red, 4);
  for (let x = 700; x < 1100; x += 60) { word(image, x, 250); word(image, x, 330); }
  const regions = detectRedRegions(image).regions;
  const web = regions.find((r) => r.y > 0.5);
  assert.equal(web.kind, 'matching');
  assert.ok(regions.filter((r) => r.y < 0.5).every((r) => r.kind === 'answer'));
});

test('returns normalized, padded coordinates', () => {
  const image = createImage(500, 300);
  drawEllipse(image, 250, 150, 20, 20, red, 4);
  const [region] = detectRedRegions(image).regions;
  assert.ok(region.x < 0.46 && region.y < 0.42);
  assert.ok(region.w > 0.08 && region.h > 0.13);
  assert.ok(region.x >= 0 && region.y >= 0 && region.x + region.w <= 1 && region.y + region.h <= 1);
});

test('downsamples large pages and remains fast on A4 scan dimensions', () => {
  const image = createImage(2480, 3508);
  drawLine(image, 300, 300, 850, 300, red, 12);
  const start = performance.now();
  const result = detectRedRegions(image);
  assert.ok(performance.now() - start < 2000);
  assert.equal(result.regions.length, 1);
  assert.ok(result.regions[0].x > 0.1 && result.regions[0].x < 0.13);
});
