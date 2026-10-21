import { getFallback, registerGrader } from '../graders.js';

// Work on a bounded grid: topology survives scan resolution, while thinning stays cheap.
function dimensions(image) {
  if (!image || !Number.isInteger(image.width) || !Number.isInteger(image.height)
      || image.width < 1 || image.height < 1 || !image.data
      || image.data.length < image.width * image.height * 4) {
    throw new TypeError('Expected an RGBA ImageData-like crop');
  }
  const scale = Math.min(1, 480 / image.width, 360 / image.height);
  return { width: Math.round(image.width * scale), height: Math.round(image.height * scale) };
}

function masks(image, width, height) {
  dimensions(image);
  const ink = new Uint8Array(width * height);
  const red = new Uint8Array(ink.length);
  const print = new Uint8Array(ink.length);
  const xs = Array.from({ length: image.width }, (_, x) => Math.min(width - 1, Math.floor(x * width / image.width)));
  for (let y = 0; y < image.height; y++) {
    const row = Math.min(height - 1, Math.floor(y * height / image.height)) * width;
    for (let x = 0; x < image.width; x++) {
      const i = (y * image.width + x) * 4;
      const alpha = image.data[i + 3] / 255;
      const r = 255 - (255 - image.data[i]) * alpha;
      const g = 255 - (255 - image.data[i + 1]) * alpha;
      const b = 255 - (255 - image.data[i + 2]) * alpha;
      if (0.299 * r + 0.587 * g + 0.114 * b > 238) continue;
      const p = row + xs[x];
      ink[p] = 1;
      // White anti-aliasing reduces absolute channel differences, but preserves
      // red's share of the darkness. Its pale fringe must not become printed ink:
      // downsampling and background dilation would erase nearby student strokes.
      if (r > 80 && r - g > (255 - g) * 0.2 && r - b > (255 - b) * 0.2) red[p] = 1;
      else print[p] = 1;
    }
  }
  return { ink, red, print };
}

function points(mask) {
  const out = [];
  for (let i = 0; i < mask.length; i++) if (mask[i]) out.push(i);
  return out;
}

function dilate(mask, width, height, radius = 1) {
  const out = new Uint8Array(mask.length);
  for (const p of points(mask)) {
    const x = p % width;
    const y = Math.floor(p / width);
    for (let dy = -radius; dy <= radius; dy++) {
      if (y + dy < 0 || y + dy >= height) continue;
      for (let dx = -radius; dx <= radius; dx++) {
        if (x + dx >= 0 && x + dx < width) out[p + dy * width + dx] = 1;
      }
    }
  }
  return out;
}

function bestShift(reference, target, width, height) {
  const all = points(reference);
  if (!all.length) return { dx: 0, dy: 0 };
  const sample = all.filter((_, i) => i % Math.max(1, Math.ceil(all.length / 400)) === 0);
  const rx = Math.max(1, Math.round(width * 0.04));
  const ry = Math.max(1, Math.round(height * 0.04));
  let best = -Infinity;
  let shift = { dx: 0, dy: 0 };
  for (let dy = -ry; dy <= ry; dy++) {
    for (let dx = -rx; dx <= rx; dx++) {
      let hits = 0;
      for (const p of sample) {
        const x = p % width + dx;
        const y = Math.floor(p / width) + dy;
        if (x >= 0 && x < width && y >= 0 && y < height) hits += target[y * width + x];
      }
      const score = hits - (dx * dx + dy * dy) * 0.0001;
      if (score > best) {
        best = score;
        shift = { dx, dy };
      }
    }
  }
  return shift;
}

function align(mask, width, height, { dx, dy }) {
  const out = new Uint8Array(mask.length);
  for (let y = 0; y < height; y++) {
    if (y + dy < 0 || y + dy >= height) continue;
    for (let x = 0; x < width; x++) {
      if (x + dx >= 0 && x + dx < width) out[y * width + x] = mask[(y + dy) * width + x + dx];
    }
  }
  return out;
}

function subtract(mask, background) {
  return mask.map((v, i) => v && !background[i] ? 1 : 0);
}

function prepare(keyImage, studentImage, options = {}) {
  const { width, height } = dimensions(keyImage);
  const key = masks(keyImage, width, height);
  let printed = key.print;
  let keyInk = key.red;
  if (options.templateImage) {
    const template = masks(options.templateImage, width, height).ink;
    const shift = bestShift(template, key.ink, width, height);
    // Bring the template into key coordinates before subtracting it from both crops.
    printed = align(template, width, height, { dx: -shift.dx, dy: -shift.dy });
    keyInk = subtract(key.ink, dilate(printed, width, height));
  }
  if (!studentImage) return { width, height, keyInk, printed };
  const student = masks(studentImage, width, height).ink;
  const shift = bestShift(printed, student, width, height);
  const studentInk = subtract(align(student, width, height, shift), dilate(printed, width, height));
  return { width, height, keyInk, studentInk, printed, shift };
}

