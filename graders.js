const graders = new Map();
const fallbacks = new Map();

export const ANSWER_TYPES = ['written', 'number', 'circle', 'matching', 'checkbox', 'short'];

export function registerGrader(type, fn) {
  if (!ANSWER_TYPES.includes(type)) {
    throw new TypeError(`Unknown grader type: ${type}`);
  }
  if (typeof fn !== 'function') throw new TypeError('Grader must be a function');
  graders.set(type, fn);
}

export function hasGrader(type) {
  return graders.has(type);
}

export async function runGrader(type, input) {
  const grader = graders.get(type);
  if (!grader) throw new Error(`No grader registered for type: ${type}`);
  return grader(input);
}

// Fallbacks receive only a question crop and local endpoint coordinates, never a page.
export function registerFallback(type, fn) {
  if (!ANSWER_TYPES.includes(type)) throw new TypeError(`Unknown grader type: ${type}`);
  if (typeof fn !== 'function') throw new TypeError('Fallback must be a function');
  fallbacks.set(type, fn);
}

export function hasFallback(type) {
  return fallbacks.has(type);
}

export function getFallback(type) {
  return fallbacks.get(type);
}

// Example matching result (graders register from their own modules):
// registerGrader('matching', async ({ question, expected, keyCrop, studentCrop }) => ({
//   status: 'correct', // 'correct' | 'partial' | 'wrong' | null
//   confidence: 0.93, // 0..1
//   credit: 1, // fraction correct; null when status is null
//   correctMatches: 3, totalMatches: 3,
//   mismatches: [], // [{ left: 'L1', expected: 'R3', actual: 'R2' | null }]
//   expected: { L1: 'R3', L2: 'R1', L3: 'R2' },
//   connections: { L1: 'R3', L2: 'R1', L3: 'R2' },
//   uncertain: [], // left node IDs
//   leftNodes: [{ id: 'L1', x: 0.1, y: 0.2 }], // normalized crop coordinates
//   rightNodes: [{ id: 'R1', x: 0.9, y: 0.2 }],
//   stage: 'similarity', // 'similarity' | 'graph' | 'review'
//   note: '3 of 3 matches correct',
// }));
