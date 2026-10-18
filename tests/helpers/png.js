import { inflateSync } from 'node:zlib';

const signature = [137, 80, 78, 71, 13, 10, 26, 10];

function paeth(a, b, c) {
  const p = a + b - c;
  const pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
  return pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
}

// Minimal test-only decoder: 8-bit RGB/RGBA, non-interlaced PNGs.
export function decodePng(bytes) {
  const png = Buffer.from(bytes);
  if (!signature.every((value, i) => png[i] === value)) throw new Error('Invalid PNG signature');
  let width, height, channels;
  const compressed = [];
  for (let offset = 8; offset < png.length;) {
    if (offset + 12 > png.length) throw new Error('Truncated PNG chunk');
    const length = png.readUInt32BE(offset);
    const type = png.toString('ascii', offset + 4, offset + 8);
    const start = offset + 8, end = start + length;
    if (end + 4 > png.length) throw new Error('Truncated PNG chunk');
    if (type === 'IHDR') {
      if (length !== 13) throw new Error('Invalid PNG header');
      width = png.readUInt32BE(start);
      height = png.readUInt32BE(start + 4);
      const depth = png[start + 8], color = png[start + 9];
      if (!width || !height || depth !== 8 || (color !== 2 && color !== 6) ||
          png[start + 10] !== 0 || png[start + 11] !== 0 || png[start + 12] !== 0) {
        throw new Error('Unsupported PNG format');
      }
      channels = color === 2 ? 3 : 4;
    } else if (type === 'IDAT') {
      compressed.push(png.subarray(start, end));
    } else if (type === 'IEND') {
      break;
    }
    offset = end + 4;
  }
  if (!channels || !compressed.length) throw new Error('Missing PNG header or image data');
  const raw = inflateSync(Buffer.concat(compressed));
  const stride = width * channels;
  if (raw.length !== height * (stride + 1)) throw new Error('Invalid PNG image data length');
  const pixels = new Uint8Array(height * stride);
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)];
    if (filter > 4) throw new Error('Unsupported PNG filter');
    for (let x = 0; x < stride; x++) {
      const index = y * stride + x;
      const left = x >= channels ? pixels[index - channels] : 0;
      const up = y ? pixels[index - stride] : 0;
      const upperLeft = y && x >= channels ? pixels[index - stride - channels] : 0;
      const prediction = [0, left, up, Math.floor((left + up) / 2), paeth(left, up, upperLeft)][filter];
      pixels[index] = raw[y * (stride + 1) + x + 1] + prediction;
    }
  }
  const data = new Uint8ClampedArray(width * height * 4);
  for (let pixel = 0; pixel < width * height; pixel++) {
    data.set(pixels.subarray(pixel * channels, pixel * channels + 3), pixel * 4);
    data[pixel * 4 + 3] = channels === 4 ? pixels[pixel * channels + 3] : 255;
  }
  return { width, height, data };
}