// Zhang-Suen thinning, iterating only foreground pixels rather than the whole crop.
function skeletonize(mask, width, height) {
  const out = mask.slice();
  let active = points(out).filter(p => p % width > 0 && p % width < width - 1 && p >= width && p < out.length - width);
  let changed = true;
  while (changed) {
    changed = false;
    for (let pass = 0; pass < 2; pass++) {
      const remove = [];
      for (const p of active) {
        if (!out[p]) continue;
        const a = out[p - width], b = out[p - width + 1], c = out[p + 1], d = out[p + width + 1];
        const e = out[p + width], f = out[p + width - 1], g = out[p - 1], h = out[p - width - 1];
        const count = a + b + c + d + e + f + g + h;
        if (count < 2 || count > 6) continue;
        const transitions = (!a && b) + (!b && c) + (!c && d) + (!d && e)
          + (!e && f) + (!f && g) + (!g && h) + (!h && a);
        if (transitions !== 1) continue;
        if (pass === 0 ? a * c * e || c * e * g : a * c * g || a * e * g) continue;
        remove.push(p);
      }
      if (remove.length) changed = true;
      for (const p of remove) out[p] = 0;
    }
    if (changed) active = active.filter(p => out[p]);
  }
  return out;
}

function neighbors(mask, p, width, height) {
  const result = [];
  const x = p % width;
  const y = Math.floor(p / width);
  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      if ((!dx && !dy) || x + dx < 0 || x + dx >= width || y + dy < 0 || y + dy >= height) continue;
      // Do not count a diagonal shortcut across a connected right-angle corner.
      if (dx && dy && (mask[p + dx] || mask[p + dy * width])) continue;
      if (mask[p + dy * width + dx]) result.push(p + dy * width + dx);
    }
  }
  return result;
}

function endpointNodes(skeleton, width, height) {
  const ends = points(skeleton).filter(p => neighbors(skeleton, p, width, height).length === 1);
  if (!ends.length) return { leftNodes: [], rightNodes: [] };
  const minX = Math.min(...ends.map(p => p % width));
  const maxX = Math.max(...ends.map(p => p % width));
  const middle = (minX + maxX) / 2;
  const make = (list, side) => {
    const sorted = list.sort((a, b) => Math.floor(a / width) - Math.floor(b / width));
    const groups = [];
    const tolerance = Math.max(3, Math.min(width, height) * 0.025);
    for (const p of sorted) {
      const x = p % width;
      const y = Math.floor(p / width);
      const previous = groups.at(-1);
      if (previous && Math.hypot(x - previous.x, y - previous.y) < tolerance) {
        previous.x = side === 'L' ? Math.min(previous.x, x) : Math.max(previous.x, x);
        previous.y = (previous.y + y) / 2;
      } else groups.push({ x, y });
    }
    return groups.map((p, i) => ({ id: `${side}${i + 1}`, x: p.x / width, y: p.y / height }));
  };
  return {
    leftNodes: make(ends.filter(p => p % width < middle), 'L'),
    rightNodes: make(ends.filter(p => p % width >= middle), 'R'),
  };
}

function suppliedNodes(endpoints) {
  const make = (list, prefix) => list.slice().sort((a, b) => a.y - b.y)
    .map((p, i) => ({ id: `${prefix}${i + 1}`, x: p.x, y: p.y }));
  if (!Array.isArray(endpoints.left) || !Array.isArray(endpoints.right)
      || [...endpoints.left, ...endpoints.right].some(p => !Number.isFinite(p.x) || !Number.isFinite(p.y)
        || p.x < 0 || p.x > 1 || p.y < 0 || p.y > 1)) {
    throw new TypeError('Endpoint zones must contain normalized x/y coordinates');
  }
  return { leftNodes: make(endpoints.left, 'L'), rightNodes: make(endpoints.right, 'R') };
}

