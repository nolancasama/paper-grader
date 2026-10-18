export const RED = [210, 35, 35];
export const BLACK = [30, 30, 30];
export const BLUE = [30, 65, 180];
export const PENCIL = [190, 190, 190];

export function image(width = 320, height = 240) {
  const data = new Uint8ClampedArray(width * height * 4);
  data.fill(255);
  return { width, height, data };
}

export function dot(target, x, y, radius, color = BLACK) {
  for (let py = Math.max(0, Math.floor(y - radius)); py <= Math.min(target.height - 1, Math.ceil(y + radius)); py++) {
    for (let px = Math.max(0, Math.floor(x - radius)); px <= Math.min(target.width - 1, Math.ceil(x + radius)); px++) {
      if ((px - x) ** 2 + (py - y) ** 2 > radius ** 2) continue;
      const index = (py * target.width + px) * 4;
      target.data.set([...color, 255], index);
    }
  }
}

export function polyline(target, points, color = BLACK, thickness = 3) {
  for (let i = 1; i < points.length; i++) {
    const from = points[i - 1];
    const to = points[i];
    const steps = Math.ceil(Math.hypot(to.x - from.x, to.y - from.y) * 2);
    for (let step = 0; step <= steps; step++) {
      const t = steps ? step / steps : 0;
      dot(target, from.x + (to.x - from.x) * t, from.y + (to.y - from.y) * t, thickness / 2, color);
    }
  }
}

export function bezier(target, points, color = BLACK, thickness = 3) {
  const samples = [];
  for (let i = 0; i <= 400; i++) {
    const t = i / 400;
    const s = 1 - t;
    samples.push({
      x: s ** 3 * points[0].x + 3 * s ** 2 * t * points[1].x + 3 * s * t ** 2 * points[2].x + t ** 3 * points[3].x,
      y: s ** 3 * points[0].y + 3 * s ** 2 * t * points[1].y + 3 * s * t ** 2 * points[2].y + t ** 3 * points[3].y,
    });
  }
  polyline(target, samples, color, thickness);
}

export function worksheet(count = 3, { width = 320, height = 240, rows } = {}) {
  const target = image(width, height);
  const positions = rows || Array.from({ length: count }, (_, i) => height * (0.16 + (count === 1 ? 0.34 : i * 0.68 / (count - 1))));
  const left = positions.map(y => ({ x: width * 0.15, y }));
  const right = positions.map(y => ({ x: width * 0.85, y }));
  for (const node of [...left, ...right]) dot(target, node.x, node.y, 3);
  for (let i = 0; i < count; i++) {
    for (const x of [width * 0.04, width * 0.91]) {
      polyline(target, [{ x, y: positions[i] - 4 }, { x: x + width * 0.045, y: positions[i] - 4 }], BLACK, 2);
      polyline(target, [{ x, y: positions[i] + 3 }, { x: x + width * 0.03, y: positions[i] + 3 }], BLACK, 2);
    }
  }
  return {
    target,
    left,
    right,
    endpoints: {
      left: left.map(({ x, y }) => ({ x: x / width, y: y / height })),
      right: right.map(({ x, y }) => ({ x: x / width, y: y / height })),
    },
  };
}

export function drawWeb(sheet, connections, { color = BLACK, thickness = 3, curve = 0 } = {}) {
  connections.forEach((target, i) => {
    if (target === null) return;
    const from = sheet.left[i];
    const to = sheet.right[target];
    if (curve) {
      const dx = to.x - from.x;
      bezier(sheet.target, [from, { x: from.x + dx * 0.3, y: from.y + curve }, { x: from.x + dx * 0.7, y: to.y + curve }, to], color, thickness);
    } else {
      polyline(sheet.target, [from, to], color, thickness);
    }
  });
  return sheet.target;
}

export function fixture(expected = [0, 1, 2], actual = expected, options = {}) {
  const key = worksheet(expected.length, options);
  const student = worksheet(expected.length, options);
  drawWeb(key, expected, { color: RED, ...options.key });
  drawWeb(student, actual, options.student);
  return { keyImage: key.target, studentImage: student.target, question: { endpoints: key.endpoints }, key, student };
}

export function shifted(source, dx, dy) {
  const target = image(source.width, source.height);
  for (let y = 0; y < source.height; y++) {
    for (let x = 0; x < source.width; x++) {
      const tx = x + dx;
      const ty = y + dy;
      if (tx < 0 || tx >= source.width || ty < 0 || ty >= source.height) continue;
      const from = (y * source.width + x) * 4;
      target.data.set(source.data.subarray(from, from + 4), (ty * source.width + tx) * 4);
    }
  }
  return target;
}

export function ambiguousFixture() {
  const result = fixture([0, 1], [1, 0], { rows: [95, 115] });
  dot(result.studentImage, 160, 105, 8);
  return result;
}
