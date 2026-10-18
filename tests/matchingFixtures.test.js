import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { deflateSync } from 'node:zlib';
import { gradeMatching } from '../graders/matching.js';
import { decodePng } from './helpers/png.js';
import { fixture as syntheticFixture, polyline } from './helpers/matchingSynth.js';

const expected = { L1: 'R3', L2: 'R1', L3: 'R2' };
const students = [
  { name: 'alice', status: 'correct', credit: 1, connections: expected },
  { name: 'bob', status: 'partial', credit: 1 / 3, connections: { L1: 'R2', L2: 'R1', L3: 'R3' } },
  { name: 'cara', status: 'partial', credit: 2 / 3, connections: { L1: 'R3', L2: 'R1', L3: null } },
];

function fixture(crop, name) {
  return decodePng(readFileSync(new URL(`./fixtures/matching/${crop}-${name}.png`, import.meta.url)));
}

for (const crop of ['tight', 'wide']) {
  for (const student of students) {
    test(`Chrome canvas ${crop} matching crop: ${student.name}`, async () => {
      const result = await gradeMatching({ keyImage: fixture(crop, 'key'), studentImage: fixture(crop, student.name) });
      const details = JSON.stringify(result);
      assert.deepEqual(result.expected, expected, details);
      assert.deepEqual(result.connections, student.connections, details);
      assert.equal(result.status, student.status, details);
      assert.equal(result.credit, student.credit, details);
      assert.ok(result.confidence >= 0.8, details);
      assert.deepEqual(result.uncertain, [], details);
    });
  }
}

test('two left traces sharing an unresolved trunk are both uncertain', async () => {
  const input = syntheticFixture([0, 1, 2], [null, null, null]);
  const join = { x: 160, y: 120 };
  for (const index of [0, 2]) {
    polyline(input.studentImage, [input.student.left[index], join, input.student.right[1]]);
  }
  const result = await gradeMatching(input);
  assert.equal(result.status, null, JSON.stringify(result));
  assert.equal(result.credit, null);
  assert.ok(result.confidence < 0.8);
  assert.deepEqual(result.uncertain.slice().sort(), ['L1', 'L3']);
});

// Build rows with each PNG predictor, including wraparound and alpha values.
for (const channels of [3, 4]) {
  test(`PNG helper decodes all five filters for ${channels === 3 ? 'RGB' : 'RGBA'}`, () => {
    const width = 3, height = 5, stride = width * channels;
    const pixels = Uint8Array.from({ length: stride * height }, (_, i) => (i * 71 + 19) % 256);
    const raw = Buffer.alloc(height * (stride + 1));
    for (let y = 0; y < height; y++) {
      raw[y * (stride + 1)] = y;
      for (let x = 0; x < stride; x++) {
        const index = y * stride + x;
        const a = x >= channels ? pixels[index - channels] : 0;
        const b = y ? pixels[index - stride] : 0;
        const c = y && x >= channels ? pixels[index - stride - channels] : 0;
        const p = a + b - c;
        const nearest = [a, b, c].reduce((best, value) => Math.abs(p - value) < Math.abs(p - best) ? value : best);
        const predictor = [0, a, b, Math.floor((a + b) / 2), nearest][y];
        raw[y * (stride + 1) + x + 1] = (pixels[index] - predictor + 256) % 256;
      }
    }
    const chunk = (type, data) => {
      const result = Buffer.alloc(data.length + 12);
      result.writeUInt32BE(data.length);
      result.write(type, 4, 'ascii');
      result.set(data, 8);
      return result;
    };
    const header = Buffer.alloc(13);
    header.writeUInt32BE(width);
    header.writeUInt32BE(height, 4);
    header[8] = 8;
    header[9] = channels === 3 ? 2 : 6;
    const compressed = deflateSync(raw);
    const png = Buffer.concat([
      Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', header),
      chunk('IDAT', compressed.subarray(0, 7)), chunk('IDAT', compressed.subarray(7)), chunk('IEND', Buffer.alloc(0)),
    ]);
    const decoded = decodePng(png);
    assert.equal(decoded.width, width);
    assert.equal(decoded.height, height);
    assert.ok(decoded.data instanceof Uint8ClampedArray);
    const expectedPixels = Array.from({ length: width * height }, (_, i) => [
      ...pixels.subarray(i * channels, i * channels + 3), channels === 4 ? pixels[i * channels + 3] : 255,
    ]).flat();
    assert.deepEqual(Array.from(decoded.data), expectedPixels);
  });
}