function buildGraph(skeleton, width, height, leftNodes, rightNodes, options) {
  const radius = Math.max(3, (options.endpointRadius ?? 0.03) * Math.min(width, height));
  const zones = [...leftNodes, ...rightNodes].map(n => ({ ...n, px: n.x * width, py: n.y * height }));
  const mask = skeleton.slice();
  const nearest = (p, extra = 0) => {
    const x = p % width;
    const y = Math.floor(p / width);
    return zones.find(z => Math.hypot(x - z.px, y - z.py) <= radius + extra);
  };
  for (const p of points(mask)) if (nearest(p)) mask[p] = 0;
  const pixels = points(mask);
  const adjacency = new Map(pixels.map(p => [p, neighbors(mask, p, width, height)]));
  const regionMask = new Uint8Array(mask.length);
  // Thinning an X can produce two Y junctions joined by a short horizontal segment.
  // Keep both in one decision region so the incoming tangent survives the crossing.
  let frontier = pixels.filter(p => adjacency.get(p).length > 2);
  for (const p of frontier) regionMask[p] = 1;
  const junctionReach = Math.max(4, Math.round(Math.min(width, height) * 0.035));
  for (let step = 0; step < junctionReach; step++) {
    const next = [];
    for (const p of frontier) {
      for (const q of adjacency.get(p)) if (!regionMask[q]) {
        regionMask[q] = 1;
        next.push(q);
      }
    }
    frontier = next;
  }
  for (const p of pixels) if (adjacency.get(p).length < 2) regionMask[p] = 1;
  const regionAt = new Int32Array(mask.length).fill(-1);
  const nodes = [];
  for (const p of pixels) {
    if (!regionMask[p] || regionAt[p] !== -1) continue;
    const id = nodes.length;
    const members = [p];
    regionAt[p] = id;
    for (let i = 0; i < members.length; i++) {
      for (const q of adjacency.get(members[i])) if (regionMask[q] && regionAt[q] === -1) {
        regionAt[q] = id;
        members.push(q);
      }
    }
    const zone = members.map(q => nearest(q, 2)).find(Boolean)?.id;
    nodes.push({ id, members, zone, edges: [] });
  }
  const edges = [];
  const used = new Set();
  for (const node of nodes) {
    for (const p of node.members) {
      for (const q of adjacency.get(p)) {
        if (regionAt[q] === node.id || used.has(`${p}:${q}`)) continue;
        const path = [p, q];
        let previous = p;
        let current = q;
        while (regionAt[current] === -1) {
          const next = adjacency.get(current).find(v => v !== previous);
          if (next === undefined) break;
          previous = current;
          current = next;
          path.push(current);
        }
        const target = regionAt[current];
        if (target === -1) continue;
        used.add(`${path[0]}:${path[1]}`);
        used.add(`${path.at(-1)}:${path.at(-2)}`);
        const edge = { id: edges.length, a: node.id, b: target, path };
        edges.push(edge);
        node.edges.push(edge);
        nodes[target].edges.push(edge);
      }
    }
  }
  return { nodes, edges, width, height, radius };
}

function outward(edge, node, width) {
  const path = edge.a === node ? edge.path : edge.path.slice().reverse();
  const start = path[Math.min(1, path.length - 1)];
  const end = path[Math.min(path.length - 1, 10)];
  const dx = end % width - start % width;
  const dy = Math.floor(end / width) - Math.floor(start / width);
  const length = Math.hypot(dx, dy) || 1;
  return { x: dx / length, y: dy / length };
}

function traceZone(graph, zone, targetPrefix) {
  const targets = new Set();
  const paths = [];
  let ambiguous = false;
  let incomplete = false;
  let budget = Math.max(100, graph.edges.length * 12);
  const visit = (nodeId, incoming, visited) => {
    if (--budget < 0) { ambiguous = true; return; }
    const node = graph.nodes[nodeId];
    if (node.zone?.startsWith(targetPrefix)) {
      targets.add(node.zone);
      paths.push([...visited]);
      return;
    }
    if (incoming !== null && node.zone && node.zone !== zone) { incomplete = true; return; }
    let candidates = node.edges.filter(e => e.id !== incoming && !visited.has(e.id));
    if (!candidates.length) { incomplete = true; return; }
    if (incoming !== null && candidates.length > 1) {
      const previous = graph.edges[incoming];
      const back = outward(previous, nodeId, graph.width);
      const ranked = candidates.map(e => {
        const direction = outward(e, nodeId, graph.width);
        return { edge: e, direction, score: -back.x * direction.x - back.y * direction.y };
      }).sort((a, b) => b.score - a.score);
      if (ranked[0].score < 0.25) { ambiguous = true; return; }
      // Near-parallel branches at an X cannot reliably preserve stroke identity.
      if (node.edges.length >= 4) {
        const directions = node.edges.map(e => outward(e, nodeId, graph.width));
        for (let i = 0; i < directions.length; i++) {
          for (let j = i + 1; j < directions.length; j++) {
            if (directions[i].x * directions[j].x + directions[i].y * directions[j].y > 0.93) ambiguous = true;
          }
        }
      }
      // Compare angles, not cosine gaps: cosine compresses differences near straight ahead.
      const angle = score => Math.acos(Math.max(-1, Math.min(1, score)));
      const bestAngle = angle(ranked[0].score);
      candidates = ranked.filter(c => angle(c.score) <= bestAngle + 0.16).map(c => c.edge);
    }
    for (const edge of candidates) {
      const nextVisited = new Set(visited);
      nextVisited.add(edge.id);
      visit(edge.a === nodeId ? edge.b : edge.a, edge.id, nextVisited);
    }
  };
  const starts = graph.nodes.filter(n => n.zone === zone);
  for (const node of starts) visit(node.id, null, new Set());
  return { targets: [...targets], paths, ambiguous, incomplete, present: starts.some(n => n.edges.length) };
}

