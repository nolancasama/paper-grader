import test from 'node:test';
import assert from 'node:assert/strict';
import { performance } from 'node:perf_hooks';
import { extractKeyGraph, extractStudentGraph, webSimilarity, gradeMatching } from '../graders/matching.js';
import { ANSWER_TYPES, registerGrader, hasGrader, runGrader, registerFallback, hasFallback, getFallback } from '../graders.js';
import { RED, BLUE, PENCIL, polyline, drawWeb, fixture, worksheet, shifted, ambiguousFixture } from './helpers/matchingSynth.js';

function assertCorrect(result, count) {
  assert.equal(result.status, 'correct', JSON.stringify(result));
  assert.equal(result.credit, 1);
  assert.equal(result.correctMatches, count);
  assert.equal(result.totalMatches, count);
  assert.ok(result.confidence >= 0.8);
  assert.deepEqual(result.mismatches, []);
  assert.deepEqual(result.uncertain, []);
}

test('registry supports checkbox and short while preserving grader inputs and validation', async () => {
  assert.deepEqual(ANSWER_TYPES, ['written', 'number', 'circle', 'matching', 'checkbox', 'short']);
  const input = { question: {}, expected: 'answer', keyCrop: {}, studentCrop: {} };
  const result = { status: 'correct', confidence: 1 };
  for (const type of ['checkbox', 'short']) {
    registerGrader(type, received => {
      assert.equal(received, input);
      return result;
    });
    assert.equal(hasGrader(type), true);
    assert.equal(await runGrader(type, input), result);
  }
  assert.throws(() => registerGrader('unknown', () => {}), TypeError);
  assert.throws(() => registerGrader('short', null), TypeError);
  await assert.rejects(runGrader('unknown', input), /No grader registered/);
});

test('fallback registry validates registration and leaves matching unregistered', () => {
  assert.equal(hasFallback('matching'), false);
  assert.equal(getFallback('matching'), undefined);
  assert.throws(() => registerFallback('unknown', () => {}), TypeError);
  assert.throws(() => registerFallback('matching', null), TypeError);
  const fallback = () => ({ connections: {}, confidence: 0.5 });
  registerFallback('short', fallback);
  assert.equal(hasFallback('short'), true);
  assert.equal(getFallback('short'), fallback);
  assert.equal(hasFallback('matching'), false);
});

test('registered matching wrapper reads canvas crops only when invoked', async () => {
  const input = fixture();
  let reads = 0;
  const canvas = image => ({
    width: image.width,
    height: image.height,
    getContext(type) {
      assert.equal(type, '2d');
      return {
        getImageData(...args) {
          reads++;
          assert.deepEqual(args, [0, 0, image.width, image.height]);
          return image;
        },
      };
    },
  });
  assert.equal(hasGrader('matching'), true);
  assertCorrect(await runGrader('matching', {
    question: input.question,
    expected: '',
    keyCrop: canvas(input.keyImage),
    studentCrop: canvas(input.studentImage),
  }), 3);
  assert.equal(reads, 2);
});

test('infers ordered normalized endpoint nodes and red key connections without DOM', () => {
  const { keyImage } = fixture([2, 0, 1]);
  const graph = extractKeyGraph(keyImage);
  assert.deepEqual(graph.connections, { L1: 'R3', L2: 'R1', L3: 'R2' });
  assert.equal(graph.leftNodes.length, 3);
  assert.equal(graph.rightNodes.length, 3);
  for (const nodes of [graph.leftNodes, graph.rightNodes]) {
    assert.ok(nodes.every(node => node.x >= 0 && node.x <= 1 && node.y >= 0 && node.y <= 1));
    assert.ok(nodes.every((node, i) => !i || node.y > nodes[i - 1].y));
  }
  assert.ok(graph.confidence >= 0.8);
});

test('identical web grades correct and returns the complete result metadata', async () => {
  const result = await gradeMatching(fixture());
  assertCorrect(result, 3);
  assert.equal(result.stage, 'similarity');
  assert.deepEqual(result.expected, { L1: 'R1', L2: 'R2', L3: 'R3' });
  assert.deepEqual(result.connections, result.expected);
  assert.equal(result.leftNodes.length, 3);
  assert.equal(result.rightNodes.length, 3);
  assert.match(result.note, /3.*3/);
});

