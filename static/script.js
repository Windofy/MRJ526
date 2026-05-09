/* MRJ3.0 — SPA Controller */
'use strict';

const API = '';  // same-origin; change to 'http://localhost:5000' for dev

// ── STATE ──────────────────────────────────────────────────────────────────
let sessionId = null;
let pollTimer = null;
let pollTimeout = null;   // hard stop after MAX_POLL_MS
const MAX_POLL_MS = 5 * 60 * 1000;  // 5 minutes (pipeline is now 3 calls)
let currentStep = 0;
let analysisData = null;
let renderInstruction = null;
let selectedColor = null;
let originalImageUrl = null;
let renderUrl = null;
let toastTimer = null;  // declared early to avoid temporal dead zone

// Catalog populated from analysis suggestions + config
const CATALOG = {
  "Aluminium Jaloezieën": [],
  "Houten Jaloezieën": []
};

// ── ELEMENTS ───────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const screens = {
  landing:  $('screen-landing'),
  loading:  $('screen-loading'),
  result:   $('screen-result'),
};

// ── SCREEN TRANSITIONS ─────────────────────────────────────────────────────
function showScreen(name) {
  Object.entries(screens).forEach(([k, el]) => {
    el.classList.toggle('screen--hidden', k !== name);
  });
  // Hide logo badge on loading screen
  const logo = $('topbar-logo');
  if (logo) logo.style.display = name === 'loading' ? 'none' : '';
}

// ── UPLOAD ─────────────────────────────────────────────────────────────────
const uploadZone = $('upload-zone');
const fileInput  = $('file-input');

uploadZone.addEventListener('click', () => fileInput.click());
uploadZone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});
fileInput.addEventListener('change', () => { if (fileInput.files[0]) handleFile(fileInput.files[0]); });

function handleFile(file) {
  const MAX = 10 * 1024 * 1024;
  const TYPES = ['image/png', 'image/jpeg', 'image/webp'];
  if (!TYPES.includes(file.type)) { showToast('Alleen PNG, JPG of WEBP is toegestaan.', true); return; }
  if (file.size > MAX) { showToast('Bestand te groot. Maximaal 10MB.', true); return; }

  originalImageUrl = URL.createObjectURL(file);
  $('slider-before').src = originalImageUrl;

  uploadFile(file);
}

async function uploadFile(file) {
  showScreen('loading');
  resetPhaseList();

  const fd = new FormData();
  fd.append('image', file);

  try {
    const res = await fetch(`${API}/upload`, { method: 'POST', body: fd });
    const json = await res.json();
    if (!res.ok) { handleError(json.error || 'Upload mislukt.'); return; }
    sessionId = json.session_id;
    startPolling();
  } catch (e) {
    handleError('Verbindingsfout bij uploaden.');
  }
}

// ── POLLING ────────────────────────────────────────────────────────────────
const MAX_RETRIES = 5;          // consecutive network failures before abort
let _pollRetries = 0;
let _isPolling = false;         // guard: prevents concurrent poll executions

function stopPolling() {
  clearInterval(pollTimer);
  clearTimeout(pollTimeout);
  pollTimer = null;
  pollTimeout = null;
  _isPolling = false;
  _pollRetries = 0;
}

function startPolling() {
  stopPolling();                // always clear before starting
  if (!sessionId) return;

  // Hard timeout: abort after MAX_POLL_MS
  pollTimeout = setTimeout(() => {
    stopPolling();
    handleError('De analyse duurt te lang. Controleer je API sleutels en probeer opnieuw.');
  }, MAX_POLL_MS);

  pollTimer = setInterval(pollStatus, 3000);
}

async function pollStatus() {
  if (!sessionId) { stopPolling(); return; }   // session was cleared (e.g. retry)
  if (_isPolling) return;                       // previous call still in-flight → skip tick
  _isPolling = true;

  try {
    const res = await fetch(`${API}/status/${sessionId}`);

    // 404 = session expired / not found → terminal
    if (res.status === 404) {
      console.warn('[poll] 404 — sessie niet gevonden, stop polling');
      stopPolling();
      handleError('Sessie verlopen. Upload opnieuw je foto.');
      return;
    }

    // 5xx = server fout → count retries
    if (!res.ok) {
      _pollRetries++;
      console.warn(`[poll] HTTP ${res.status} (${_pollRetries}/${MAX_RETRIES})`);
      if (_pollRetries >= MAX_RETRIES) {
        stopPolling();
        handleError('Server reageert niet. Probeer later opnieuw.');
      }
      return;
    }

    _pollRetries = 0;  // reset on success
    const json = await res.json();



    updateLoadingUI(json);

    if (json.status === 'done') {
      stopPolling();
      await fetchResult();
    } else if (json.status === 'error') {
      stopPolling();
      handleError(json.error || 'Er is een fout opgetreden.');
    }
    // 'uploading' | 'analysing' | 'rendering' → keep polling

  } catch (e) {
    // Network hiccup — increment retry counter
    _pollRetries++;
    console.warn(`[poll] network error (${_pollRetries}/${MAX_RETRIES}):`, e.message);
    if (_pollRetries >= MAX_RETRIES) {
      stopPolling();
      handleError('Verbinding verbroken. Controleer je internet en probeer opnieuw.');
    }
  } finally {
    _isPolling = false;
  }
}


