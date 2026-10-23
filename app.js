import { ANSWER_TYPES, hasGrader, runGrader } from './graders.js';
import { detectRedRegions, sortReadingOrder, DEFAULT_RED_OPTIONS } from './redDetect.js';
import { detectDifferenceRegions, estimateAlignment, forwardCanvasTransform, inverseCanvasTransform, DEFAULT_ALIGNMENT_OPTIONS } from './alignment.js';
import { CELEBRATION_COLORS, celebrationForPercent, chooseStampRect, stampJitter } from './celebrations.js';
import { applyI18n, getLanguage, setLanguage, t } from './i18n.js';
import './graders/matching.js';

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const STORAGE_KEY = 'papergrader-session-v3';
const ALIGNMENT_REVIEW_THRESHOLD = DEFAULT_ALIGNMENT_OPTIONS.reviewThreshold;
const PAPER_MM = { A4: [210, 297], B5: [182, 257], B4: [257, 364], A3: [297, 420], LETTER: [215.9, 279.4] };
const TYPE_ICONS = { written: 'Aa', number: '12', circle: '○', matching: '↔', checkbox: '☑', short: '✎' };
const detectionCache = new WeakMap();
const keyCropCache = new WeakMap();
const celebrationDensityCache = new WeakMap();
const isProposal = (question) => question.origin === 'auto' && !question.confirmed;

const state = {
  blankPage: null,
  keyPage: null,
  alignedKeyPage: null,
  setupFiles: { blank: null, key: null },
  setupAlignment: null,
  allPages: [],
  files: [],
  studentFingerprint: null,
  restoredSession: null,
  questions: [],
  nameBox: null,
  scoreBox: null,
  selectedAreas: new Set(),
  grades: {},
  names: [],
  fingerprint: null,
  activeQuestion: 0,
  selectedStudent: 0,
  selectedArea: null,
  interaction: null,
  tool: 'question',
  filter: 'all',
  pdfjs: null,
  lastDetection: null,
  celebrationImage: null,
  celebrationImageName: '',
};

const studentPages = () => state.allPages;
const setupPage = () => state.alignedKeyPage || state.keyPage;
const templatePage = () => state.blankPage;

function currentSettings() {
  return {
    offsetX: $('#offsetX').value,
    offsetY: $('#offsetY').value,
    paperSize: $('#paperSize').value,
    reverseOrder: $('#reverseOrder').checked,
    rotate180: $('#rotate180').checked,
    celebrationEnabled: $('#celebrationEnabled').checked,
    celebrationColor: $('#celebrationColor').value,
  };
}

function applySettings(settings = {}) {
  if (settings.offsetX !== undefined) $('#offsetX').value = settings.offsetX;
  if (settings.offsetY !== undefined) $('#offsetY').value = settings.offsetY;
  if (settings.paperSize && PAPER_MM[settings.paperSize]) $('#paperSize').value = settings.paperSize;
  if (settings.reverseOrder !== undefined) $('#reverseOrder').checked = Boolean(settings.reverseOrder);
  if (settings.rotate180 !== undefined) $('#rotate180').checked = Boolean(settings.rotate180);
  if (settings.celebrationEnabled !== undefined) $('#celebrationEnabled').checked = Boolean(settings.celebrationEnabled);
  if (settings.celebrationColor && CELEBRATION_COLORS[settings.celebrationColor])
    $('#celebrationColor').value = settings.celebrationColor;
}

function getSavedSession() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY));
  } catch (_) {
    return null;
  }
}

function fileIdentity(file) {
  return file ? [file.name, file.size, file.lastModified || 0] : null;
}

function setupFingerprint() {
  return JSON.stringify({
    blank: fileIdentity(state.setupFiles.blank),
    key: fileIdentity(state.setupFiles.key),
  });
}

function makeStudentFingerprint() {
  return JSON.stringify({
    files: state.files.map(fileIdentity),
    pages: state.allPages.length,
  });
}

function saveSession() {
  if (!state.fingerprint) return;
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        setupFingerprint: state.fingerprint,
        studentFingerprint: state.studentFingerprint,
        pageCount: studentPages().length,
        questions: state.questions,
        nameBox: state.nameBox,
        scoreBox: state.scoreBox,
        grades: state.grades,
        names: state.names,
        alignmentAccepted: studentPages().map((page) => Boolean(page.alignmentAccepted)),
        settings: currentSettings(),
      }),
    );
    renderSavedBanner();
  } catch (_) {}
}

function restoreSetupSession(fingerprint) {
  const saved = getSavedSession();
  state.restoredSession = saved;
  if (!saved || saved.setupFingerprint !== fingerprint) return false;
  state.questions = Array.isArray(saved.questions) ? saved.questions : [];
  state.nameBox = saved.nameBox || null;
  state.scoreBox = saved.scoreBox || null;
  state.questions.forEach((question) => {
    if (!question.origin) question.origin = 'manual';
    if (question.confirmed === undefined) question.confirmed = true;
  });
  applySettings(saved.settings);
  return true;
}

function restoreStudentSession() {
  const saved = state.restoredSession || getSavedSession();
  if (!saved || !state.studentFingerprint || saved.studentFingerprint !== state.studentFingerprint) {
    state.grades = {};
    state.names = studentPages().map((_, index) => t('studentDefault', { number: index + 1 }));
    return false;
  }
  state.grades = saved.grades && typeof saved.grades === 'object' ? saved.grades : {};
  state.names = studentPages().map(
    (_, index) => saved.names?.[index] || t('studentDefault', { number: index + 1 }),
  );
  studentPages().forEach((page, index) => {
    page.alignmentAccepted = Boolean(saved.alignmentAccepted?.[index]);
  });
  return true;
}

function renderSavedBanner() {
  const banner = $('#savedSessionBanner');
  const saved = getSavedSession();
  if (!saved?.setupFingerprint) {
    banner.classList.add('hidden');
    return;
  }
  banner.textContent = t('savedSession', { count: saved.pageCount || 0 });
  banner.classList.remove('hidden');
}

applySettings(getSavedSession()?.settings);
applyI18n();
renderSavedBanner();

function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove('show'), 2200);
}

function enableStep(id, enabled = true) {
  const button = $(`.step[data-step="${id}"]`);
  if (button) button.disabled = !enabled;
}

function switchStep(id) {
  if (id === 'grade' && !acceptProposals()) return;
  $$('.panel').forEach((panel) => panel.classList.toggle('active', panel.id === id));
  $$('.step').forEach((button) => button.classList.toggle('active', button.dataset.step === id));
  if (id === 'areas') {
    renderQuestionList();
    renderSetupCanvas();
  }
  if (id === 'students') renderStudentThumbs();
  if (id === 'grade') {
    initGradeData();
    renderGradeView();
  }
  if (id === 'results') renderResults();
  if (id === 'print') updateAspectRatioWarning();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

$$('.step').forEach((button) =>
  button.addEventListener('click', () => {
    if (!button.disabled) switchStep(button.dataset.step);
  }),
);

$('#languageToggle').addEventListener('click', () => {
  setLanguage(getLanguage() === 'ja' ? 'en' : 'ja');
  applyI18n();
  renderSavedBanner();
  renderSetupThumbs();
  renderStudentThumbs();
  renderQuestionList();
  renderSetupCanvas();
  updateToolButtons();
  if ($('#grade').classList.contains('active')) renderGradeView();
  if ($('#results').classList.contains('active')) renderResults();
  if ($('#print').classList.contains('active')) updateAspectRatioWarning();
});

async function ensurePdfJs() {
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
  throw new Error(`${t('pdfLoadFailed')} ${lastError?.message || ''}`);
}

function resetDerivedForSetupChange() {
  state.alignedKeyPage = null;
  state.setupAlignment = null;
  state.questions = [];
  state.nameBox = null;
  state.scoreBox = null;
  state.selectedAreas.clear();
  state.grades = {};
  state.names = [];
  state.allPages = [];
  state.files = [];
  state.studentFingerprint = null;
  state.restoredSession = null;
  state.fingerprint = null;
  state.lastDetection = null;
  ['areas', 'students', 'grade', 'results', 'print'].forEach((id) => enableStep(id, false));
  $('#continueToAreas').disabled = true;
  $('#continueToStudents').disabled = true;
  $('#continueToGrade').disabled = true;
  $('#setupPreviewWrap').classList.add('hidden');
  $('#studentPreviewWrap').classList.add('hidden');
}

async function loadPdfPages(file, statusElement) {
  const pdfjs = await ensurePdfJs();
  const pdf = await pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) }).promise;
  const pages = [];
  for (let number = 1; number <= pdf.numPages; number++) {
    if (statusElement) statusElement.textContent = t('renderingPdf', { page: number, total: pdf.numPages });
    const page = await pdf.getPage(number);
    const base = page.getViewport({ scale: 1 });
    const scale = Math.min(2.2, Math.max(1.15, 1900 / Math.max(base.width, base.height)));
    const viewport = page.getViewport({ scale });
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(viewport.width);
    canvas.height = Math.round(viewport.height);
    const ctx = canvas.getContext('2d', { alpha: false });
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    await page.render({ canvasContext: ctx, viewport }).promise;
    pages.push({ canvas, width: canvas.width, height: canvas.height, source: file.name + ' · page ' + number });
  }
  return pages;
}