test('different Bezier curves, thickness, and blue ink preserve topology', async () => {
  const result = await gradeMatching(fixture([0, 1, 2], undefined, {
    key: { thickness: 2, curve: -10 },
    student: { color: BLUE, thickness: 5, curve: 16 },
  }));
  assertCorrect(result, 3);
});

test('curved lines grade correctly when endpoint positions must be inferred', async () => {
  const input = fixture([0, 1, 2], undefined, {
    key: { curve: -10 },
    student: { curve: 14, thickness: 4 },
  });
  delete input.question;
  assertCorrect(await gradeMatching(input), 3);
});

test('red student ink is graded by connectivity', async () => {
  assertCorrect(await gradeMatching(fixture([0, 1, 2], undefined, { student: { color: RED } })), 3);
});

test('multiple clear crossings preserve the connections', async () => {
  assertCorrect(await gradeMatching(fixture([3, 1, 2, 0], undefined, { student: { color: BLUE } })), 4);
});

test('one wrong target of three earns two thirds credit with the mismatch', async () => {
  const result = await gradeMatching(fixture([0, 1, 2], [0, 2, 2]));
  assert.equal(result.status, 'partial', JSON.stringify(result));
  assert.equal(result.credit, 2 / 3);
  assert.equal(result.correctMatches, 2);
  assert.deepEqual(result.mismatches, [{ left: 'L2', expected: 'R2', actual: 'R3' }]);
});

test('two swapped targets of four earn one half credit', async () => {
  const result = await gradeMatching(fixture([0, 1, 2, 3], [0, 2, 1, 3]));
  assert.equal(result.status, 'partial', JSON.stringify(result));
  assert.equal(result.credit, 0.5);
  assert.equal(result.correctMatches, 2);
  assert.equal(result.mismatches.length, 2);
});

test('a redrawn double stroke to the same target is accepted', async () => {
  const input = fixture();
  drawWeb(input.student, [null, 1, null], { curve: 5, thickness: 2 });
  assertCorrect(await gradeMatching(input), 3);
});

test('accidental touching never produces a confident incorrect verdict', async () => {
  const input = fixture();
  polyline(input.studentImage, [
    { x: 150, y: input.student.left[0].y },
    { x: 150, y: input.student.left[1].y },
  ], undefined, 2);
  const result = await gradeMatching(input);
  assert.ok(result.status === 'correct' || result.status === null, JSON.stringify(result));
  if (result.status === null) assert.ok(result.confidence < 0.8);
});

test('thin faint pencil lines are detected', async () => {
  assertCorrect(await gradeMatching(fixture([0, 1, 2], undefined, {
    student: { color: PENCIL, thickness: 1.6 },
  })), 3);
});

test('a genuinely absent line is a confident null connection with partial credit', async () => {
  const input = fixture([0, 1, 2], [0, null, 2]);
  const graph = extractKeyGraph(input.keyImage, { endpoints: input.question.endpoints });
  const student = extractStudentGraph(input.studentImage, input.keyImage, graph);
  assert.equal(student.connections.L2, null);
  assert.ok(!student.uncertain.includes('L2'));
  assert.ok(student.stats && typeof student.stats === 'object');
  const result = await gradeMatching(input);
  assert.equal(result.status, 'partial', JSON.stringify(result));
  assert.equal(result.credit, 2 / 3);
  assert.deepEqual(result.mismatches, [{ left: 'L2', expected: 'R2', actual: null }]);
});

test('entirely incorrect connections receive zero credit', async () => {
  const result = await gradeMatching(fixture([0, 1], [1, 0]));
  assert.equal(result.status, 'wrong', JSON.stringify(result));
  assert.equal(result.credit, 0);
  assert.equal(result.correctMatches, 0);
  assert.equal(result.totalMatches, 2);
  assert.deepEqual(result.connections, { L1: 'R2', L2: 'R1' });
  assert.equal(result.mismatches.length, 2);
  assert.ok(result.confidence >= 0.8);
});

test('all missing lines receive proportional zero credit without uncertainty', async () => {
  const result = await gradeMatching(fixture([0, 1, 2], [null, null, null]));
  assert.equal(result.status, 'wrong', JSON.stringify(result));
  assert.equal(result.credit, 0);
  assert.equal(result.correctMatches, 0);
  assert.equal(result.totalMatches, 3);
  assert.deepEqual(result.connections, { L1: null, L2: null, L3: null });
  assert.deepEqual(result.uncertain, []);
  assert.ok(result.confidence >= 0.8);
});

