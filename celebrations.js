export const CELEBRATION_COLORS = {
  red: '#d00000',
  blue: '#1557a0',
  green: '#16753a',
  purple: '#713f91',
};

export function celebrationForPercent(percent) {
  if (!Number.isFinite(percent)) return { kind: 'none', text: '' };
  if (percent >= 99.999) return { kind: 'frame', text: '' };
  if (percent >= 98) return { kind: 'stamp', text: 'GENIUS!' };
  if (percent >= 95) return { kind: 'stamp', text: 'AMAZING!' };
  if (percent >= 90) return { kind: 'stamp', text: 'GOOD JOB!' };
  return { kind: 'none', text: '' };
}

export function overlapFraction(a, b) {
  const x = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
  const y = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
  return a.w * a.h ? (x * y) / (a.w * a.h) : 0;
}

function clampRect(rect, margin) {
  return {
    ...rect,
    x: Math.max(margin, Math.min(1 - margin - rect.w, rect.x)),
    y: Math.max(margin, Math.min(1 - margin - rect.h, rect.y)),
  };
}

function center(rect) {
  return { x: rect.x + rect.w / 2, y: rect.y + rect.h / 2 };
}

function distance(a, b) {
  const ac = center(a), bc = center(b);
  return Math.hypot(ac.x - bc.x, ac.y - bc.y);
}

export function chooseStampRect({
  scoreRect,
  blockedRects = [],
  density = () => 0,
  width = 0.18,
  height = 0.105,
  margin = 0.025,
} = {}) {
  const score = scoreRect || { x: 0.78, y: 0.02, w: 0.185, h: 0.065 };
  const candidates = [];
  const push = (x, y, scale = 1) => {
    const rect = clampRect({ x, y, w: width * scale, h: height * scale }, margin);
    if (!candidates.some((item) =>
      Math.abs(item.x - rect.x) < 0.002 && Math.abs(item.y - rect.y) < 0.002
      && Math.abs(item.w - rect.w) < 0.002 && Math.abs(item.h - rect.h) < 0.002)) {
      candidates.push(rect);
    }
  };

  push(score.x - width - 0.018, score.y - height * 0.15);
  push(score.x + score.w + 0.018, score.y - height * 0.15);
  push(score.x + score.w - width, score.y + score.h + 0.018);
  push(score.x - width * 0.45, score.y + score.h + 0.018);
  push(score.x - width - 0.018, score.y + score.h + 0.01);

  for (const scale of [1, 0.88]) {
    const w = width * scale, h = height * scale;
    for (let y = margin; y <= 1 - margin - h; y += 0.055) {
      for (let x = margin; x <= 1 - margin - w; x += 0.055) {
        const probe = { x, y, w, h };
        if (distance(probe, score) <= 0.46) candidates.push(probe);
      }
    }
  }

  let best = null;
  let bestScore = Infinity;
  for (const rect of candidates) {
    const blocked = blockedRects.reduce((sum, item) => sum + overlapFraction(rect, item), 0);
    const ink = Math.max(0, Math.min(1, Number(density(rect)) || 0));
    const near = distance(rect, score);
    const edgePenalty = rect.x < margin || rect.y < margin
      || rect.x + rect.w > 1 - margin || rect.y + rect.h > 1 - margin ? 2 : 0;
    const scoreValue = blocked * 30 + ink * 7 + near * 1.4 + edgePenalty;
    if (scoreValue < bestScore) {
      bestScore = scoreValue;
      best = { ...rect, density: ink, blocked, placementScore: scoreValue };
    }
  }
  return best;
}
