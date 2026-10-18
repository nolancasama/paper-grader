export function createImage(width, height) {
  const data = new Uint8ClampedArray(width * height * 4);
  data.fill(255);
  return { width, height, data };
}

function pixel(image, x, y, color) {
  if (x < 0 || y < 0 || x >= image.width || y >= image.height) return;
  const i = (y * image.width + x) * 4;
  image.data.set([color[0], color[1], color[2], color[3] ?? 255], i);
}

export function fillRect(image, x, y, w, h, color) {
  for (let py = y; py < y + h; py++) for (let px = x; px < x + w; px++) pixel(image, px, py, color);
}

export function drawLine(image, x1, y1, x2, y2, color, thickness = 3) {
  const steps = Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1), 1);
  const radius = Math.max(0, Math.floor(thickness / 2));
  for (let step = 0; step <= steps; step++) {
    const x = Math.round(x1 + (x2 - x1) * step / steps);
    const y = Math.round(y1 + (y2 - y1) * step / steps);
    for (let py = y - radius; py <= y + radius; py++) for (let px = x - radius; px <= x + radius; px++) pixel(image, px, py, color);
  }
}

export function drawPolyline(image, points, color, thickness = 3) {
  for (let i = 1; i < points.length; i++) drawLine(image, points[i - 1][0], points[i - 1][1], points[i][0], points[i][1], color, thickness);
}

export function drawEllipse(image, cx, cy, rx, ry, color, thickness = 3) {
  const steps = Math.ceil(Math.PI * 2 * Math.max(rx, ry) * 2);
  let previous = [cx + rx, cy];
  for (let i = 1; i <= steps; i++) {
    const point = [cx + rx * Math.cos(i * Math.PI * 2 / steps), cy + ry * Math.sin(i * Math.PI * 2 / steps)];
    drawLine(image, previous[0], previous[1], point[0], point[1], color, thickness);
    previous = point;
  }
}