test('an isolated extra stray stroke does not affect grading', async () => {
  const input = fixture();
  polyline(input.studentImage, [{ x: 110, y: 8 }, { x: 160, y: 20 }, { x: 190, y: 9 }], BLUE, 3);
  assertCorrect(await gradeMatching(input), 3);
});

test('shallow crossing in a central blob is sent to review', async () => {
  const result = await gradeMatching(ambiguousFixture());
  assert.equal(result.status, null, JSON.stringify(result));
  assert.equal(result.credit, null);
  assert.equal(result.stage, 'review');
  assert.ok(result.confidence < 0.8);
  assert.ok(result.uncertain.length > 0);
});

test('a student scan translated a few pixels still grades correctly', async () => {
  const input = fixture([2, 0, 1]);
  input.studentImage = shifted(input.studentImage, 4, -3);
  assertCorrect(await gradeMatching(input), 3);
});

test('similarity tolerates modest translation and pen thickness and penalizes swapped pairs', () => {
  const identical = fixture([0, 1, 2, 3]);
  const altered = fixture([0, 1, 2, 3], undefined, { student: { thickness: 5, curve: 3 } });
  const swapped = fixture([0, 1, 2, 3], [0, 2, 1, 3]);
  const exactScore = webSimilarity(identical.keyImage, identical.studentImage);
  const variedScore = webSimilarity(altered.keyImage, shifted(altered.studentImage, 3, 2));
  const wrongScore = webSimilarity(swapped.keyImage, swapped.studentImage);
  assert.ok(exactScore >= 0.9, `Identical similarity: ${exactScore}`);
  assert.ok(variedScore >= 0.8, `Varied similarity: ${variedScore}`);
  assert.ok(wrongScore < exactScore - 0.1, `Swapped ${wrongScore}; identical ${exactScore}`);
  for (const score of [exactScore, variedScore, wrongScore]) assert.ok(score >= 0 && score <= 1);
});

test('a separate blank template can remove printed background from both images', async () => {
  const input = fixture();
  input.options = { templateImage: worksheet().target };
  assertCorrect(await gradeMatching(input), 3);
});

test('900 by 600 crop with ten pairs grades in under 300 ms', async () => {
  const connections = Array.from({ length: 10 }, (_, i) => i);
  const input = fixture(connections, undefined, { width: 900, height: 600 });
  const start = performance.now();
  const result = await gradeMatching(input);
  const elapsed = performance.now() - start;
  assertCorrect(result, 10);
  assert.ok(elapsed < 300, `Grading took ${elapsed.toFixed(1)} ms`);
});

test('registered fallback sees only the crop and endpoints and runs only for ambiguity', async () => {
  assert.equal(hasFallback('matching'), false);
  const ambiguous = ambiguousFixture();
  let calls = 0;
  let response = { connections: { L1: 'R1', L2: 'R2' }, confidence: 0.99 };
  let reject = false;
  registerFallback('matching', async input => {
    calls++;
    assert.deepEqual(Object.keys(input).sort(), ['crop', 'leftNodes', 'rightNodes']);
    assert.equal(input.crop, ambiguous.studentImage);
    assert.equal(input.leftNodes.length, 2);
    assert.equal(input.rightNodes.length, 2);
    if (reject) throw new Error('Fallback unavailable');
    return response;
  });
  assertCorrect(await gradeMatching(fixture()), 3);
  assert.equal(calls, 0);
  assertCorrect(await gradeMatching(ambiguous), 2);
  assert.equal(calls, 1);
  for (const invalid of [
    { connections: { L1: 'R1', L2: 'R2' }, confidence: 0.7 },
    { connections: { L1: 'R99', L2: 'R2' }, confidence: 0.99 },
    { connections: { L1: 'R1' }, confidence: 0.99 },
  ]) {
    response = invalid;
    const result = await gradeMatching(ambiguous);
    assert.equal(result.status, null);
    assert.equal(result.credit, null);
    assert.ok(result.confidence < 0.8);
  }
  reject = true;
  const result = await gradeMatching(ambiguous);
  assert.equal(result.status, null);
  assert.equal(result.stage, 'review');
  assert.equal(calls, 5);
});