// Phase messages shown as progress advances
const PHASE_MESSAGES = [
  'Super! Ik analyseer jouw foto…',
  'Ik bekijk de ramen in jouw ruimte…',
  'Ik bepaal de ideale jaloezie voor jou…',
  'Ik bereken de perfecte kleur…',
  'Ik leg de laatste hand aan de visualisatie…',
];

function updateLoadingUI({ status, step }) {
  const stepNum = parseInt(step) || 0;
  if (stepNum === currentStep && status !== 'rendering') return;
  currentStep = stepNum;

  // Progress bar: 0→95% across phases, 98% on rendering
  let pct = Math.min((stepNum / 5) * 95, 95);
  if (status === 'rendering') pct = 98;
  $('loading-bar').style.width = `${pct}%`;

  // Status message
  const msgEl = $('loading-message');
  if (status === 'rendering') {
    msgEl.textContent = 'Bijna klaar! Jouw visualisatie wordt gegenereerd…';
  } else if (stepNum >= 1 && stepNum <= PHASE_MESSAGES.length) {
    msgEl.textContent = PHASE_MESSAGES[stepNum - 1];
  }
}

function resetPhaseList() {
  currentStep = 0;
  $('loading-bar').style.width = '0%';
  $('loading-message').textContent = 'Super! Ik analyseer jouw foto…';
}

// ── RESULT ─────────────────────────────────────────────────────────────────
async function fetchResult() {
  try {
    const res = await fetch(`${API}/result/${sessionId}`);
    const json = await res.json();
    if (!res.ok) { handleError(json.error || 'Resultaat ophalen mislukt.'); return; }

    analysisData = json.analysis || {};
    renderInstruction = json.render_instruction || {};
    renderUrl = json.render_url;
    if (json.image_url) originalImageUrl = json.image_url;

    populateResultScreen();
    showScreen('result');
    $('loading-bar').style.width = '100%';
  } catch (e) {
    handleError('Kon resultaat niet ophalen.');
  }
}

async function populateResultScreen() {
  // Before/after images
  if (originalImageUrl) $('slider-before').src = originalImageUrl;
  if (renderUrl) {
    $('slider-after').src = renderUrl;
    initSlider();
  }

  // Pre-load catalog so suggestions + color-hero can use sampleUrls immediately
  await loadCatalog();

  // Suggestions
  const suggs = analysisData.suggestions || [];
  renderSuggestions(suggs);

  // Auto-select top suggestion (try to match with catalog to get sampleUrl)
  if (suggs.length > 0) {
    const top = suggs[0];
    // Try catalog match first for real sample image
    const catalogMatch = findCatalogColor(top.colorName);
    selectColor(catalogMatch || {
      name: top.colorName,
      hex: top.colorHex,
      material: `${top.material} ${top.productType}`,
      sampleUrl: '',
    });
  }

  // Technical window check
  const wc = analysisData.windowCheck || {};
  $('tech-type').textContent = wc.windowType || '—';
  $('tech-mount').textContent = wc.recommendation || '—';
  $('tech-count').textContent = wc.detectedWindowCount || '—';
  $('bijzonderheden').textContent = wc.specialConsiderations || wc.reasoning || '—';

  // Populate flyout from catalog
  populateFlyout();
}


