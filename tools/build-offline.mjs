import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Script } from 'node:vm';

const root = fileURLToPath(new URL('../', import.meta.url));
const read = async (name) => (await readFile(path.join(root, name), 'utf8')).replace(/\r\n/g, '\n');

function replaceOnce(source, anchor, replacement, label) {
  const matches = typeof anchor === 'string' ? source.split(anchor).length - 1 : [...source.matchAll(anchor)].length;
  if (matches !== 1) throw new Error(`${label}: expected exactly one anchor, found ${matches}`);
  return source.replace(anchor, () => replacement);
}

// Keep the bundled PDF.js version and its worker byte-for-byte: neither is downloaded.
const previousBundle = await read('offline/offline-app.js');
const workers = [...previousBundle.matchAll(/^const PDF_WORKER_SOURCE = ("(?:[^"\\\n]|\\.)*");$/gm)];
if (workers.length !== 1 || !JSON.parse(workers[0][1]).includes('WorkerMessageHandler')) {
  throw new Error('Expected one embedded PDF_WORKER_SOURCE in offline/offline-app.js');
}
const workerDeclaration = workers[0][0];

const webPdfLoader = `async function ensurePdfJs() {
  if (state.pdfjs) return state.pdfjs;
  const attempts = ['./vendor/pdf.mjs', 'https://cdn.jsdelivr.net/npm/pdfjs-dist@6.3.289/build/pdf.mjs'];
  let lastError;
  for (const url of attempts) {
    try {
      const mod = await import(url);
      mod.GlobalWorkerOptions.workerSrc = url.startsWith('.')
        ? './vendor/pdf.worker.mjs'
        : 'https://cdn.jsdelivr.net/npm/pdfjs-dist@6.3.289/build/pdf.worker.mjs';
      state.pdfjs = mod;
      return mod;
    } catch (error) {
      lastError = error;
    }
  }
  throw new Error(\`\${t('pdfLoadFailed')} \${lastError?.message || ''}\`);
}`;

// This is the original hand build's loader, including its Blob worker fallback.
const offlinePdfLoader = `async function ensurePdfJs() {
  if (state.pdfjs) return state.pdfjs;
  const mod = globalThis.pdfjsLib;
  if (!mod) throw new Error(t('pdfLoadFailed'));
  try {
    if (!globalThis.__paperGraderPdfWorkerUrl) {
      const blob = new Blob([PDF_WORKER_SOURCE], { type: 'text/javascript' });
      globalThis.__paperGraderPdfWorkerUrl = URL.createObjectURL(blob);
    }
    mod.GlobalWorkerOptions.workerSrc = globalThis.__paperGraderPdfWorkerUrl;
  } catch (_) {}
  state.pdfjs = mod;
  return mod;
}`;

const modules = [
  ['graders.js', 0],
  ['redDetect.js', 0],
  ['alignment.js', 0],
  ['celebrations.js', 0],
  ['graders/matching.js', 1],
  ['i18n.js', 0],
  ['app.js', 6],
];
const built = new Map();
const chunks = [];
for (const [name, expectedImports] of modules) {
  let source = await read(name);
  if (name === 'app.js') {
    source = replaceOnce(source, webPdfLoader, offlinePdfLoader, 'PDF.js loader');
    source = replaceOnce(source,
      "if ('serviceWorker' in navigator)\n  window.addEventListener('load', async () => {\n    try {\n      const registration = await navigator.serviceWorker.register('./sw.js', { updateViaCache: 'none' });\n      await registration.update();\n    } catch (_) {}\n  });",
      '', 'Service-worker registration');
  }
  let imports = 0;
  source = source.replace(/^import (?:\{([^}]+)\} from )?'([^']+)';\n/gm, (_, bindings, specifier) => {
    imports++;
    const dependency = path.posix.normalize(path.posix.join(path.posix.dirname(name), specifier));
    const module = built.get(dependency);
    if (!module) throw new Error(`${name}: dependency not built: ${specifier}`);
    if (!bindings) return '';
    const resolved = bindings.split(',').map((binding) => {
      const match = binding.trim().match(/^(\w+)(?:\s+as\s+(\w+))?$/);
      if (!match || !module.exports.includes(match[1])) throw new Error(`${name}: unsupported binding: ${binding}`);
      return match[2] ? `${match[1]}: ${match[2]}` : match[1];
    });
    return `const { ${resolved.join(', ')} } = ${module.id};\n`;
  });
  if (imports !== expectedImports) throw new Error(`${name}: expected ${expectedImports} imports, found ${imports}`);
  const exports = [];
  source = source.replace(/^export ((?:async )?function|const) (\w+)/gm, (_, declaration, binding) => {
    exports.push(binding);
    return `${declaration} ${binding}`;
  });
  if (name !== 'app.js' && !exports.length) throw new Error(`${name}: no export anchors found`);
  if (/^\s*(?:import|export)\b/m.test(source) || /\bimport\s*\(/.test(source)) {
    throw new Error(`${name}: unsupported module syntax remains`);
  }
  if (/https?:\/\//i.test(source) || /navigator\.serviceWorker/.test(source)) {
    throw new Error(`${name}: network URL or service-worker reference remains`);
  }
  const id = `offlineModule${built.size}`;
  // Each module has its own lexical scope; only declared exports cross the boundary.
  chunks.push(`// ${name}\nconst ${id} = (() => {\n${source.trim()}\nreturn { ${exports.join(', ')} };\n})();`);
  built.set(name, { id, exports });
}

let html = await read('index.html');
html = replaceOnce(html, '    <link rel="manifest" href="./manifest.webmanifest" />\n', '', 'Manifest link');
html = replaceOnce(html, '    <link rel="preconnect" href="https://fonts.googleapis.com" />\n', '', 'Google Fonts preconnect');
html = replaceOnce(html, '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n', '', 'Font static preconnect');
html = replaceOnce(html, /    <link\n      href="https:\/\/fonts\.googleapis\.com\/[^"\n]+"\n      rel="stylesheet"\n    \/>\n/g, '', 'Font stylesheet');
html = replaceOnce(html, '    <script type="module" src="./app.js"></script>',
  '    <script src="./pdf.min.js"></script>\n    <script src="./offline-app.js"></script>', 'App script');
const css = await read('styles.css');
if (/https?:\/\/|\bmanifest\b|type="module"/i.test(html) || /https?:\/\/|@import\b/i.test(css)) {
  throw new Error('External dependency remains in offline HTML/CSS');
}
const bundle = `// PaperGrader v2 offline build. Generated by tools/build-offline.mjs.\n(() => {\n'use strict';\n${workerDeclaration}\n\n${chunks.join('\n\n')}\n})();\n`;
new Script(bundle, { filename: 'offline-app.js' });

if (process.argv.length > 3 || process.argv[2]?.startsWith('-')) {
  throw new Error('Usage: node tools/build-offline.mjs [output-directory]');
}
const output = path.resolve(process.argv[2] ?? path.join(root, 'offline'));
await mkdir(output, { recursive: true });
for (const [name, content] of [['offline-app.js', bundle], ['index.html', html], ['styles.css', css]]) {
  await writeFile(path.join(output, name), content);
}
console.log(`Offline build written to ${output}`);
