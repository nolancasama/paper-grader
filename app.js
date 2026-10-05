const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const state = {
  pages: [],
  questions: [],
  grades: {},
  names: [],
  activeQuestion: 0,
  selectedStudent: 0,
  drawing: null,
  pdfjs: null,
};

const PAPER_MM = {
  A4: [210, 297],
  B5: [182, 257],
  B4: [257, 364],
  A3: [297, 420],
  LETTER: [215.9, 279.4],
};

function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove('show'), 2200);
}

function switchStep(id) {
  $$('.panel').forEach(p => p.classList.toggle('active', p.id === id));
  $$('.step').forEach(b => b.classList.toggle('active', b.dataset.step === id));
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

$$('.step').forEach(btn => btn.addEventListener('click', () => {
  if (!btn.disabled) switchStep(btn.dataset.step);
}));

function enableStep(id, enabled = true) {
  const btn = $(`.step[data-step="${id}"]`);
  if (btn) btn.disabled = !enabled;
}

async function ensurePdfJs() {
  if (state.pdfjs) return state.pdfjs;
  const attempts = [
    './vendor/pdf.mjs',
    'https://cdn.jsdelivr.net/npm/pdfjs-dist@6.3.289/build/pdf.mjs'
  ];
  let lastError;
  for (const url of attempts) {
    try {
      const mod = await import(url);
      const worker = url.startsWith('.')
        ? './vendor/pdf.worker.mjs'
        : 'https://cdn.jsdelivr.net/npm/pdfjs-dist@6.3.289/build/pdf.worker.mjs';
      mod.GlobalWorkerOptions.workerSrc = worker;
      state.pdfjs = mod;
      return mod;
    } catch (err) { lastError = err; }
  }
  throw new Error(`PDF support could not load. ${lastError?.message || ''}`);
}

$('#fileInput').addEventListener('change', async (e) => {
  const files = [...e.target.files];
  if (!files.length) return;
  $('#loadStatus').textContent = 'Loading scans…';
  state.pages = [];
  state.questions = [];
  state.grades = {};
  state.names = [];

  try {
    for (const file of files) {
      if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
        await loadPdf(file);
      } else if (file.type.startsWith('image/')) {
        await loadImage(file);
      }
    }
    if (!state.pages.length) throw new Error('No readable pages were found.');
    state.names = state.pages.map((_, i) => `Student ${i + 1}`);
    $('#loadStatus').textContent = `${state.pages.length} page${state.pages.length === 1 ? '' : 's'} ready.`;
    $('#pageCountText').textContent = `${state.pages.length} student page${state.pages.length === 1 ? '' : 's'} loaded.`;
    renderThumbs();
    $('#pagePreviewWrap').classList.remove('hidden');
    enableStep('setup', true);
    $('#continueToSetup').disabled = false;
  } catch (err) {
    console.error(err);
    $('#loadStatus').textContent = err.message;
    toast('Could not load the scan.');
  }
});

async function loadPdf(file) {
  const pdfjs = await ensurePdfJs();
  const data = new Uint8Array(await file.arrayBuffer());
  const pdf = await pdfjs.getDocument({ data }).promise;
  for (let n = 1; n <= pdf.numPages; n++) {
    $('#loadStatus').textContent = `Rendering PDF page ${n} of ${pdf.numPages}…`;
    const page = await pdf.getPage(n);
    const base = page.getViewport({ scale: 1 });
    const targetLongSide = 1900;
    const scale = Math.min(2.2, Math.max(1.15, targetLongSide / Math.max(base.width, base.height)));
    const viewport = page.getViewport({ scale });
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(viewport.width);
    canvas.height = Math.round(viewport.height);
    const ctx = canvas.getContext('2d', { alpha: false });
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    await page.render({ canvasContext: ctx, viewport }).promise;
    state.pages.push({ canvas, width: canvas.width, height: canvas.height, source: `${file.name} · page ${n}` });
  }
}

async function loadImage(file) {
  const bitmap = await createImageBitmap(file);
  const long = Math.max(bitmap.width, bitmap.height);
  const scale = Math.min(1, 1900 / long);
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext('2d', { alpha: false });
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  state.pages.push({ canvas, width: canvas.width, height: canvas.height, source: file.name });
}