function analyze(skeleton, width, height, keyGraph, options) {
  const graph = buildGraph(skeleton, width, height, keyGraph.leftNodes, keyGraph.rightNodes, options);
  const reverse = Object.fromEntries(keyGraph.rightNodes.map(n => [n.id, traceZone(graph, n.id, 'L')]));
  const connections = {};
  const uncertain = [];
  const owners = new Map();
  for (const left of keyGraph.leftNodes) {
    const result = traceZone(graph, left.id, 'R');
    const target = result.targets.length === 1 ? result.targets[0] : null;
    connections[left.id] = target;
    if (result.ambiguous || result.targets.length > 1 || (!target && result.present)
        || (target && (!reverse[target].targets.includes(left.id) || reverse[target].ambiguous))) {
      uncertain.push(left.id);
    }
    for (const edge of new Set(result.paths.flat())) {
      if (!owners.has(edge)) owners.set(edge, new Set());
      owners.get(edge).add(left.id);
    }
  }
  // Separate strokes may end at the same dot. Reusing a traced segment for
  // different left nodes, however, loses stroke identity and needs review.
  const conflicts = new Set([...owners.values()].filter(ids => ids.size > 1).flatMap(ids => [...ids]));
  for (const left of keyGraph.leftNodes) {
    if (conflicts.has(left.id) && !uncertain.includes(left.id)) uncertain.push(left.id);
  }
  return {
    connections,
    uncertain,
    confidence: uncertain.length ? Math.max(0.25, 0.75 - uncertain.length / Math.max(1, keyGraph.leftNodes.length) * 0.3) : 0.96,
    stats: { skeletonPixels: points(skeleton).length, junctions: graph.nodes.filter(n => n.edges.length > 2).length },
  };
}

function keyFromPrepared(prepared, options) {
  const { width, height, keyInk } = prepared;
  const skeleton = skeletonize(keyInk, width, height);
  const endpoints = options.endpoints ?? options.question?.endpoints;
  const nodes = endpoints ? suppliedNodes(endpoints) : endpointNodes(skeleton, width, height);
  const traced = analyze(skeleton, width, height, nodes, options);
  const valid = nodes.leftNodes.length && nodes.rightNodes.length
    && Object.values(traced.connections).every(Boolean);
  return { ...nodes, connections: traced.connections, confidence: valid ? traced.confidence : 0.3 };
}

export function extractKeyGraph(keyImage, options = {}) {
  return keyFromPrepared(prepare(keyImage, null, options), options);
}

export function extractStudentGraph(studentImage, keyImage, keyGraph, options = {}) {
  const prepared = prepare(keyImage, studentImage, options);
  const result = analyze(skeletonize(prepared.studentInk, prepared.width, prepared.height),
    prepared.width, prepared.height, keyGraph, options);
  result.stats.shift = prepared.shift;
  return result;
}

function similarity(prepared, keySkeleton, studentSkeleton) {
  const { width, height } = prepared;
  const shift = bestShift(keySkeleton, dilate(studentSkeleton, width, height), width, height);
  const aligned = align(studentSkeleton, width, height, shift);
  const keyPoints = points(keySkeleton);
  const studentPoints = points(aligned);
  if (!keyPoints.length || !studentPoints.length) return 0;
  const radius = Math.max(2, Math.round(Math.min(width, height) * 0.012));
  const nearKey = dilate(keySkeleton, width, height, radius);
  const nearStudent = dilate(aligned, width, height, radius);
  const precision = studentPoints.reduce((sum, p) => sum + nearKey[p], 0) / studentPoints.length;
  const recall = keyPoints.reduce((sum, p) => sum + nearStudent[p], 0) / keyPoints.length;
  return precision + recall ? 2 * precision * recall / (precision + recall) : 0;
}