async function loadImagePage(file) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 1900 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext('2d', { alpha: false });
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return { canvas, width: canvas.width, height: canvas.height, source: file.name };
}

async function loadFiles(files, statusElement) {
  const pages = [];
  for (const file of files) {
    if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf'))
      pages.push(...await loadPdfPages(file, statusElement));
    else if (file.type.startsWith('image/'))
      pages.push(await loadImagePage(file));
  }
  return pages;
}

function imageDataForAlignment(canvas, maxWidth = 850) {
  const width = Math.min(maxWidth, canvas.width);
  const height = Math.max(1, Math.round(canvas.height * width / canvas.width));
  const work = document.createElement('canvas');
  work.width = width;
  work.height = height;
  const ctx = work.getContext('2d', { alpha: false, willReadFrequently: true });
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(canvas, 0, 0, width, height);
  return ctx.getImageData(0, 0, width, height);
}

function alignPageToTemplate(page) {
  const reference = templatePage();
  if (!reference || !page) return null;
  const alignment = estimateAlignment(
    imageDataForAlignment(reference.canvas),
    imageDataForAlignment(page.canvas),
  );
  const normalized = document.createElement('canvas');
  normalized.width = reference.width;
  normalized.height = reference.height;
  const normalizedCtx = normalized.getContext('2d', { alpha: false });
  normalizedCtx.fillStyle = '#fff';
  normalizedCtx.fillRect(0, 0, normalized.width, normalized.height);
  normalizedCtx.drawImage(page.canvas, 0, 0, normalized.width, normalized.height);

  const canvas = document.createElement('canvas');
  canvas.width = reference.width;
  canvas.height = reference.height;
  const ctx = canvas.getContext('2d', { alpha: false });
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const m = inverseCanvasTransform(alignment, canvas.width, canvas.height);
  ctx.setTransform(m.a, m.b, m.c, m.d, m.e, m.f);
  ctx.drawImage(normalized, 0, 0);
  ctx.setTransform(1, 0, 0, 1, 0, 0);

  return {
    canvas,
    width: canvas.width,
    height: canvas.height,
    source: page.source,
    rawCanvas: page.canvas,
    alignment,
    alignmentAccepted: false,
  };
}

function alignmentPercent(page) {
  return Math.round((page?.alignment?.confidence || 0) * 100);
}

function alignmentTrusted(page) {
  return Boolean(page?.alignmentAccepted || (page?.alignment?.confidence ?? 0) >= ALIGNMENT_REVIEW_THRESHOLD);
}

async function loadSetupRole(role, file) {
  const status = $('#' + role + 'Status');
  status.textContent = t('loading');
  try {
    const pages = await loadFiles([file], status);
    if (!pages.length) throw new Error(t('noReadable'));
    resetDerivedForSetupChange();
    state.setupFiles[role] = file;
    state[role === 'blank' ? 'blankPage' : 'keyPage'] = pages[0];
    if (pages.length > 1) toast(t('usingFirstPage'));
    status.textContent = pages[0].source;
    await prepareSetup();
  } catch (error) {
    console.error(error);
    status.textContent = error.message || t('loadFailed');
  }
}

async function prepareSetup() {
  if (!state.blankPage || !state.keyPage) return;
  $('#setupPreviewWrap').classList.remove('hidden');
  $('#setupStatus').textContent = t('aligningKey');
  await new Promise((resolve) => requestAnimationFrame(resolve));
  state.alignedKeyPage = alignPageToTemplate(state.keyPage);
  state.setupAlignment = state.alignedKeyPage.alignment;
  state.fingerprint = setupFingerprint();
  const restored = restoreSetupSession(state.fingerprint);
  $('#setupStatus').textContent = t('setupReady');
  const percent = alignmentPercent(state.alignedKeyPage);
  $('#alignmentStatus').textContent = t(
    alignmentTrusted(state.alignedKeyPage) ? 'alignmentGood' : 'alignmentLow',
    { percent },
  );
  renderSetupThumbs();
  enableStep('areas');
  $('#continueToAreas').disabled = false;
  if (!restored && !state.questions.length) detectDifferenceAnswers();
  else {
    renderDetectionStatus();
    toast(t('restored'));
  }
  updateSetupReady();
}

$('#blankInput').addEventListener('change', (event) => {
  const file = event.target.files?.[0];
  if (file) loadSetupRole('blank', file);
});

$('#keyInput').addEventListener('change', (event) => {
  const file = event.target.files?.[0];
  if (file) loadSetupRole('key', file);
});

function thumbCanvas(page) {
  const canvas = document.createElement('canvas');
  canvas.width = 180;
  canvas.height = Math.round(180 * page.height / page.width);
  canvas.getContext('2d').drawImage(page.canvas, 0, 0, canvas.width, canvas.height);
  return canvas;
}

function appendThumb(wrap, page, labelText, badgeText, className = '') {
  const item = document.createElement('div');
  item.className = 'thumb ' + className;
  item.append(thumbCanvas(page));
  const label = document.createElement('div');
  label.className = 'thumb-label';
  label.textContent = labelText;
  item.append(label);
  if (badgeText) {
    const badge = document.createElement('span');
    badge.className = 'thumb-badge';
    badge.textContent = badgeText;
    item.append(badge);
  }
  wrap.append(item);
  return item;
}

function renderSetupThumbs() {
  const wrap = $('#setupThumbs');
  if (!wrap) return;
  wrap.innerHTML = '';
  if (state.blankPage) appendThumb(wrap, state.blankPage, t('blankTest'), t('blankBadge'));
  if (state.keyPage) appendThumb(wrap, state.keyPage, t('answerKey'), t('keyBadge'), 'key');
  if (state.alignedKeyPage)
    appendThumb(wrap, state.alignedKeyPage, t('alignedKeyBadge'), alignmentPercent(state.alignedKeyPage) + '%', 'key');
  renderDetectionStatus();
}

function getDetectionCache(page) {
  let entry = detectionCache.get(page);
  if (!entry) {
    entry = {};
    detectionCache.set(page, entry);
  }
  return entry;
}

function applyDetectedRegions(result, detector) {
  state.lastDetection = { detector, result };
  const removed = state.questions.filter(isProposal);
  const kept = state.questions.filter((question) => !isProposal(question));
  removed.forEach((question) => {
    Object.values(state.grades).forEach((grades) => delete grades[question.id]);
  });
  const overlap = (a, b) => {
    const intersection = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x))
      * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
    return Math.max(
      intersection / Math.max(1e-8, a.w * a.h + b.w * b.h - intersection),
      intersection / Math.max(1e-8, b.w * b.h) - 0.2,
    );
  };
  const lastNumber = Math.max(
    kept.length,
    ...kept.map((q) => Number(/^Q(\d+)$/.exec(q.label || '')?.[1]) || 0),
  );
  const proposals = sortReadingOrder(result.regions)
    .filter((region) => !kept.some((q) => overlap(q, region) > 0.3))
    .map((region, index) => ({
      id: crypto.randomUUID ? crypto.randomUUID() : Date.now() + '-auto-' + index,
      label: 'Q' + (lastNumber + index + 1),
      type: region.kind === 'matching' ? 'matching' : 'written',
      points: 1,
      expected: '',
      x: region.x,
      y: region.y,
      w: region.w,
      h: region.h,
      origin: 'auto',
      detector,
      confirmed: false,
      detectConfidence: region.confidence,
      uncertain: region.uncertain,
    }));
  state.questions = [...kept, ...proposals];
  selectArea(null);
  refreshAreas();
  renderDetectionStatus();
}

function renderDetectionStatus() {
  const status = $('#detectionStatus');
  if (!status) return;
  const last = state.lastDetection;
  if (!last) {
    status.textContent = '';
    return;
  }
  const count = last.result.regions.length;
  const key = count
    ? (last.detector === 'difference' ? 'detectedChanges' : 'detectedRegions')
    : (last.detector === 'difference' ? 'noChangesFound' : 'noRedFound');
  status.textContent = t(key, { count });
}

function detectDifferenceAnswers(force = false) {
  const key = setupPage();
  const blank = templatePage();
  if (!key || !blank) return;
  try {
    const cache = getDetectionCache(key);
    let result = force ? null : cache.difference;
    if (!result) {
      const width = Math.min(1100, blank.width);
      const height = Math.round(blank.height * width / blank.width);
      const get = (page) => {
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d', { alpha: false, willReadFrequently: true });
        ctx.fillStyle = '#fff';
        ctx.fillRect(0, 0, width, height);
        ctx.drawImage(page.canvas, 0, 0, width, height);
        return ctx.getImageData(0, 0, width, height);
      };
      result = detectDifferenceRegions(get(blank), get(key));
      cache.difference = result;
    }
    applyDetectedRegions(result, 'difference');
    toast(t(result.regions.length ? 'detectedChanges' : 'noChangesFound', { count: result.regions.length }));
  } catch (error) {
    console.error(error);
    toast(t('detectionFailed'));
  }
}

