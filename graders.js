const graders = new Map();

export function registerGrader(type, fn) {
  if (!['written', 'number', 'circle', 'matching'].includes(type)) {
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

// Example grader registration (no grader is registered in v2 build 1):
// registerGrader('written', async ({ question, expected, keyCrop, studentCrop }) => ({
//   status: 'correct', // 'correct' | 'partial' | 'wrong' | null
//   confidence: 0.93, // 0..1
//   reading: expected,
//   note: `Compared ${question.label} with the answer key`,
// }));