// ── SUGGESTIONS — 4-card animated swatch grid ──────────────────────────────
function renderSuggestions(suggs) {
  const container = $('suggestions');
  container.innerHTML = '';

  // Show up to 4 suggestions in 2×2 grid
  suggs.slice(0, 4).forEach((s, idx) => {
    const catalogItem = findCatalogColor(s.colorName);
    const topUrl    = catalogItem?.topUrl    || catalogItem?.sampleUrl || '';
    const bottomUrl = catalogItem?.bottomUrl || catalogItem?.sampleUrl || '';
    const sampleUrl = catalogItem?.sampleUrl || topUrl || '';
    const hex       = s.colorHex || catalogItem?.hex || '#ccc';
    const material  = (s.material || catalogItem?.material || '').toUpperCase();

    const card = document.createElement('div');
    card.className = 'color-swatch-card';
    card.setAttribute('role', 'listitem');
    card.setAttribute('tabindex', '0');
    card.setAttribute('aria-label', s.colorName);

    // Mark first suggestion as selected by default
    if (idx === 0) card.classList.add('is-selected');

    // Build inner HTML — picture elements for the hover animation
    const topImg    = topUrl    ? `<img src="${topUrl}"    alt="${s.colorName} voorkant" loading="lazy" />` : '';
    const bottomImg = bottomUrl ? `<img src="${bottomUrl}" alt="${s.colorName} detail"   loading="lazy" />` : '';

    const hasImages = topUrl || bottomUrl;

    card.innerHTML = `
      <div class="color-swatch">
        ${hasImages ? `
          <picture>${topImg}</picture>
          <picture>${bottomImg}</picture>
        ` : `
          <div class="color-swatch__hex-block" style="background:${hex}"></div>
        `}
      </div>
      <p class="color-swatch-card__name">${s.colorName}</p>
      <p class="color-swatch-card__material">${material}</p>
    `;

    // Click / keyboard selection
    const onSelect = () => {
      // Remove selected state from all cards
      container.querySelectorAll('.color-swatch-card').forEach(c => c.classList.remove('is-selected'));
      card.classList.add('is-selected');
      selectColor({
        name:      s.colorName,
        hex:       hex,
        material:  `${s.material || ''} ${s.productType || ''}`.trim(),
        sampleUrl: sampleUrl,
      });
    };

    card.addEventListener('click', onSelect);
    card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(); } });

    container.appendChild(card);
  });
}


// ── COLOR SELECTION ────────────────────────────────────────────────────────
function selectColor(color) {
  selectedColor = color;
  const hero   = $('color-hero');
  const heroImg = $('color-hero-img');

  if (color.sampleUrl) {
    heroImg.src = color.sampleUrl;
    heroImg.style.display = 'block';
    hero.classList.remove('color-hero--hex-only');
  } else {
    // Fallback: show hex-colored swatch div
    heroImg.style.display = 'none';
    hero.classList.add('color-hero--hex-only');
    let swatchEl = hero.querySelector('.color-hero__swatch');
    if (!swatchEl) {
      swatchEl = document.createElement('div');
      swatchEl.className = 'color-hero__swatch';
      hero.insertBefore(swatchEl, hero.firstChild);
    }
    swatchEl.style.background = color.hex || '#ccc';
  }

  $('color-hero-name').textContent = color.name;
  $('color-hero-material').textContent = color.material || color.productType || '';

  // Mark selected in flyout
  document.querySelectorAll('.flyout-color-item').forEach(el => {
    el.classList.toggle('selected', el.dataset.colorName === color.name);
  });
}

// ── FLYOUT & CATALOG ────────────────────────────────────────────────────────
let _catalog = null;  // { 'Aluminium Jaloezieën': [...], 'Houten Jaloezieën': [...] }

async function loadCatalog() {
  if (_catalog) return _catalog;
  try {
    const res = await fetch(`${API}/catalogus`);
    _catalog = await res.json();
  } catch (e) {
    console.warn('[catalog] kon niet laden:', e);
    _catalog = {};
  }
  return _catalog;
}

function findCatalogColor(name) {
  if (!_catalog) return null;
  for (const items of Object.values(_catalog)) {
    const match = items.find(c => c.name.toLowerCase() === name.toLowerCase());
    if (match) return { name: match.name, hex: match.hex, material: match.material, sampleUrl: match.sampleUrl };
  }
  return null;
}

async function populateFlyout() {
  const cat = await loadCatalog();
  const aluItems  = cat['Aluminium Jaloezieën'] || [];
  const houtItems = cat['Houten Jaloezieën'] || [];

  // Update tab count badges
  $('tab-alu').innerHTML  = `Aluminium <span class="flyout__tab-count">${aluItems.length}</span>`;
  $('tab-hout').innerHTML = `Hout &amp; Bamboe <span class="flyout__tab-count">${houtItems.length}</span>`;

  renderFlyoutList('tabpanel-alu',  aluItems);
  renderFlyoutList('tabpanel-hout', houtItems);
}