function detectRedAnswers(force = false) {
  const page = setupPage();
  if (!page) return;
  try {
    const cache = getDetectionCache(page);
    let result = force ? null : cache.red;
    if (!result) {
      const canvas = document.createElement('canvas');
      canvas.width = Math.min(DEFAULT_RED_OPTIONS.workingWidth, page.width);
      canvas.height = Math.round(page.height * canvas.width / page.width);
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(page.canvas, 0, 0, canvas.width, canvas.height);
      result = detectRedRegions(ctx.getImageData(0, 0, canvas.width, canvas.height));
      cache.red = result;
    }
    applyDetectedRegions(result, 'red');
    toast(t(result.regions.length ? 'detectedRegions' : 'noRedFound', { count: result.regions.length }));
  } catch (error) {
    console.error(error);
    toast(t('detectionFailed'));
  }
}

$('#detectChangesScan').addEventListener('click', () => detectDifferenceAnswers(true));
$('#detectChangesAreas').addEventListener('click', () => detectDifferenceAnswers(true));
$('#detectRedScan').addEventListener('click', () => detectRedAnswers(true));
$('#detectRedAreas').addEventListener('click', () => detectRedAnswers(true));
$('#continueToAreas').addEventListener('click', () => switchStep('areas'));

function confirmProposals() {
  state.questions.forEach((question) => {
    if (isProposal(question)) question.confirmed = true;
  });
  refreshAreas();
}

function acceptProposals() {
  const count = state.questions.filter(isProposal).length;
  if (!count) return true;
  if (!confirm(t('acceptProposals', { count }))) return false;
  confirmProposals();
  return true;
}

$('#confirmAll').addEventListener('click', confirmProposals);

$('#renumberAreas').addEventListener('click', () => {
  state.questions = sortReadingOrder(state.questions);
  state.questions.forEach((question, index) => {
    question.label = 'Q' + (index + 1);
  });
  refreshAreas();
});

$('#mergeAreas').addEventListener('click', () => {
  const selected = sortReadingOrder(state.questions.filter((q) => state.selectedAreas.has(q.id)));
  if (selected.length < 2) return;
  const first = selected[0];
  const x = Math.min(...selected.map((q) => q.x));
  const y = Math.min(...selected.map((q) => q.y));
  const right = Math.max(...selected.map((q) => q.x + q.w));
  const bottom = Math.max(...selected.map((q) => q.y + q.h));
  const removed = new Set(selected.slice(1).map((q) => q.id));
  state.questions = state.questions.filter((q) => !removed.has(q.id));
  Object.values(state.grades).forEach((grades) => removed.forEach((id) => delete grades[id]));
  Object.assign(first, { x, y, w: right - x, h: bottom - y, confirmed: true });
  selectArea(first.id);
  refreshAreas();
});

async function loadStudents(files) {
  $('#studentLoadStatus').textContent = t('loading');
  const rawPages = await loadFiles(files, $('#studentLoadStatus'));
  if (!rawPages.length) throw new Error(t('noReadable'));
  state.files = files;
  state.allPages = [];
  for (let index = 0; index < rawPages.length; index++) {
    $('#studentLoadStatus').textContent = t('aligningStudent', { page: index + 1, total: rawPages.length });
    await new Promise((resolve) => requestAnimationFrame(resolve));
    state.allPages.push(alignPageToTemplate(rawPages[index]));
  }
  state.studentFingerprint = makeStudentFingerprint();
  restoreStudentSession();
  $('#studentLoadStatus').textContent = t('pagesReady', { count: state.allPages.length });
  $('#studentPreviewWrap').classList.remove('hidden');
  renderStudentThumbs();
  updateSetupReady();
  saveSession();
}

$('#studentInput').addEventListener('change', async (event) => {
  const files = [...event.target.files].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }),
  );
  if (!files.length) return;
  try {
    await loadStudents(files);
  } catch (error) {
    console.error(error);
    $('#studentLoadStatus').textContent = error.message || t('loadFailed');
  }
});

function renderStudentThumbs() {
  const wrap = $('#studentThumbs');
  if (!wrap) return;
  wrap.innerHTML = '';
  const pages = studentPages();
  if (!pages.length) return;
  let good = 0;
  pages.slice(0, 60).forEach((page, index) => {
    const trusted = alignmentTrusted(page);
    if (trusted) good++;
    const item = appendThumb(
      wrap,
      page,
      t('studentBadge', { number: index + 1 }),
      null,
      trusted ? '' : 'alignment-review',
    );
    const meta = document.createElement('div');
    meta.className = 'alignment-meta';
    const score = document.createElement('span');
    score.className = 'alignment-score ' + (trusted ? 'good' : 'review');
    score.textContent = alignmentPercent(page) + '%';
    meta.append(score);
    if (!trusted) {
      const review = document.createElement('button');
      review.className = 'ghost';
      review.textContent = t('reviewAlignment');
      review.onclick = () => openAlignmentReview(index);
      meta.append(review);
    }
    item.append(meta);
  });
  $('#studentPageCountText').textContent = t('pagesReady', { count: pages.length });
  $('#studentAlignmentSummary').textContent = t('alignmentSummary', {
    good,
    total: pages.length,
    review: pages.length - good,
  });
}

let alignmentReviewIndex = null;

function drawAlignmentOverlay() {
  if (alignmentReviewIndex == null) return;
  const page = studentPages()[alignmentReviewIndex];
  const blank = templatePage();
  if (!page || !blank) return;
  const canvas = $('#alignmentOverlayCanvas');
  const maxW = 820;
  canvas.width = Math.min(maxW, blank.width);
  canvas.height = Math.round(blank.height * canvas.width / blank.width);
  const ctx = canvas.getContext('2d', { alpha: false });
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.globalAlpha = 1;
  ctx.drawImage(blank.canvas, 0, 0, canvas.width, canvas.height);
  ctx.globalAlpha = Number($('#alignmentOpacity').value) || 0.5;
  ctx.drawImage(page.canvas, 0, 0, canvas.width, canvas.height);
  ctx.globalAlpha = 1;
}

function openAlignmentReview(index) {
  alignmentReviewIndex = index;
  const page = studentPages()[index];
  $('#alignmentDialogStatus').textContent = t(
    alignmentTrusted(page) ? 'alignmentGood' : 'alignmentLow',
    { percent: alignmentPercent(page) },
  );
  drawAlignmentOverlay();
  $('#alignmentDialog').showModal();
}

$('#alignmentOpacity').addEventListener('input', drawAlignmentOverlay);
$('#closeAlignmentDialog').addEventListener('click', () => $('#alignmentDialog').close());
$('#acceptAlignment').addEventListener('click', () => {
  const page = studentPages()[alignmentReviewIndex];
  if (page) page.alignmentAccepted = true;
  $('#alignmentDialog').close();
  renderStudentThumbs();
  saveSession();
});

function renderSetupCanvas(tempRect = null) {
  const page = setupPage();
  if (!page) return;
  const canvas = $('#setupCanvas');
  canvas.width = page.width;
  canvas.height = page.height;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(page.canvas, 0, 0);
  state.questions.forEach((question, index) => drawArea(ctx, question, index, false));
  if (state.nameBox) drawArea(ctx, state.nameBox, 0, true);
  if (state.scoreBox) drawArea(ctx, state.scoreBox, 0, 'score');
  if (tempRect) drawArea(ctx, tempRect, state.questions.length, tempRect.kind === 'score' ? 'score' : tempRect.kind === 'name', true);
}

function drawArea(ctx, area, index, isName = false, temporary = false) {
  const canvas = $('#setupCanvas');
  const x = area.x * canvas.width,
    y = area.y * canvas.height,
    w = area.w * canvas.width,
    h = area.h * canvas.height;
  const areaKey = isName === 'score' ? 'score' : isName ? 'name' : area.id;
  const selected = !temporary && (state.selectedArea === areaKey || state.selectedAreas.has(areaKey));
  const proposed = !isName && isProposal(area);
  const accent = isName || (proposed && area.uncertain) ? '#b7791f' : '#c8322b';
  ctx.save();
  ctx.fillStyle = isName ? 'rgba(183,121,31,.08)' : 'rgba(200,50,43,.08)';
  ctx.strokeStyle = accent;
  ctx.lineWidth = Math.max(selected ? 5 : 3, canvas.width * 0.002);
  if (isName || temporary || proposed) ctx.setLineDash([12, 8]);
  ctx.fillRect(x, y, w, h);
  ctx.strokeRect(x, y, w, h);
  // Label sits as a tag just above the box so it never covers the printed test.
  const fs = Math.max(16, canvas.width * 0.014);
  const label = isName === 'score' ? t('scoreLabel') : isName ? t('nameArea') : `${area.label || `Q${index + 1}`}${proposed && area.uncertain ? ' ?' : ''}`;
  ctx.setLineDash([]);
  ctx.font = `700 ${fs}px system-ui`;
  const tagW = ctx.measureText(label).width + 12,
    tagH = fs + 8;
  const tagY = y - tagH >= 0 ? y - tagH : y;
  ctx.fillStyle = accent;
  ctx.fillRect(x, tagY, tagW, tagH);
  ctx.fillStyle = '#fffdf8';
  ctx.fillText(label, x + 6, tagY + fs + 1);
  if (selected) drawHandles(ctx, x, y, w, h, canvas.width);
  ctx.restore();
}