export function webSimilarity(keyImage, studentImage, options = {}) {
  const prepared = prepare(keyImage, studentImage, options);
  return similarity(prepared, skeletonize(prepared.keyInk, prepared.width, prepared.height),
    skeletonize(prepared.studentInk, prepared.width, prepared.height));
}

function resultFor(keyGraph, studentGraph, stage, confidence) {
  const expected = { ...keyGraph.connections };
  const connections = Object.fromEntries(keyGraph.leftNodes.map(n => [n.id, studentGraph.connections[n.id] ?? null]));
  const totalMatches = keyGraph.leftNodes.length;
  const mismatches = keyGraph.leftNodes.filter(n => !expected[n.id] || expected[n.id] !== connections[n.id])
    .map(n => ({ left: n.id, expected: expected[n.id], actual: connections[n.id] }));
  const correctMatches = totalMatches - mismatches.length;
  const review = stage === 'review';
  const credit = review ? null : correctMatches / totalMatches;
  return {
    status: review ? null : credit === 1 ? 'correct' : credit < 0.2 ? 'wrong' : 'partial',
    confidence: review ? Math.min(0.79, confidence) : confidence,
    credit,
    correctMatches,
    totalMatches,
    mismatches,
    expected,
    connections,
    uncertain: [...studentGraph.uncertain],
    leftNodes: keyGraph.leftNodes,
    rightNodes: keyGraph.rightNodes,
    stage,
    note: review ? 'Connectivity needs review' : `${correctMatches} of ${totalMatches} matches correct`,
  };
}

export function gradeMatching({ keyImage, studentImage, question = {}, options = {} }) {
  const settings = { ...options, endpoints: question.endpoints ?? options.endpoints };
  const prepared = prepare(keyImage, studentImage, settings);
  const keyGraph = keyFromPrepared(prepared, settings);
  const keySkeleton = skeletonize(prepared.keyInk, prepared.width, prepared.height);
  const studentSkeleton = skeletonize(prepared.studentInk, prepared.width, prepared.height);
  const score = similarity(prepared, keySkeleton, studentSkeleton);
  // Always trace, including near-identical crops: an attractive pixel score cannot hide a swapped pair.
  const student = analyze(studentSkeleton, prepared.width, prepared.height, keyGraph, settings);
  const ambiguous = student.uncertain.length > 0 || student.confidence < 0.8 || keyGraph.confidence < 0.8;
  if (!ambiguous) {
    const allCorrect = keyGraph.leftNodes.every(n => student.connections[n.id] === keyGraph.connections[n.id]);
    const stage = score >= Math.max(0.95, settings.similarityThreshold ?? 0.97) && allCorrect ? 'similarity' : 'graph';
    return resultFor(keyGraph, student, stage, Math.min(keyGraph.confidence, student.confidence));
  }
  const review = resultFor(keyGraph, student, 'review', Math.min(keyGraph.confidence, student.confidence));
  const fallback = getFallback('matching');
  if (!fallback || keyGraph.confidence < 0.8) return review;
  const accept = response => {
    if (!response || !Number.isFinite(response.confidence) || response.confidence < 0.8 || response.confidence > 1
        || !response.connections) return review;
    const rightIds = new Set(keyGraph.rightNodes.map(n => n.id));
    const valid = keyGraph.leftNodes.every(n => Object.hasOwn(response.connections, n.id)
      && (response.connections[n.id] === null || rightIds.has(response.connections[n.id])));
    if (!valid) return review;
    return resultFor(keyGraph, { connections: response.connections, uncertain: [] }, 'graph', response.confidence);
  };
  try {
    const response = fallback({ crop: studentImage, leftNodes: keyGraph.leftNodes, rightNodes: keyGraph.rightNodes });
    return response && typeof response.then === 'function' ? Promise.resolve(response).then(accept, () => review) : accept(response);
  } catch {
    return review;
  }
}

// Canvas APIs are used only when the browser invokes this registered wrapper.
registerGrader('matching', async ({ question, keyCrop, studentCrop, templateImage }) => {
  const read = crop => crop.getContext('2d').getImageData(0, 0, crop.width, crop.height);
  return gradeMatching({
    question,
    keyImage: read(keyCrop),
    studentImage: read(studentCrop),
    options: templateImage ? { templateImage: read(templateImage) } : {},
  });
});