function renderFlyoutList(panelId, items) {
  const panel = $(panelId);
  panel.innerHTML = '';
  items.forEach(item => {
    const el = document.createElement('div');
    el.className = 'flyout-color-item';
    el.dataset.colorName = item.name;

    if (item.sampleUrl) {
      el.innerHTML = `
        <img class="flyout-color-item__img" src="${item.sampleUrl}" alt="${item.name}" loading="lazy" />
        <div class="flyout-color-item__footer">
          <div class="flyout-color-item__name">${item.name}</div>
          <div class="flyout-color-item__material">${item.material}</div>
        </div>`;
    } else {
      // Hex-only fallback
      el.innerHTML = `
        <div class="flyout-color-item__swatch" style="background:${item.hex || '#ccc'}"></div>
        <div class="flyout-color-item__footer">
          <div class="flyout-color-item__name">${item.name}</div>
          <div class="flyout-color-item__material">${item.material}</div>
        </div>`;
    }

    el.addEventListener('click', () => {
      selectColor({ name: item.name, hex: item.hex, material: item.material, sampleUrl: item.sampleUrl || '' });
      closeFlyout();
    });
    panel.appendChild(el);
  });
}

// Flyout open/close
$('btn-open-flyout').addEventListener('click', openFlyout);
$('btn-close-flyout').addEventListener('click', closeFlyout);
$('flyout-overlay').addEventListener('click', closeFlyout);

function openFlyout() {
  $('color-flyout').classList.add('open');
  $('flyout-overlay').classList.add('visible');
  $('color-flyout').removeAttribute('aria-hidden');
  $('btn-open-flyout').setAttribute('aria-expanded', 'true');
}
function closeFlyout() {
  $('color-flyout').classList.remove('open');
  $('flyout-overlay').classList.remove('visible');
  $('color-flyout').setAttribute('aria-hidden', 'true');
  $('btn-open-flyout').setAttribute('aria-expanded', 'false');
}

// Flyout tabs
$('tab-alu').addEventListener('click', () => switchTab('alu'));
$('tab-hout').addEventListener('click', () => switchTab('hout'));
function switchTab(tab) {
  $('tabpanel-alu').classList.toggle('flyout__list--hidden', tab !== 'alu');
  $('tabpanel-hout').classList.toggle('flyout__list--hidden', tab !== 'hout');
  $('tab-alu').classList.toggle('flyout__tab--active', tab === 'alu');
  $('tab-hout').classList.toggle('flyout__tab--active', tab === 'hout');
  $('tab-alu').setAttribute('aria-selected', tab === 'alu');
  $('tab-hout').setAttribute('aria-selected', tab === 'hout');
}

// ── BEFORE/AFTER SLIDER ────────────────────────────────────────────────────
function initSlider() {
  const slider    = $('slider');
  const clip      = $('slider-clip');
  const divider   = $('slider-divider');
  const handle    = $('slider-handle');
  let dragging = false;

  function setPosition(x) {
    const rect = slider.getBoundingClientRect();
    let pct = Math.max(0, Math.min(1, (x - rect.left) / rect.width));
    const pctPx = `${pct * 100}%`;
    divider.style.left = pctPx;
    clip.style.clipPath = `inset(0 ${100 - pct * 100}% 0 0)`;
    handle.setAttribute('aria-valuenow', Math.round(pct * 100));
  }

  slider.addEventListener('mousedown', e => { dragging = true; setPosition(e.clientX); });
  window.addEventListener('mousemove', e => { if (dragging) setPosition(e.clientX); });
  window.addEventListener('mouseup', () => { dragging = false; });

  slider.addEventListener('touchstart', e => { dragging = true; setPosition(e.touches[0].clientX); }, { passive: true });
  window.addEventListener('touchmove', e => { if (dragging) setPosition(e.touches[0].clientX); }, { passive: true });
  window.addEventListener('touchend', () => { dragging = false; });

  handle.addEventListener('keydown', e => {
    const rect = slider.getBoundingClientRect();
    const curr = parseFloat(divider.style.left || '50%') / 100;
    if (e.key === 'ArrowLeft') setPosition(rect.left + (curr - 0.05) * rect.width);
    if (e.key === 'ArrowRight') setPosition(rect.left + (curr + 0.05) * rect.width);
  });

  setPosition(slider.getBoundingClientRect().left + slider.getBoundingClientRect().width / 2);
}

