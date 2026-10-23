import assert from 'node:assert/strict';
import test from 'node:test';
import { celebrationForPercent, chooseStampRect, overlapFraction, stampJitter } from '../celebrations.js';

test('celebration policy follows score bands', () => {
  assert.deepEqual(celebrationForPercent(89.9), { kind: 'none', text: '' });
  assert.deepEqual(celebrationForPercent(90), { kind: 'stamp', text: 'GOOD JOB!' });
  assert.deepEqual(celebrationForPercent(95), { kind: 'stamp', text: 'AMAZING!' });
  assert.deepEqual(celebrationForPercent(98), { kind: 'stamp', text: 'GENIUS!' });
  assert.deepEqual(celebrationForPercent(99.9), { kind: 'stamp', text: 'GENIUS!' });
  assert.deepEqual(celebrationForPercent(100), { kind: 'frame', text: '' });
});

test('stamp placement avoids blocked rectangles and prefers empty space near score', () => {
  const scoreRect = { x: 0.78, y: 0.02, w: 0.18, h: 0.07 };
  const blocked = [{ x: 0.57, y: 0.02, w: 0.2, h: 0.13 }];
  const chosen = chooseStampRect({
    scoreRect,
    blockedRects: blocked,
    density: (rect) => rect.y > 0.25 ? 0.7 : 0.01,
  });
  assert.ok(chosen);
  assert.ok(overlapFraction(chosen, blocked[0]) < 0.01, JSON.stringify(chosen));
  assert.ok(chosen.y < 0.25, JSON.stringify(chosen));
});

test('stamp placement can shrink when nearby areas are crowded', () => {
  const scoreRect = { x: 0.78, y: 0.02, w: 0.18, h: 0.07 };
  const blocked = [
    { x: 0.02, y: 0.02, w: 0.5, h: 0.18 },
    { x: 0.55, y: 0.02, w: 0.22, h: 0.18 },
  ];
  const chosen = chooseStampRect({ scoreRect, blockedRects: blocked, density: () => 0.02 });
  assert.ok(chosen);
  assert.ok(chosen.w <= 0.18);
  assert.ok(chosen.x >= 0.025 && chosen.x + chosen.w <= 0.975);
});


test('hand-stamp jitter is stable per student but varies across students', () => {
  const a = stampJitter('student-1:98');
  const aAgain = stampJitter('student-1:98');
  const b = stampJitter('student-2:98');
  assert.deepEqual(a, aAgain);
  assert.notDeepEqual(a, b);
  assert.ok(a.angleDeg >= -9 && a.angleDeg <= 9);
  assert.ok(a.scale >= 0.94 && a.scale <= 1.06);
});