function drawHandles(ctx, x, y, w, h, width) {
  const size = Math.max(12, width * 0.009);
  ctx.setLineDash([]);
  ctx.fillStyle = '#fffdf8';
  ctx.strokeStyle = '#c8322b';
  [
    [x, y],
    [x + w, y],
    [x, y + h],
    [x + w, y + h],
  ].forEach(([hx, hy]) => {
    ctx.fillRect(hx - size / 2, hy - size / 2, size, size);
    ctx.strokeRect(hx - size / 2, hy - size / 2, size, size);
  });
}

function eventPoint(event, canvas) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) * canvas.width) / rect.width,
    y: ((event.clientY - rect.top) * canvas.height) / rect.height,
  };
}

function areaAt(point) {
  const canvas = $('#setupCanvas');
  const normalized = { x: point.x / canvas.width, y: point.y / canvas.height };
  const areas = [
    ...state.questions.map((area) => ({ area, key: area.id })),
    ...(state.nameBox ? [{ area: state.nameBox, key: 'name' }] : []),
    ...(state.scoreBox ? [{ area: state.scoreBox, key: 'score' }] : []),
  ].reverse();
  for (const entry of areas) {
    const a = entry.area,
      threshold = 0.018;
    const corners = {
      nw: [a.x, a.y],
      ne: [a.x + a.w, a.y],
      sw: [a.x, a.y + a.h],
      se: [a.x + a.w, a.y + a.h],
    };
    for (const [handle, [x, y]] of Object.entries(corners))
      if (Math.abs(normalized.x - x) < threshold && Math.abs(normalized.y - y) < threshold)
        return { ...entry, handle };
    if (normalized.x >= a.x && normalized.x <= a.x + a.w && normalized.y >= a.y && normalized.y <= a.y + a.h)
      return entry;
  }
  return null;
}

const setupCanvas = $('#setupCanvas');
setupCanvas.addEventListener('pointerdown', (event) => {
  if (!setupPage()) return;
  setupCanvas.setPointerCapture(event.pointerId);
  const point = eventPoint(event, setupCanvas);
  const hit = areaAt(point);
  if (hit) {
    selectArea(hit.key, event.shiftKey);
    if (event.shiftKey) {
      renderQuestionList();
      renderSetupCanvas();
      return;
    }
    const start = { ...hit.area };
    state.interaction = {
      mode: hit.handle ? 'resize' : 'move',
      handle: hit.handle,
      area: hit.area,
      start,
      x0: point.x / setupCanvas.width,
      y0: point.y / setupCanvas.height,
    };
    renderQuestionList();
    renderSetupCanvas();
    return;
  }
  const kind = state.tool;
  state.selectedArea = null;
  state.selectedAreas.clear();
  state.interaction = { mode: 'draw', kind, x0: point.x, y0: point.y, x: point.x, y: point.y, w: 0, h: 0 };
  renderQuestionList();
});

setupCanvas.addEventListener('pointermove', (event) => {
  const interaction = state.interaction;
  if (!interaction) return;
  const point = eventPoint(event, setupCanvas);
  if (interaction.mode === 'draw') {
    interaction.x = Math.min(interaction.x0, point.x);
    interaction.y = Math.min(interaction.y0, point.y);
    interaction.w = Math.abs(point.x - interaction.x0);
    interaction.h = Math.abs(point.y - interaction.y0);
    renderSetupCanvas({
      x: interaction.x / setupCanvas.width,
      y: interaction.y / setupCanvas.height,
      w: interaction.w / setupCanvas.width,
      h: interaction.h / setupCanvas.height,
      kind: interaction.kind,
    });
    return;
  }
  const nx = point.x / setupCanvas.width,
    ny = point.y / setupCanvas.height,
    dx = nx - interaction.x0,
    dy = ny - interaction.y0,
    a = interaction.area,
    s = interaction.start,
    min = 0.01;
  if (interaction.mode === 'move') {
    a.x = Math.max(0, Math.min(1 - s.w, s.x + dx));
    a.y = Math.max(0, Math.min(1 - s.h, s.y + dy));
  } else {
    let left = s.x,
      top = s.y,
      right = s.x + s.w,
      bottom = s.y + s.h;
    if (interaction.handle.includes('w')) left = Math.max(0, Math.min(right - min, s.x + dx));
    if (interaction.handle.includes('e')) right = Math.min(1, Math.max(left + min, s.x + s.w + dx));
    if (interaction.handle.includes('n')) top = Math.max(0, Math.min(bottom - min, s.y + dy));
    if (interaction.handle.includes('s')) bottom = Math.min(1, Math.max(top + min, s.y + s.h + dy));
    Object.assign(a, { x: left, y: top, w: right - left, h: bottom - top });
  }
  if (a.id && (a.x !== s.x || a.y !== s.y || a.w !== s.w || a.h !== s.h)) a.confirmed = true;
  renderSetupCanvas();
});