function renderThumbs() {
  const wrap = $('#pageThumbs');
  wrap.innerHTML = '';
  state.pages.slice(0, 24).forEach((page, i) => {
    const item = document.createElement('div');
    item.className = 'thumb';
    const c = document.createElement('canvas');
    const ratio = page.height / page.width;
    c.width = 220;
    c.height = Math.round(220 * ratio);
    c.getContext('2d').drawImage(page.canvas, 0, 0, c.width, c.height);
    const label = document.createElement('div');
    label.textContent = `Student ${i + 1}`;
    item.append(c, label);
    wrap.append(item);
  });
  if (state.pages.length > 24) {
    const more = document.createElement('div');
    more.className = 'thumb';
    more.style.display = 'grid';
    more.style.placeItems = 'center';
    more.style.minHeight = '180px';
    more.textContent = `+ ${state.pages.length - 24} more`;
    wrap.append(more);
  }
}

$('#continueToSetup').addEventListener('click', () => {
  switchStep('setup');
  renderSetupCanvas();
});

function renderSetupCanvas(tempRect = null) {
  if (!state.pages.length) return;
  const src = state.pages[0].canvas;
  const c = $('#setupCanvas');
  c.width = src.width;
  c.height = src.height;
  const ctx = c.getContext('2d');
  ctx.drawImage(src, 0, 0);
  state.questions.forEach((q, idx) => drawQuestionRect(ctx, q, idx));
  if (tempRect) {
    ctx.save();
    ctx.strokeStyle = '#1c5b45';
    ctx.lineWidth = Math.max(3, c.width * .002);
    ctx.setLineDash([12, 8]);
    ctx.strokeRect(tempRect.x, tempRect.y, tempRect.w, tempRect.h);
    ctx.restore();
  }
}

function drawQuestionRect(ctx, q, idx) {
  const c = $('#setupCanvas');
  const x = q.x * c.width, y = q.y * c.height, w = q.w * c.width, h = q.h * c.height;
  ctx.save();
  ctx.fillStyle = 'rgba(28,91,69,.10)';
  ctx.strokeStyle = '#1c5b45';
  ctx.lineWidth = Math.max(3, c.width * .002);
  ctx.fillRect(x, y, w, h);
  ctx.strokeRect(x, y, w, h);
  const fs = Math.max(18, c.width * .016);
  ctx.font = `800 ${fs}px system-ui`;
  ctx.fillStyle = '#1c5b45';
  ctx.fillText(q.label || `Q${idx + 1}`, x + 7, y + fs + 4);
  ctx.restore();
}

