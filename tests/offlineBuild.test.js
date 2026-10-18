import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const projectRoot = fileURLToPath(new URL('../', import.meta.url));

test('offline build compiles as a classic script and committed outputs are current', () => {
  const outputDir = mkdtempSync(join(tmpdir(), 'papergrader-offline-'));
  try {
    const result = spawnSync(process.execPath, ['tools/build-offline.mjs', outputDir], {
      cwd: projectRoot,
      encoding: 'utf8',
    });
    assert.ifError(result.error);
    assert.equal(result.status, 0, `Offline build failed:\n${result.stderr}\n${result.stdout}`);

    const script = readFileSync(join(outputDir, 'offline-app.js'), 'utf8');
    assert.doesNotThrow(() => new vm.Script(script, { filename: 'offline-app.js' }));
    assert.doesNotMatch(script, /^\s*(?:import|export)\s/m);
    assert.match(script, /^registerGrader\('matching'/m);
    assert.match(script, /\bdetectRedRegions\b/);
    assert.match(script, /\bPDF_WORKER_SOURCE\b/);
    assert.doesNotMatch(script, /navigator\.serviceWorker\.register/);
    assert.doesNotMatch(script, /\bimport\s*\(/);
    // The unchanged worker includes license URLs and inert XML namespace identifiers.
    // App/module code must contain no URL that could reintroduce a network loader.
    const withoutWorker = script.replace(/^const PDF_WORKER_SOURCE = .*;$/m, '');
    assert.doesNotMatch(withoutWorker, /https?:\/\//i);

    // Execute the DOM-free modules to verify matching registration and import resolution.
    const modulePrefix = script.slice(0, script.indexOf('// app.js\n'));
    const context = { localStorage: { getItem: () => null }, navigator: { language: 'en' } };
    vm.runInNewContext(`${modulePrefix}\nglobalThis.registered = offlineModule0.hasGrader('matching');\n})();`, context);
    assert.equal(context.registered, true);

    const html = readFileSync(join(outputDir, 'index.html'), 'utf8');
    const scripts = [...html.matchAll(/<script\b([^>]*)>/gi)].map((match) => match[1]);
    for (const src of ['./pdf.min.js', './offline-app.js']) {
      const attributes = scripts.find((value) => value.includes(`src="${src}"`));
      assert.ok(attributes, `Missing classic script ${src}`);
      assert.doesNotMatch(attributes, /\btype\s*=\s*["']module["']/i);
    }
    assert.doesNotMatch(html, /fonts\.googleapis|rel\s*=\s*["']manifest["']/i);
    assert.doesNotMatch(html, /https?:\/\//i);

    for (const filename of ['offline-app.js', 'index.html', 'styles.css']) {
      // Git may check out text as CRLF on Windows; compare canonical LF content.
      assert.equal(
        readFileSync(join(outputDir, filename), 'utf8').replace(/\r\n/g, '\n'),
        readFileSync(join(projectRoot, 'offline', filename), 'utf8').replace(/\r\n/g, '\n'),
        `${filename} is stale; run npm run build:offline`,
      );
    }
  } finally {
    rmSync(outputDir, { recursive: true, force: true });
  }
});

test('offline build fails before writing when the PDF loader anchor changes', () => {
  const fixture = mkdtempSync(join(tmpdir(), 'papergrader-offline-anchor-'));
  try {
    for (const filename of ['tools/build-offline.mjs', 'offline/offline-app.js', 'graders.js',
      'redDetect.js', 'graders/matching.js', 'i18n.js', 'app.js']) {
      const target = join(fixture, filename);
      mkdirSync(join(target, '..'), { recursive: true });
      let content = readFileSync(join(projectRoot, filename), 'utf8');
      if (filename === 'app.js') content = content.replace('async function ensurePdfJs()', 'async function changedPdfLoader()');
      writeFileSync(target, content);
    }
    const outputDir = join(fixture, 'output');
    const result = spawnSync(process.execPath, [join(fixture, 'tools/build-offline.mjs'), outputDir], { encoding: 'utf8' });
    assert.ifError(result.error);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /PDF\.js loader: expected exactly one anchor, found 0/);
    assert.equal(existsSync(outputDir), false);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});