// ── VISUALIZE (re-render) ──────────────────────────────────────────────────
async function triggerVisualize() {
  if (!sessionId || !renderInstruction) return;

  const TILT_MAP = {
    fully_open:   'Slats fully open at 0° horizontal — blades are perfectly flat, maximum transparency, full outdoor view visible through wide gaps between slats',
    slightly_open:'Slats tilted slightly at 35° downward — partial view through narrowed gaps, soft diffused light, gentle diagonal shadows on floor',
    privacy:      'Slats at privacy mode 50° steep angle — broad slat faces visible from front, sightlines from outside blocked, only indirect ambient light enters',
    closed:       'Slats fully closed at 90° vertical — solid opaque panel, zero gaps, zero light transmission, no outdoor view, fully closed blind surface',
  };
  const tiltVal = document.querySelector('input[name="tilt"]:checked')?.value || 'fully_open';

  // Lighting descriptions with exact keywords matched to render_gemini.py _lighting_block() detection
  const LIGHTING_MAP = {
    'Ochtend (Koel)':       'Early morning ochtend — soft cool blue-white daylight from low sun angle, long cool shadows, fresh quiet atmosphere, pale sky outside',
    'Middag (Helder)':      'Bright middag noon — high overhead sun, strong white-yellow direct light, sharp high-contrast shadows, vivid saturated colors, bright helder sky outside',
    'Zonsondergang (Warm)': 'Golden hour zonsondergang — warm amber-orange light flooding through window, rich golden tones on all surfaces, long dramatic shadows, cinematic atmosphere, orange sky outside',
    'Avond (Sfeervol)':     'Evening avond — exterior is dark night sky, NO daylight outside, interior lit by warm artificial lamps switched on, cozy amber glow inside, dark nacht exterior visible through window',
  };
  const rawDaytime = document.querySelector('input[name="daytime"]:checked')?.value || 'Zonsondergang (Warm)';

  const config = {
    color_name:         selectedColor?.name || renderInstruction.color_name,
    hex_code:           selectedColor?.hex  || renderInstruction.hex_code,
    slat_width:         document.querySelector('input[name="slat"]:checked')?.value || renderInstruction.slat_width,
    ladder_tape:        document.querySelector('input[name="ladder"]:checked')?.value === 'ladderband',
    lighting_condition: LIGHTING_MAP[rawDaytime] || rawDaytime,
    state:              TILT_MAP[tiltVal] || TILT_MAP.fully_open,
  };

  const btnTop = $('btn-viz-top');
  const btnBot = $('btn-viz-bottom');
  [btnTop, btnBot].forEach(b => { b.disabled = true; b.textContent = '⏳ Bezig…'; });

  try {
    const res = await fetch(`${API}/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, config }),
    });
    const json = await res.json();
    if (!res.ok) { showToast(json.error || 'Visualisatie mislukt.', true); return; }
    renderUrl = json.render_url;
    $('slider-after').src = renderUrl + '?t=' + Date.now();
  } catch (e) {
    showToast('Verbindingsfout bij visualiseren.', true);
  } finally {
    [btnTop, btnBot].forEach(b => { b.disabled = false; b.textContent = '✨ Resultaat visualiseren'; });
  }
}

$('btn-viz-top').addEventListener('click', triggerVisualize);
$('btn-viz-bottom').addEventListener('click', triggerVisualize);

// ── SAVE IMAGE ─────────────────────────────────────────────────────────────
$('btn-save').addEventListener('click', () => {
  if (!renderUrl) return;
  const a = document.createElement('a');
  a.href = renderUrl;
  a.download = 'mr-jealousy-visualisatie.png';
  a.click();
});

// ── RETRY ──────────────────────────────────────────────────────────────────
$('btn-retry').addEventListener('click', resetToLanding);
const btnClose = $('btn-close');
if (btnClose) btnClose.addEventListener('click', resetToLanding);

function resetToLanding() {
  stopPolling();
  sessionId = null; analysisData = null; renderInstruction = null;
  selectedColor = null; renderUrl = null; originalImageUrl = null;
  fileInput.value = '';
  showScreen('landing');
}

// ── ERROR HANDLING ─────────────────────────────────────────────────────────
function handleError(msg) {
  showToast(msg, true);
  showScreen('landing');
}

// ── TOAST ──────────────────────────────────────────────────────────────────
// toastTimer is declared at top of file to avoid temporal dead zone
function showToast(msg, isError = false) {
  const toast = $('toast');
  $('toast-message').textContent = msg;
  toast.classList.toggle('toast--error', isError);
  toast.classList.add('visible');
  toast.removeAttribute('aria-hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(hideToast, 5000);
}
function hideToast() {
  const toast = $('toast');
  toast.classList.remove('visible');
  toast.setAttribute('aria-hidden', 'true');
}
$('btn-close-toast').addEventListener('click', hideToast);