setupCanvas.addEventListener('pointerup', () => {
  const interaction = state.interaction;
  if (!interaction) return;
  state.interaction = null;
  if (
    interaction.mode === 'draw' &&
    interaction.w >= setupCanvas.width * 0.015 &&
    interaction.h >= setupCanvas.height * 0.01
  ) {
    const rect = {
      x: interaction.x / setupCanvas.width,
      y: interaction.y / setupCanvas.height,
      w: interaction.w / setupCanvas.width,
      h: interaction.h / setupCanvas.height,
    };
    if (interaction.kind === 'name' || interaction.kind === 'score') {
      state[interaction.kind === 'name' ? 'nameBox' : 'scoreBox'] = rect;
      state.selectedArea = interaction.kind;
      state.tool = 'question';
      updateToolButtons();
    } else {
      const index = state.questions.length + 1;
      const question = {
        id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${index}`,
        label: `Q${index}`,
        type: 'written',
        points: 1,
        expected: '',
        origin: 'manual',
        confirmed: true,
        ...rect,
      };
      state.questions.push(question);
      state.selectedArea = question.id;
      state.selectedAreas = new Set([question.id]);
    }
  }
  renderQuestionList();
  renderSetupCanvas();
  updateSetupReady();
  saveSession();
});

setupCanvas.addEventListener('pointercancel', () => {
  state.interaction = null;
  renderSetupCanvas();
});

$('#drawQuestion').addEventListener('click', () => {
  state.tool = 'question';
  updateToolButtons();
});
$('#markName').addEventListener('click', () => {
  state.tool = 'name';
  updateToolButtons();
});
$('#markScore').addEventListener('click', () => {
  state.tool = 'score';
  updateToolButtons();
});
function updateToolButtons() {
  $('#drawQuestion').classList.toggle('active', state.tool === 'question');
  $('#markName').classList.toggle('active', state.tool === 'name');
  $('#markScore').classList.toggle('active', state.tool === 'score');
  $('#drawingHint').textContent = state.tool === 'name' ? t('drawingName') : state.tool === 'score' ? t('drawingScore') : '';
}

function renderQuestionList() {
  renderSpecialArea('name');
  renderSpecialArea('score');
  $('#confirmAll').disabled = !state.questions.some(isProposal);
  $('#mergeAreas').disabled = state.questions.filter((q) => state.selectedAreas.has(q.id)).length < 2;
  const list = $('#questionList');
  if (!state.questions.length) {
    list.className = 'question-list empty-state';
    list.textContent = t('noQuestions');
    return;
  }
  list.className = 'question-list';
  list.innerHTML = '';
  state.questions.forEach((question, index) => {
    const item = document.createElement('div');
    item.dataset.questionId = question.id;
    item.className = `question-item ${state.selectedArea === question.id || state.selectedAreas.has(question.id) ? 'selected' : ''}`;
    const status = isProposal(question) ? question.uncertain ? 'uncertainProposal' : 'proposed' : 'confirmed';
    item.innerHTML = `<div class="question-item-head"><span class="question-type-icon">${TYPE_ICONS[question.type] || 'Aa'}</span><input class="question-label" data-label aria-label="${escapeHtml(t('questionLabel'))}" value="${escapeHtml(question.label || `Q${index + 1}`)}"><button class="icon-button" data-delete>${escapeHtml(t('delete'))}</button></div><div class="question-fields"><label>${escapeHtml(t('type'))}<select data-type>${ANSWER_TYPES.map((type) => `<option value="${type}" ${question.type === type ? 'selected' : ''}>${escapeHtml(t(type))}</option>`).join('')}</select></label><label>${escapeHtml(t('points'))}<input data-points type="number" min="0.5" step="0.5" value="${question.points}"></label></div><label class="expected-field ${question.type !== 'matching' ? '' : 'hidden'}">${escapeHtml(t('expected'))}<input data-expected value="${escapeHtml(question.expected || '')}" placeholder="${escapeHtml(t('expectedPlaceholder'))}"><span class="field-hint">${escapeHtml(t('expectedHint'))}</span></label><p class="question-status ${isProposal(question) && question.uncertain ? 'uncertain' : ''}"><span data-status>${escapeHtml(t(status))}</span> · ${escapeHtml(t('ocrNotRun'))}</p><div class="question-order"><button data-up ${index === 0 ? 'disabled' : ''} aria-label="${escapeHtml(t('moveUp'))}">↑</button><button data-down ${index === state.questions.length - 1 ? 'disabled' : ''} aria-label="${escapeHtml(t('moveDown'))}">↓</button>${isProposal(question) ? `<button class="confirm-question" data-confirm>✓ ${escapeHtml(t('confirmQuestion'))}</button>` : ''}</div>`;
    const crop = questionThumbnail(question);
    if (crop) item.insertBefore(crop, item.querySelector('.question-fields'));
    item.addEventListener('pointerdown', (event) => {
      if (event.shiftKey) event.preventDefault();
    }, true);
    item.addEventListener('click', (event) => {
      if (!event.shiftKey) {
        selectArea(question.id);
        list.querySelectorAll('.question-item').forEach((el) => el.classList.toggle('selected', el === item));
        $('#mergeAreas').disabled = true;
        renderSetupCanvas();
        return;
      }
      event.preventDefault();
      event.stopImmediatePropagation();
      selectArea(question.id, true);
      renderQuestionList();
      renderSetupCanvas();
    }, true);
    item.addEventListener('focusin', () => {
      selectArea(question.id);
      list.querySelectorAll('.question-item').forEach((el) => el.classList.toggle('selected', el === item));
      $('#mergeAreas').disabled = true;
      renderSetupCanvas();
    });
    item.addEventListener('click', (event) => {
      if (event.target.matches('input,select,button')) return;
      selectArea(question.id);
      renderQuestionList();
      renderSetupCanvas();
    });
    const edited = () => {
      question.confirmed = true;
      item.querySelector('[data-status]').textContent = t('confirmed');
      item.querySelector('.question-status').classList.remove('uncertain');
      item.querySelector('[data-confirm]')?.remove();
      $('#confirmAll').disabled = !state.questions.some(isProposal);
      renderSetupCanvas();
      saveSession();
    };
    item.querySelector('[data-delete]').addEventListener('click', () => deleteQuestion(question.id));
    item.querySelector('[data-label]').addEventListener('input', (event) => {
      question.label = event.target.value;
      edited();
    });
    item.querySelector('[data-type]').addEventListener('change', (event) => {
      question.type = event.target.value;
      edited();
      renderQuestionList();
    });
    item.querySelector('[data-points]').addEventListener('input', (event) => {
      question.points = Math.max(0.5, Number(event.target.value) || 1);
      edited();
    });
    item.querySelector('[data-expected]').addEventListener('input', (event) => {
      question.expected = event.target.value;
      edited();
    });
    item.querySelector('[data-confirm]')?.addEventListener('click', edited);
    const reorder = (delta) => {
      [state.questions[index], state.questions[index + delta]] = [state.questions[index + delta], question];
      refreshAreas();
    };
    item.querySelector('[data-up]').addEventListener('click', () => reorder(-1));
    item.querySelector('[data-down]').addEventListener('click', () => reorder(1));
    list.append(item);
  });
  scrollSidebarTo(list.querySelector(`[data-question-id="${state.selectedArea}"]`));
}

// Scroll only the sticky sidebar; scrollIntoView would also scroll the window and shift the canvas under the pointer.
function scrollSidebarTo(item) {
  const sidebar = item?.closest('.question-sidebar');
  if (!sidebar) return;
  const bounds = sidebar.getBoundingClientRect(),
    rect = item.getBoundingClientRect();
  if (rect.top < bounds.top) sidebar.scrollTop += rect.top - bounds.top;
  else if (rect.bottom > bounds.bottom) sidebar.scrollTop += Math.min(rect.bottom - bounds.bottom, rect.top - bounds.top);
}

function renderSpecialArea(kind) {
  const item = $(`#${kind}AreaItem`);
  const field = kind === 'name' ? 'nameBox' : 'scoreBox';
  item.className = `name-area-item ${state[field] ? '' : 'hidden'} ${state.selectedArea === kind ? 'selected' : ''}`;
  if (!state[field]) return;
  item.innerHTML = `<div class="question-item-head"><span>${escapeHtml(t(kind === 'name' ? 'nameArea' : 'scoreArea'))}</span><button class="icon-button" data-delete-special>${escapeHtml(t('delete'))}</button></div>`;
  item.onclick = (event) => {
    if (event.target.matches('[data-delete-special]')) { state[field] = null; selectArea(null); }
    else selectArea(kind);
    refreshAreas();
  };
}

function questionThumbnail(question) {
  const page = setupPage();
  if (!page) return null;
  const geometry = [question.x, question.y, question.w, question.h].join(',');
  let cached = keyCropCache.get(question);
  if (!cached || cached.geometry !== geometry || cached.page !== page) {
    const canvas = makeCropCanvas(page.canvas, question, 240, 110);
    canvas.className = 'question-thumbnail';
    cached = { geometry, page, canvas };
    keyCropCache.set(question, cached);
  }
  return cached.canvas;
}

function selectArea(id, additive = false) {
  if (!additive) state.selectedAreas.clear();
  if (id && id !== 'name' && id !== 'score') state.selectedAreas.add(id);
  state.selectedArea = id;
  $('#nameAreaItem').classList.toggle('selected', id === 'name');
  $('#scoreAreaItem').classList.toggle('selected', id === 'score');
}

function refreshAreas() {
  renderQuestionList();
  renderSetupCanvas();
  updateSetupReady();
  saveSession();
}

function deleteQuestion(id) {
  state.questions = state.questions.filter((question) => question.id !== id);
  Object.values(state.grades).forEach((grades) => delete grades[id]);
  state.selectedAreas.delete(id);
  if (state.selectedArea === id) state.selectedArea = null;
  renderQuestionList();
  renderSetupCanvas();
  updateSetupReady();
  saveSession();
}
function escapeHtml(value = '') {
  return String(value).replace(
    /[&<>'"]/g,
    (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char],
  );
}
function updateSetupReady() {
  const setupReady = Boolean(setupPage() && templatePage());
  const areasReady = setupReady && state.questions.length > 0;
  const gradeReady = areasReady && studentPages().length > 0;
  $('#continueToAreas').disabled = !setupReady;
  $('#continueToStudents').disabled = !areasReady;
  $('#continueToGrade').disabled = !gradeReady;
  enableStep('areas', setupReady);
  enableStep('students', areasReady);
  enableStep('grade', gradeReady);
  if (!gradeReady) {
    enableStep('results', false);
    enableStep('print', false);
  }
}

$('#clearAreas').addEventListener('click', () => {
  if ((state.questions.length || state.nameBox || state.scoreBox) && !confirm(t('clearConfirm'))) return;
  state.questions = [];
  state.nameBox = null;
  state.scoreBox = null;
  state.selectedAreas.clear();
  state.grades = {};
  state.selectedArea = null;
  renderQuestionList();
  renderSetupCanvas();
  updateSetupReady();
  saveSession();
});
$('#continueToStudents').addEventListener('click', () => {
  if (!acceptProposals()) return;
  switchStep('students');
});
$('#continueToGrade').addEventListener('click', () => {
  state.activeQuestion = 0;
  state.selectedStudent = 0;
  switchStep('grade');
});

function initGradeData() {
  studentPages().forEach((_, studentIndex) => {
    if (!state.grades[studentIndex]) state.grades[studentIndex] = {};
    state.questions.forEach((question) => {
      const grade = state.grades[studentIndex][question.id];
      if (!grade) state.grades[studentIndex][question.id] = { status: null, source: 'auto', flagged: false };
      else {
        grade.source = grade.source || 'auto';
        grade.flagged = Boolean(grade.flagged);
      }
    });
  });
  saveSession();
}

function renderGradeView() {
  const question = state.questions[state.activeQuestion];
  if (!question) return;
  renderQuestionTabs();
  $('#gradeQuestionTitle').textContent = question.label || `Q${state.activeQuestion + 1}`;
  $('#gradeExpected').textContent = question.expected
    ? t('expectedAnswer', { answer: question.expected })
    : t('noExpected');
  const keyWrap = $('#keyCrop');
  keyWrap.innerHTML = '';
  if (setupPage()) keyWrap.append(makeCropCanvas(setupPage().canvas, question));
  $('#autoGrade').classList.toggle('hidden', !hasGrader(question.type));
  const visible = studentPages()
    .map((page, index) => ({ page, index, grade: state.grades[index][question.id] }))
    .filter(
      (item) =>
        state.filter === 'all' ||
        (state.filter === 'ungraded' && !item.grade.status) ||
        (state.filter === 'flagged' && item.grade.flagged),
    );
  if (visible.length && !visible.some((item) => item.index === state.selectedStudent))
    state.selectedStudent = visible[0].index;
  const grid = $('#gradeGrid');
  grid.innerHTML = '';
  renderMatchingReview(question, visible.length > 0);
  if (!visible.length) {
    grid.innerHTML = `<div class="no-cards">${escapeHtml(t('noCards'))}</div>`;
    return;
  }
  visible.forEach(({ page, index, grade }) => grid.append(makeStudentCard(page, index, question, grade)));
}

function matchingCounts(detail, connections = detail.connections || {}) {
  const expected = detail.expected || {};
  const leftIds = (detail.leftNodes || []).map((node) => node.id);
  const correct = leftIds.filter((id) => expected[id] && connections[id] === expected[id]).length;
  return { correct, total: leftIds.length };
}

function renderMatchingReview(question, hasVisibleStudent) {
  $('#matchingReview')?.remove();
  const record = state.grades[state.selectedStudent]?.[question.id];
  if (question.type !== 'matching' || !record?.detail || !hasVisibleStudent) return;
  const detail = record.detail;
  const panel = document.createElement('section');
  panel.id = 'matchingReview';
  panel.className = 'matching-review';
  const heading = document.createElement('h2');
  heading.textContent = t('matchingReview');
  const crops = document.createElement('div');
  crops.className = 'matching-review-crops';
  [[t('keyAnswer'), setupPage()], [t('matchingStudent'), studentPages()[state.selectedStudent]]]
    .forEach(([label, page]) => {
      const figure = document.createElement('figure');
      const caption = document.createElement('figcaption');
      caption.textContent = label;
      figure.append(caption, makeCropCanvas(page.canvas, question, 1100, 1100));
      crops.append(figure);
    });
  const rows = document.createElement('div');
  rows.className = 'matching-review-rows';
  const selects = new Map();
  const expected = detail.expected || {};
  const connections = detail.connections || {};
  (detail.leftNodes || []).forEach((node) => {
    const row = document.createElement('label');
    const uncertain = (detail.uncertain || []).includes(node.id);
    row.className = `matching-review-row${uncertain ? ' uncertain' : ''}`;
    const summary = document.createElement('span');
    const actual = connections[node.id];
    const correct = actual && actual === expected[node.id];
    summary.textContent = `${node.id} → ${actual || '?'} ${uncertain ? '⚠' : correct ? '✓' : '✗'}${!correct && expected[node.id] ? ` (${t('matchingExpected', { node: expected[node.id] })})` : ''}`;
    const select = document.createElement('select');
    select.setAttribute('aria-label', t('matchingConnection', { node: node.id }));
    const none = document.createElement('option');
    none.value = '';
    none.textContent = t('matchingNone');
    select.append(none);
    (detail.rightNodes || []).forEach((right) => {
      const option = document.createElement('option');
      option.value = right.id;
      option.textContent = right.id;
      select.append(option);
    });
    select.value = actual || '';
    selects.set(node.id, select);
    row.append(summary, select);
    rows.append(row);
  });
  const apply = document.createElement('button');
  apply.className = 'primary';
  apply.textContent = t('matchingApply');
  apply.disabled = !selects.size;
  apply.onclick = () => {
    const corrected = Object.fromEntries([...selects].map(([id, select]) => [id, select.value || null]));
    const { correct, total } = matchingCounts(detail, corrected);
    Object.assign(record, {
      status: correct === total ? 'correct' : correct ? 'partial' : 'wrong',
      credit: correct / total,
      source: 'teacher',
      flagged: false,
      detail: {
        ...detail,
        connections: corrected,
        uncertain: [],
        mismatches: [...selects.keys()].filter((id) => !expected[id] || corrected[id] !== expected[id])
          .map((id) => ({ left: id, expected: expected[id], actual: corrected[id] })),
      },
    });
    delete record.confidence;
    delete record.reading;
    saveSession();
    renderGradeView();
  };
  panel.append(heading, crops, rows, apply);
  $('.grade-context').after(panel);
}

function renderQuestionTabs() {
  const tabs = $('#questionTabs');
  tabs.innerHTML = '';
  state.questions.forEach((question, index) => {
    const records = studentPages().map((_, studentIndex) => state.grades[studentIndex]?.[question.id]);
    const done = records.filter((record) => record?.status).length,
      flagged = records.filter((record) => record?.flagged).length;
    const button = document.createElement('button');
    button.className = `question-tab ${index === state.activeQuestion ? 'active' : ''}`;
    button.innerHTML = `<div class="tab-name">${escapeHtml(question.label || `Q${index + 1}`)}</div><div class="tab-meta"><span>${escapeHtml(t('progress', { done, total: studentPages().length }))}</span>${flagged ? `<span class="tab-flag">${escapeHtml(t('flaggedCount', { count: flagged }))}</span>` : ''}</div>`;
    button.onclick = () => {
      state.activeQuestion = index;
      state.selectedStudent = firstUngraded(index);
      renderGradeView();
    };
    tabs.append(button);
  });
}

function makeStudentCard(page, index, question, grade) {
  const card = document.createElement('article');
  card.className = `student-card ${index === state.selectedStudent ? 'selected' : ''}`;
  card.dataset.student = index;
  const top = document.createElement('div');
  top.className = 'student-top';
  const number = document.createElement('span');
  number.className = 'student-number';
  number.textContent = `${index + 1}.`;
  if (state.nameBox) {
    const nameCrop = makeCropCanvas(page.canvas, state.nameBox, 280, 70);
    nameCrop.className = 'name-crop';
    top.append(number, nameCrop);
  } else {
    const input = document.createElement('input');
    input.className = 'student-name';
    input.value = state.names[index] || t('studentDefault', { number: index + 1 });
    input.addEventListener('input', () => {
      state.names[index] = input.value;
      saveSession();
    });
    top.append(number, input);
  }
  const chip = document.createElement('span');
  chip.className = `status-chip ${grade.flagged ? 'flagged' : grade.status || ''}`;
  chip.textContent = grade.flagged ? t('needsReview') : statusLabel(grade.status);
  top.append(chip);
  // An unresolved matching result has no trustworthy count, so only graded records show one.
  if (question.type === 'matching' && grade.detail && grade.status && !grade.flagged) {
    const credit = document.createElement('span');
    credit.className = 'matching-credit';
    credit.textContent = t('matchingCredit', matchingCounts(grade.detail));
    top.append(credit);
  }
  const crop = makeCropCanvas(page.canvas, question);
  crop.className = 'answer-crop';
  const note = document.createElement('div');
  note.className = 'auto-note';
  const buttons = document.createElement('div');
  buttons.className = 'grade-buttons';
  [
    ['correct', t('correct')],
    ['partial', t('partial')],
    ['wrong', t('wrong')],
    [null, t('clear')],
  ].forEach(([status, label]) => {
    const button = document.createElement('button');
    button.textContent = status ? label.split(' ')[0] : label;
    button.title = label;
    button.className = grade.status === status && status ? 'active' : '';
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      setGrade(index, status);
    });
    buttons.append(button);
  });
  if (grade.source === 'auto' && (grade.confidence !== undefined || grade.reading !== undefined || grade.note))
    note.innerHTML = `<span class="auto-tag">${escapeHtml(t('auto'))}</span>${escapeHtml(grade.note || grade.reading || '')}`;
  else note.innerHTML = '';
  card.append(top, crop, note, buttons);
  card.addEventListener('click', (event) => {
    if (event.target.matches('input,button')) return;
    state.selectedStudent = index;
    renderGradeView();
  });
  return card;
}

function makeCropCanvas(src, area, maxW = 700, maxH = 300) {
  const sx = Math.max(0, Math.round(area.x * src.width)),
    sy = Math.max(0, Math.round(area.y * src.height)),
    sw = Math.max(1, Math.round(area.w * src.width)),
    sh = Math.max(1, Math.round(area.h * src.height));
  const canvas = document.createElement('canvas'),
    scale = Math.min(maxW / sw, maxH / sh, 1.8);
  canvas.width = Math.max(1, Math.round(sw * scale));
  canvas.height = Math.max(1, Math.round(sh * scale));
  const ctx = canvas.getContext('2d', { alpha: false });
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(src, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
  return canvas;
}
function statusLabel(status) {
  return status === 'correct'
    ? t('correct')
    : status === 'partial'
      ? t('partial')
      : status === 'wrong'
        ? t('wrong')
        : t('ungradedLabel');
}

function setGrade(studentIndex, status, advance = false) {
  const question = state.questions[state.activeQuestion],
    record = state.grades[studentIndex][question.id];
  assignTeacherGrade(record, status);
  state.selectedStudent = studentIndex;
  saveSession();
  if (advance) advanceSelection();
  renderGradeView();
  requestAnimationFrame(() =>
    document
      .querySelector(`.student-card[data-student="${state.selectedStudent}"]`)
      ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }),
  );
}
function assignTeacherGrade(record, status) {
  Object.assign(record, { status, source: 'teacher', flagged: false });
  ['reading', 'confidence', 'credit', 'detail', 'note'].forEach((key) => delete record[key]);
}
function firstUngraded(questionIndex) {
  const question = state.questions[questionIndex];
  const found = studentPages().findIndex((_, index) => !state.grades[index]?.[question.id]?.status);
  return found < 0 ? 0 : found;
}
function advanceSelection() {
  const total = studentPages().length;
  if (state.selectedStudent < total - 1) {
    state.selectedStudent++;
    return;
  }
  if (state.activeQuestion < state.questions.length - 1) {
    state.activeQuestion++;
    state.selectedStudent = firstUngraded(state.activeQuestion);
  }
}

$('#gradeFilters').addEventListener('click', (event) => {
  const button = event.target.closest('[data-filter]');
  if (!button) return;
  state.filter = button.dataset.filter;
  $$('.filter-chip').forEach((el) => el.classList.toggle('active', el === button));
  renderGradeView();
});
$('#markRemaining').addEventListener('click', () => {
  const question = state.questions[state.activeQuestion];
  studentPages().forEach((_, index) => {
    const record = state.grades[index][question.id];
    if (!record.status && !record.flagged)
      assignTeacherGrade(record, 'correct');
  });
  saveSession();
  renderGradeView();
});
$('#autoGrade').addEventListener('click', async () => {
  const question = state.questions[state.activeQuestion];
  if (!hasGrader(question.type)) return;
  const button = $('#autoGrade');
  button.disabled = true;
  button.textContent = t('autoRunning');
  const cropSize = question.type === 'matching' ? [1100, 1100] : [];
  const keyCrop = makeCropCanvas(setupPage().canvas, question, ...cropSize);
  const templateImage = templatePage() ? makeCropCanvas(templatePage().canvas, question, ...cropSize) : null;
  try {
    for (let index = 0; index < studentPages().length; index++) {
      const record = state.grades[index][question.id];
      if (record.source === 'teacher') continue;
      const page = studentPages()[index];
      if (!alignmentTrusted(page)) {
        Object.assign(record, {
          status: null,
          source: 'auto',
          flagged: true,
          note: t('alignmentNeedsReview'),
          alignmentConfidence: page.alignment?.confidence ?? 0,
        });
        continue;
      }
      const studentCrop = makeCropCanvas(page.canvas, question, ...cropSize);
      const result = await runGrader(question.type, {
        question,
        expected: question.expected,
        keyCrop,
        studentCrop,
        templateImage,
      });
      if (record.source === 'teacher') continue;
      delete record.credit;
      delete record.detail;
      delete record.note;
      delete record.alignmentConfidence;
      if (question.type === 'matching' && result) {
        record.credit = Number.isFinite(result.credit) ? Math.max(0, Math.min(1, result.credit)) : null;
        record.detail = Object.fromEntries(
          ['connections', 'expected', 'uncertain', 'mismatches', 'leftNodes', 'rightNodes', 'stage']
            .map((key) => [key, result[key]]),
        );
      }
      if (result?.confidence < 0.8 || result?.status == null)
        Object.assign(record, {
          status: null,
          source: 'auto',
          flagged: true,
          reading: result?.reading,
          confidence: result?.confidence,
        });
      else
        Object.assign(record, {
          status: result.status,
          source: 'auto',
          flagged: false,
          reading: result.reading,
          confidence: result.confidence,
        });
    }
    saveSession();
    toast(t('autoComplete'));
  } finally {
    button.disabled = false;
    button.textContent = t('autoGrade');
    renderGradeView();
  }
});

document.addEventListener('keydown', (event) => {
  if (
    $('#areas').classList.contains('active') &&
    event.key === 'Delete' &&
    !event.target.matches('input,select,textarea')
  ) {
    if (state.selectedArea === 'name' || state.selectedArea === 'score') {
      if (state.selectedArea === 'name') state.nameBox = null;
      else state.scoreBox = null;
      state.selectedArea = null;
      state.selectedAreas.clear();
      renderQuestionList();
      renderSetupCanvas();
      saveSession();
    } else if (state.selectedArea) deleteQuestion(state.selectedArea);
    return;
  }
  if (!$('#grade').classList.contains('active') || event.target.matches('input,select,textarea')) return;
  if (event.key === '1') {
    event.preventDefault();
    setGrade(state.selectedStudent, 'correct', true);
  } else if (event.key === '2') {
    event.preventDefault();
    setGrade(state.selectedStudent, 'partial', true);
  } else if (event.key === '3') {
    event.preventDefault();
    setGrade(state.selectedStudent, 'wrong', true);
  } else if (event.key === '0') {
    event.preventDefault();
    setGrade(state.selectedStudent, null);
  } else if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
    event.preventDefault();
    const delta = event.key === 'ArrowRight' ? 1 : -1;
    state.selectedStudent = Math.max(0, Math.min(studentPages().length - 1, state.selectedStudent + delta));
    renderGradeView();
  }
});

$('#goResults').addEventListener('click', () => {
  enableStep('results');
  switchStep('results');
});
function scoreForStudent(index) {
  let score = 0,
    max = 0,
    graded = 0;
  state.questions.forEach((question) => {
    max += question.points;
    const record = state.grades[index]?.[question.id];
    const status = record?.status;
    if (status) graded++;
    if (status === 'correct') score += question.points;
    else if (status === 'partial')
      score += question.points * (Number.isFinite(record.credit) ? Math.max(0, Math.min(1, record.credit)) : 0.5);
  });
  return { score, max, graded, percent: max ? (score / max) * 100 : 0 };
}
function markSymbol(status) {
  return status === 'correct' ? '○' : status === 'partial' ? '△' : status === 'wrong' ? '×' : '—';
}

function renderResults() {
  const scores = studentPages().map((_, index) => scoreForStudent(index));
  const classAverage = scores.length
    ? scores.reduce((sum, item) => sum + item.percent, 0) / scores.length
    : 0;
  const stats = $('#resultStats');
  stats.innerHTML =
    `<div class="stat-card"><b>${formatNum(classAverage)}%</b><span>${escapeHtml(t('classAverage'))}</span></div>` +
    state.questions
      .map((question, qIndex) => {
        const correct = studentPages().filter(
          (_, index) => state.grades[index]?.[question.id]?.status === 'correct',
        ).length;
        const rate = studentPages().length ? (correct / studentPages().length) * 100 : 0;
        return `<div class="stat-card"><b>${formatNum(rate)}%</b><span>${escapeHtml(question.label || `Q${qIndex + 1}`)} ${escapeHtml(t('correctRate'))}</span></div>`;
      })
      .join('');
  const table = $('#resultsTable');
  table.innerHTML = `<thead><tr><th>${escapeHtml(t('numberShort'))}</th><th>${escapeHtml(t('name'))}</th>${state.questions.map((q, i) => `<th>${escapeHtml(q.label || `Q${i + 1}`)}</th>`).join('')}<th>${escapeHtml(t('total'))}</th><th>${escapeHtml(t('percentage'))}</th></tr></thead><tbody></tbody>`;
  const body = table.querySelector('tbody');
  studentPages().forEach((page, index) => {
    const score = scores[index],
      row = document.createElement('tr'),
      nameCell = document.createElement('td');
    nameCell.innerHTML = '<div class="result-name"></div>';
    const nameWrap = nameCell.firstChild;
    if (state.nameBox) {
      const crop = makeCropCanvas(page.canvas, state.nameBox, 280, 80);
      nameWrap.append(crop);
    }
    const input = document.createElement('input');
    input.value = state.names[index] || t('studentDefault', { number: index + 1 });
    input.addEventListener('input', () => {
      state.names[index] = input.value;
      saveSession();
    });
    nameWrap.append(input);
    row.innerHTML = `<td>${index + 1}</td>`;
    row.append(nameCell);
    state.questions.forEach((question) => {
      const cell = document.createElement('td');
      cell.className = 'mark';
      cell.textContent = markSymbol(state.grades[index]?.[question.id]?.status);
      row.append(cell);
    });
    const total = document.createElement('td');
    total.textContent = `${formatNum(score.score)} / ${formatNum(score.max)}`;
    const percent = document.createElement('td');
    percent.textContent = `${formatNum(score.percent)}%`;
    row.append(total, percent);
    body.append(row);
  });
}

$('#exportCsv').addEventListener('click', () => {
  const quote = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;
  const headers = [
    t('numberShort'),
    t('name'),
    ...state.questions.map((q, i) => q.label || `Q${i + 1}`),
    t('total'),
    t('max'),
    '%',
  ];
  const rows = studentPages().map((_, index) => {
    const score = scoreForStudent(index);
    return [
      index + 1,
      state.names[index] || t('studentDefault', { number: index + 1 }),
      ...state.questions.map((question) => markSymbol(state.grades[index]?.[question.id]?.status)),
      formatNum(score.score),
      formatNum(score.max),
      formatNum(score.percent),
    ];
  });
  const csv = '\uFEFF' + [headers, ...rows].map((row) => row.map(quote).join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = t('csvFilename');
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
});
$('#goPrint').addEventListener('click', () => {
  enableStep('print');
  switchStep('print');
});

function updateAspectRatioWarning() {
  const el = $('#aspectRatioWarning'),
    pages = studentPages();
  if (!pages.length) {
    el.classList.add('hidden');
    return;
  }
  const [paperW, paperH] = PAPER_MM[$('#paperSize').value];
  const count = pages.filter((page) => {
    let pw = paperW,
      ph = paperH;
    if (page.width > page.height !== pw > ph) [pw, ph] = [ph, pw];
    return Math.abs(page.width / page.height / (pw / ph) - 1) > 0.02;
  }).length;
  el.textContent = t('aspectWarning', { count });
  el.classList.toggle('hidden', count === 0);
}
$('#printCorrections').addEventListener('click', () => openPrintWindow(false));
$('#printCalibration').addEventListener('click', () => openPrintWindow(true));

function openPrintWindow(calibration = false) {
  const pagesForStudents = studentPages();
  if (!pagesForStudents.length || !state.questions.length) return;
  if (!calibration) {
    const count = pagesForStudents.filter((_, pi) =>
      state.questions.some((q) => !state.grades[pi]?.[q.id]?.status || state.grades[pi]?.[q.id]?.flagged),
    ).length;
    if (count && !confirm(t('ungradedConfirm', { count }))) return;
  }
  const paperKey = $('#paperSize').value;
  let [pw, ph] = PAPER_MM[paperKey];
  const landscape = pagesForStudents[0].width > pagesForStudents[0].height;
  if (landscape && ph > pw) [pw, ph] = [ph, pw];
  const offsetX = Number($('#offsetX').value) || 0,
    offsetY = Number($('#offsetY').value) || 0,
    rotate = $('#rotate180').checked,
    reverse = $('#reverseOrder').checked;
  let indices = calibration ? [0] : pagesForStudents.map((_, i) => i);
  if (reverse && !calibration) indices = indices.reverse();
  const images = indices.map((pi) => makeOverlayCanvas(pi, calibration).toDataURL('image/png'));
  const w = window.open('', '_blank');
  if (!w) {
    toast(t('popupBlocked'));
    return;
  }
  const printPages = images
    .map(
      (src) =>
        `<section class="print-page"><img src="${src}" alt="${escapeHtml(t('correctionOverlay'))}"></section>`,
    )
    .join('');
  w.document.write(
    `<!doctype html><html><head><meta charset="utf-8"><title>${calibration ? t('alignmentTitle') : t('correctionsTitle')}</title><style>@page { size: ${pw}mm ${ph}mm; margin: 0; } html,body { margin:0; padding:0; background:white; } .print-page { position:relative; width:${pw}mm; height:${ph}mm; page-break-after:always; overflow:hidden; } .print-page:last-child { page-break-after:auto; } img { position:absolute; left:${offsetX}mm; top:${offsetY}mm; width:${pw}mm; height:${ph}mm; object-fit:fill; transform:${rotate ? 'rotate(180deg)' : 'none'}; transform-origin:center center; }</style></head><body>${printPages}<script>window.onload=()=>setTimeout(()=>window.print(),250);<\/script></body></html>`,
  );
  w.document.close();
}

['offsetX', 'offsetY', 'paperSize', 'reverseOrder', 'rotate180'].forEach((id) =>
  $(`#${id}`).addEventListener('input', () => {
    saveSession();
    if (id === 'paperSize') updateAspectRatioWarning();
  }),
);
window.addEventListener('beforeunload', (event) => {
  if (!state.questions.length) return;
  event.preventDefault();
  event.returnValue = '';
});

function makeOverlayCanvas(pi, calibration = false) {
  const base = studentPages()[pi];
  const c = document.createElement('canvas');
  c.width = base.width;
  c.height = base.height;
  const ctx = c.getContext('2d');
  ctx.clearRect(0, 0, c.width, c.height);
  // Areas live in template coordinates; map them back onto the physical sheet as scanned.
  const m = forwardCanvasTransform(base.alignment, c.width, c.height);
  ctx.setTransform(m.a, m.b, m.c, m.d, m.e, m.f);
  ctx.strokeStyle = '#d00000';
  ctx.fillStyle = '#d00000';
  ctx.lineWidth = Math.max(3, c.width * 0.0025);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  state.questions.forEach((q, qi) => {
    const record = state.grades[pi]?.[q.id];
    const status = calibration ? 'correct' : record?.flagged ? null : record?.status;
    if (!status) return;
    const x = q.x * c.width,
      y = q.y * c.height,
      w = q.w * c.width,
      h = q.h * c.height;
    const size = Math.max(20, Math.min(c.width * 0.027, Math.max(28, Math.min(w, h) * 0.34)));
    const cx = Math.min(c.width - size, x + w - size * 0.65);
    const cy = Math.max(size, y + size * 0.72);
    drawMark(ctx, status, cx, cy, size);
    if (calibration) {
      ctx.save();
      ctx.font = `700 ${Math.max(14, size * 0.45)}px system-ui`;
      ctx.fillText(q.label || `Q${qi + 1}`, Math.max(2, x + 4), Math.max(16, y + Math.max(14, size * 0.45)));
      ctx.restore();
    }
  });
  const { score, max } = scoreForStudent(pi);
  const reviewed = state.questions.every((q) => {
    const record = state.grades[pi]?.[q.id];
    return record?.status && !record.flagged;
  });
  if (!calibration && reviewed) {
    ctx.save();
    const text = `${formatNum(score)}/${formatNum(max)}`;
    if (state.scoreBox) {
      const box = state.scoreBox;
      let fs = box.h * c.height * 0.75;
      ctx.font = `800 ${fs}px system-ui`;
      fs *= Math.min(1, box.w * c.width * 0.9 / Math.max(1, ctx.measureText(text).width));
      ctx.font = `800 ${fs}px system-ui`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(text, (box.x + box.w / 2) * c.width, (box.y + box.h / 2) * c.height);
    } else {
      const fs = Math.max(28, c.width * 0.032);
      ctx.font = `800 ${fs}px system-ui`;
      ctx.textAlign = 'right';
      ctx.textBaseline = 'top';
      ctx.fillText(text, c.width * 0.965, c.height * 0.025);
    }
    ctx.restore();
  } else if (calibration) {
    ctx.save();
    const fs = Math.max(22, c.width * 0.023);
    ctx.font = `800 ${fs}px system-ui`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'top';
    ctx.fillText(t('alignmentLabel'), c.width * 0.965, c.height * 0.025);
    ctx.restore();
  }
  return c;
}
function formatNum(number) {
  return Number.isInteger(number) ? String(number) : number.toFixed(1);
}
function drawMark(ctx, status, cx, cy, size) {
  ctx.save();
  ctx.lineWidth = Math.max(3, size * 0.11);
  if (status === 'correct') {
    ctx.beginPath();
    ctx.arc(cx, cy, size * 0.52, 0, Math.PI * 2);
    ctx.stroke();
  } else if (status === 'partial') {
    ctx.beginPath();
    ctx.moveTo(cx, cy - size * 0.58);
    ctx.lineTo(cx - size * 0.58, cy + size * 0.48);
    ctx.lineTo(cx + size * 0.58, cy + size * 0.48);
    ctx.closePath();
    ctx.stroke();
  } else if (status === 'wrong') {
    ctx.beginPath();
    ctx.moveTo(cx - size * 0.48, cy - size * 0.48);
    ctx.lineTo(cx + size * 0.48, cy + size * 0.48);
    ctx.moveTo(cx + size * 0.48, cy - size * 0.48);
    ctx.lineTo(cx - size * 0.48, cy + size * 0.48);
    ctx.stroke();
  }
  ctx.restore();
}

if ('serviceWorker' in navigator)
  window.addEventListener('load', async () => {
    try {
      const registration = await navigator.serviceWorker.register('./sw.js', { updateViaCache: 'none' });
      await registration.update();
    } catch (_) {}
  });