const setupCanvas = $('#setupCanvas');
setupCanvas.addEventListener('pointerdown', (e) => {
  if (!state.pages.length) return;
  setupCanvas.setPointerCapture(e.pointerId);
  const p = eventPoint(e, setupCanvas);
  state.drawing = { x0: p.x, y0: p.y, x: p.x, y: p.y, w: 0, h: 0 };
});
setupCanvas.addEventListener('pointermove', (e) => {
  if (!state.drawing) return;
  const p = eventPoint(e, setupCanvas);
  const d = state.drawing;
  d.x = Math.min(d.x0, p.x); d.y = Math.min(d.y0, p.y);
  d.w = Math.abs(p.x - d.x0); d.h = Math.abs(p.y - d.y0);
  renderSetupCanvas(d);
});
setupCanvas.addEventListener('pointerup', (e) => {
  if (!state.drawing) return;
  const d = state.drawing;
  state.drawing = null;
  if (d.w < setupCanvas.width * .015 || d.h < setupCanvas.height * .01) {
    renderSetupCanvas();
    return;
  }
  const idx = state.questions.length + 1;
  state.questions.push({
    id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${idx}`,
    label: `Q${idx}`,
    points: 1,
    x: d.x / setupCanvas.width,
    y: d.y / setupCanvas.height,
    w: d.w / setupCanvas.width,
    h: d.h / setupCanvas.height,
  });
  renderQuestionList();
  renderSetupCanvas();
  updateSetupReady();
});

function eventPoint(e, canvas) {
  const r = canvas.getBoundingClientRect();
  return {
    x: (e.clientX - r.left) * canvas.width / r.width,
    y: (e.clientY - r.top) * canvas.height / r.height,
  };
}

function renderQuestionList() {
  const list = $('#questionList');
  if (!state.questions.length) {
    list.className = 'question-list empty-state';
    list.textContent = 'No question boxes yet.';
    return;
  }
  list.className = 'question-list';
  list.innerHTML = '';
  state.questions.forEach((q, i) => {
    const el = document.createElement('div');
    el.className = 'question-item';
    el.innerHTML = `
      <div class="question-row">
        <span class="q-color"></span>
        <input type="text" value="${escapeHtml(q.label)}" aria-label="Question label">
        <button title="Delete question" aria-label="Delete question">×</button>
      </div>
      <div class="question-row" style="margin-top:7px;color:#6d6d66;font-size:12px">
        <span style="flex:1">Points</span>
        <input type="number" min="0.5" step="0.5" value="${q.points}" aria-label="Points">
      </div>`;
    const [labelInput, pointsInput] = el.querySelectorAll('input');
    labelInput.addEventListener('input', () => { q.label = labelInput.value || `Q${i + 1}`; renderSetupCanvas(); });
    pointsInput.addEventListener('input', () => { q.points = Math.max(.5, Number(pointsInput.value) || 1); });
    el.querySelector('button').addEventListener('click', () => {
      state.questions.splice(i, 1);
      state.grades = {};
      renderQuestionList(); renderSetupCanvas(); updateSetupReady();
    });
    list.append(el);
  });
}

function escapeHtml(s='') {
  return s.replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
}

function updateSetupReady() {
  const ready = state.questions.length > 0;
  $('#continueToGrade').disabled = !ready;
  enableStep('grade', ready);
}

$('#clearQuestions').addEventListener('click', () => {
  state.questions = [];
  state.grades = {};
  renderQuestionList(); renderSetupCanvas(); updateSetupReady();
});

$('#continueToGrade').addEventListener('click', () => {
  state.activeQuestion = 0;
  state.selectedStudent = 0;
  initGradeData();
  renderGradeView();
  switchStep('grade');
});

function initGradeData() {
  state.pages.forEach((_, pi) => {
    if (!state.grades[pi]) state.grades[pi] = {};
    state.questions.forEach(q => {
      if (!state.grades[pi][q.id]) state.grades[pi][q.id] = { status: null };
    });
  });
}

function renderGradeView() {
  const q = state.questions[state.activeQuestion];
  if (!q) return;
  $('#gradeQuestionTitle').textContent = q.label || `Q${state.activeQuestion + 1}`;
  $('#gradeQuestionMeta').textContent = `${q.points} point${q.points === 1 ? '' : 's'} · ${state.activeQuestion + 1} of ${state.questions.length}`;

  const select = $('#questionSelect');
  select.innerHTML = state.questions.map((qq,i) => `<option value="${i}" ${i===state.activeQuestion?'selected':''}>${escapeHtml(qq.label || `Q${i+1}`)}</option>`).join('');
  $('#prevQuestion').disabled = state.activeQuestion === 0;
  $('#nextQuestion').disabled = state.activeQuestion === state.questions.length - 1;

  const grid = $('#gradeGrid');
  grid.innerHTML = '';
  state.pages.forEach((page, pi) => {
    const grade = state.grades[pi][q.id];
    const card = document.createElement('div');
    card.className = `student-card ${pi === state.selectedStudent ? 'selected' : ''}`;
    card.dataset.student = pi;

    const top = document.createElement('div');
    top.className = 'student-top';
    const name = document.createElement('input');
    name.className = 'student-name';
    name.value = state.names[pi] || `Student ${pi+1}`;
    name.addEventListener('input', () => state.names[pi] = name.value);
    const chip = document.createElement('span');
    chip.className = `status-chip ${grade.status || ''}`;
    chip.textContent = statusLabel(grade.status);
    top.append(name, chip);

    const crop = makeCropCanvas(page.canvas, q);
    crop.className = 'answer-crop';

    const buttons = document.createElement('div');
    buttons.className = 'grade-buttons';
    [['correct','○ Correct'],['partial','△ Half'],['wrong','× Wrong'],[null,'Clear']].forEach(([status,label]) => {
      const b = document.createElement('button');
      b.textContent = label;
      b.className = `${status || ''} ${grade.status === status && status ? 'active' : ''}`;
      b.addEventListener('click', (ev) => { ev.stopPropagation(); setGrade(pi, status); });
      buttons.append(b);
    });

    card.append(top, crop, buttons);
    card.addEventListener('click', () => { state.selectedStudent = pi; renderGradeView(); });
    grid.append(card);
  });
}

function makeCropCanvas(src, q) {
  const sx = Math.max(0, Math.round(q.x * src.width));
  const sy = Math.max(0, Math.round(q.y * src.height));
  const sw = Math.max(1, Math.round(q.w * src.width));
  const sh = Math.max(1, Math.round(q.h * src.height));
  const c = document.createElement('canvas');
  const maxW = 700, maxH = 300;
  const scale = Math.min(maxW / sw, maxH / sh, 1.8);
  c.width = Math.max(1, Math.round(sw * scale));
  c.height = Math.max(1, Math.round(sh * scale));
  const ctx = c.getContext('2d', { alpha:false });
  ctx.fillStyle = '#fff'; ctx.fillRect(0,0,c.width,c.height);
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(src, sx, sy, sw, sh, 0, 0, c.width, c.height);
  return c;
}

function statusLabel(status) {
  return status === 'correct' ? 'Correct' : status === 'partial' ? 'Partial' : status === 'wrong' ? 'Wrong' : 'Ungraded';
}

function setGrade(studentIndex, status, advance = false) {
  const q = state.questions[state.activeQuestion];
  state.grades[studentIndex][q.id].status = status;
  state.selectedStudent = advance ? Math.min(state.pages.length - 1, studentIndex + 1) : studentIndex;
  renderGradeView();
  if (advance) requestAnimationFrame(() => {
    document.querySelector(`.student-card[data-student="${state.selectedStudent}"]`)?.scrollIntoView({block:'nearest', behavior:'smooth'});
  });
}

$('#questionSelect').addEventListener('change', e => { state.activeQuestion = Number(e.target.value); state.selectedStudent = 0; renderGradeView(); });
$('#prevQuestion').addEventListener('click', () => { if (state.activeQuestion > 0) { state.activeQuestion--; state.selectedStudent=0; renderGradeView(); } });
$('#nextQuestion').addEventListener('click', () => { if (state.activeQuestion < state.questions.length-1) { state.activeQuestion++; state.selectedStudent=0; renderGradeView(); } });

document.addEventListener('keydown', (e) => {
  if (!$('#grade').classList.contains('active')) return;
  if (e.target.matches('input,select,textarea')) return;
  if (e.key === '1') { e.preventDefault(); setGrade(state.selectedStudent, 'correct', true); }
  else if (e.key === '2') { e.preventDefault(); setGrade(state.selectedStudent, 'partial', true); }
  else if (e.key === '3') { e.preventDefault(); setGrade(state.selectedStudent, 'wrong', true); }
  else if (e.key === '0') { e.preventDefault(); setGrade(state.selectedStudent, null, false); }
  else if (e.key === 'ArrowRight') { e.preventDefault(); state.selectedStudent = Math.min(state.pages.length-1, state.selectedStudent+1); renderGradeView(); }
  else if (e.key === 'ArrowLeft') { e.preventDefault(); state.selectedStudent = Math.max(0, state.selectedStudent-1); renderGradeView(); }
});

$('#goPrint').addEventListener('click', () => {
  renderScoreSummary();
  enableStep('print', true);
  switchStep('print');
});

function scoreForStudent(pi) {
  let score = 0, max = 0, graded = 0;
  state.questions.forEach(q => {
    max += q.points;
    const status = state.grades[pi]?.[q.id]?.status;
    if (status) graded++;
    if (status === 'correct') score += q.points;
    else if (status === 'partial') score += q.points / 2;
  });
  return { score, max, graded };
}

function renderScoreSummary() {
  const rows = state.pages.map((_, pi) => {
    const {score,max,graded} = scoreForStudent(pi);
    return `<tr><td>${escapeHtml(state.names[pi] || `Student ${pi+1}`)}</td><td>${score.toFixed(score%1?1:0)} / ${max.toFixed(max%1?1:0)}${graded < state.questions.length ? ' *' : ''}</td></tr>`;
  }).join('');
  $('#scoreSummary').innerHTML = `<table class="score-table"><thead><tr><th>Student</th><th>Score</th></tr></thead><tbody>${rows}</tbody></table><p class="small-note">* has ungraded questions</p>`;
}

$('#printCorrections').addEventListener('click', () => openPrintWindow(false));
$('#printCalibration').addEventListener('click', () => openPrintWindow(true));

function openPrintWindow(calibration = false) {
  if (!state.pages.length || !state.questions.length) return;
  const paperKey = $('#paperSize').value;
  let [pw, ph] = PAPER_MM[paperKey];
  const landscape = state.pages[0].width > state.pages[0].height;
  if (landscape && ph > pw) [pw, ph] = [ph, pw];
  const offsetX = Number($('#offsetX').value) || 0;
  const offsetY = Number($('#offsetY').value) || 0;
  const rotate = $('#rotate180').checked;
  const reverse = $('#reverseOrder').checked;

  let indices = calibration ? [0] : state.pages.map((_,i)=>i);
  if (reverse && !calibration) indices = indices.reverse();
  const images = indices.map(pi => makeOverlayCanvas(pi, calibration).toDataURL('image/png'));

  const w = window.open('', '_blank');
  if (!w) { toast('Popup blocked. Allow popups for printing.'); return; }
  const pages = images.map(src => `<section class="print-page"><img src="${src}" alt="correction overlay"></section>`).join('');
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${calibration?'Alignment test':'Correction marks'}</title><style>
    @page { size: ${pw}mm ${ph}mm; margin: 0; }
    html,body { margin:0; padding:0; background:white; }
    .print-page { position:relative; width:${pw}mm; height:${ph}mm; page-break-after:always; overflow:hidden; }
    .print-page:last-child { page-break-after:auto; }
    img { position:absolute; left:${offsetX}mm; top:${offsetY}mm; width:${pw}mm; height:${ph}mm; object-fit:fill; transform:${rotate?'rotate(180deg)':'none'}; transform-origin:center center; }
  </style></head><body>${pages}<script>window.onload=()=>setTimeout(()=>window.print(),250);<\/script></body></html>`);
  w.document.close();
}

function makeOverlayCanvas(pi, calibration = false) {
  const base = state.pages[pi];
  const c = document.createElement('canvas');
  c.width = base.width; c.height = base.height;
  const ctx = c.getContext('2d');
  ctx.clearRect(0,0,c.width,c.height);
  ctx.strokeStyle = '#d00000';
  ctx.fillStyle = '#d00000';
  ctx.lineWidth = Math.max(3, c.width * .0025);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  state.questions.forEach((q, qi) => {
    const status = calibration ? 'correct' : state.grades[pi]?.[q.id]?.status;
    if (!status) return;
    const x = q.x * c.width, y = q.y * c.height, w = q.w * c.width, h = q.h * c.height;
    const size = Math.max(20, Math.min(c.width * .027, Math.max(28, Math.min(w, h) * .34)));
    const cx = Math.min(c.width - size, x + w - size*.65);
    const cy = Math.max(size, y + size*.72);
    drawMark(ctx, status, cx, cy, size);
    if (calibration) {
      ctx.save();
      ctx.font = `700 ${Math.max(14,size*.45)}px system-ui`;
      ctx.fillText(q.label || `Q${qi+1}`, Math.max(2,x+4), Math.max(16,y+Math.max(14,size*.45)));
      ctx.restore();
    }
  });

  const {score,max} = scoreForStudent(pi);
  if (!calibration) {
    ctx.save();
    const fs = Math.max(28, c.width * .032);
    ctx.font = `800 ${fs}px system-ui`;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'top';
    ctx.fillText(`${formatNum(score)}/${formatNum(max)}`, c.width * .965, c.height * .025);
    ctx.restore();
  } else {
    ctx.save();
    const fs = Math.max(22,c.width*.023);
    ctx.font = `800 ${fs}px system-ui`;
    ctx.textAlign='right'; ctx.textBaseline='top';
    ctx.fillText('ALIGNMENT TEST', c.width*.965, c.height*.025);
    ctx.restore();
  }
  return c;
}

function formatNum(n) { return Number.isInteger(n) ? String(n) : n.toFixed(1); }

function drawMark(ctx, status, cx, cy, size) {
  ctx.save();
  ctx.lineWidth = Math.max(3, size * .11);
  if (status === 'correct') {
    ctx.beginPath(); ctx.arc(cx, cy, size*.52, 0, Math.PI*2); ctx.stroke();
  } else if (status === 'partial') {
    ctx.beginPath();
    ctx.moveTo(cx, cy-size*.58); ctx.lineTo(cx-size*.58, cy+size*.48); ctx.lineTo(cx+size*.58, cy+size*.48); ctx.closePath(); ctx.stroke();
  } else if (status === 'wrong') {
    ctx.beginPath(); ctx.moveTo(cx-size*.48,cy-size*.48); ctx.lineTo(cx+size*.48,cy+size*.48); ctx.moveTo(cx+size*.48,cy-size*.48); ctx.lineTo(cx-size*.48,cy+size*.48); ctx.stroke();
  }
  ctx.restore();
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('./sw.js').catch(() => {}));
}
