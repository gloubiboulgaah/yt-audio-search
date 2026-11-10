const $ = s => document.querySelector(s);
function h(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) k.startsWith('on') ? e.addEventListener(k.slice(2), v) : e.setAttribute(k, v);
  for (const k of kids.flat()) if (k != null) e.append(k);
  return e;
}
const fmt = t => { t = Math.floor(t); const p = n => String(n).padStart(2, '0'); return `${p(Math.floor(t / 3600))}:${p(Math.floor(t % 3600 / 60))}:${p(t % 60)}`; };
const fmtp = t => `${fmt(t)}.${Math.floor(t * 10) % 10}`;
const parseT = s => s.trim().split(':').reverse().reduce((a, x, i) => a + parseFloat(x.replace(',', '.')) * 60 ** i, 0);
const api = (url, body, method) => fetch(url, body === undefined ? { method: method || 'GET' } : { method: method || 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json());
document.body.prepend(h('nav', {}, ...[['upload', 'Upload'], ['search', 'Recherche'], ['bookmarks', 'Signets'], ['files', 'Fichiers'], ['settings', 'Paramètres']].map(([p, l]) => h('a', { href: '/' + p, class: location.pathname === '/' + p ? 'on' : '' }, l))));

// Icônes Lucide (ISC) en SVG inline.
const ICONS = {
  bookmark: '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
  check: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>',
  folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
  pencil: '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
};
function icon(name, cls = '') {
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  s.setAttribute('viewBox', '0 0 24 24');
  s.setAttribute('class', 'icon ' + cls);
  s.setAttribute('aria-hidden', 'true');
  s.innerHTML = ICONS[name];
  return s;
}

function modal(...kids) {
  const d = h('dialog', {}, ...kids);
  d.addEventListener('close', () => d.remove());
  document.body.append(d);
  d.showModal();
  return d;
}

// --- Signets ---
function bookmarkBtn(data, id) {
  const btn = h('button', { type: 'button', class: 'iconbtn' });
  const set = v => { id = v; btn.replaceChildren(icon('bookmark', id ? 'filled' : '')); btn.classList.toggle('on', !!id); btn.title = id ? 'Retirer des signets' : 'Ajouter aux signets'; btn.setAttribute('aria-label', btn.title); };
  btn.onclick = async () => {
    if (id) { await api('/api/bookmarks/' + id, undefined, 'DELETE'); return set(null); }
    openBookmark(data, set);
  };
  set(id);
  return btn;
}

async function openBookmark(data, onSaved) {
  const cats = await api('/api/categories');
  const sel = h('select', { 'aria-label': 'Catégorie' }, h('option', { value: '' }, 'Sans catégorie'), ...cats.map(c => h('option', { value: c.id }, c.name)), h('option', { value: 'new' }, '+ Nouvelle catégorie…'));
  const name = h('input', { placeholder: 'Nom de la nouvelle catégorie', 'aria-label': 'Nouvelle catégorie', hidden: '' });
  sel.onchange = () => { name.hidden = sel.value !== 'new'; if (!name.hidden) name.focus(); };
  if (cats.length) sel.value = localStorage.lastCat && cats.some(c => c.id == localStorage.lastCat) ? localStorage.lastCat : '';
  const err = h('div', { class: 'err' });
  const d = modal(h('form', { method: 'dialog', onsubmit: async e => {
    e.preventDefault();
    let cid = sel.value || null;
    if (cid === 'new') {
      const r = await api('/api/categories', { name: name.value });
      if (r.error) return err.textContent = r.error;
      cid = r.id;
    }
    const r = await api('/api/bookmarks', { ...data, category_id: cid && +cid });
    if (r.error) return err.textContent = r.error;
    localStorage.lastCat = cid || '';
    onSaved(r.id);
    d.close();
  } },
    h('h3', {}, 'Ajouter aux signets'),
    h('p', { class: 'muted' }, `${fmt(data.start)} — « ${data.text} »`),
    h('div', { class: 'row' }, sel, name), err,
    h('div', { class: 'row end' }, h('button', { type: 'button', class: 'ghost', onclick: () => d.close() }, 'Annuler'), h('button', {}, 'Enregistrer'))));
}

// --- Hors ligne / téléchargements ---
// a, b : passage (mots trouvés) qui doit être contenu dans un extrait téléchargé.
function offlineBtn(vid, a, b, clipId, openDl) {
  const btn = h('button', { type: 'button', class: 'iconbtn dl', 'data-vid': vid });
  btn.covers = c => c.video_id === vid && c.start - 0.05 <= a && b <= c.end + 0.05;
  btn.set = id => { clipId = id; btn.replaceChildren(icon(id ? 'check' : 'download')); btn.classList.toggle('ok', !!id); btn.title = id ? 'Disponible hors ligne — ouvrir l’emplacement' : 'Télécharger un extrait'; btn.setAttribute('aria-label', btn.title); };
  btn.onclick = () => clipId ? api(`/api/clips/${clipId}/reveal`, {}) : openDl();
  btn.set(clipId);
  return btn;
}

document.addEventListener('clip', e => document.querySelectorAll(`button.dl[data-vid="${CSS.escape(e.detail.video_id)}"]`).forEach(b => { if (!b.classList.contains('ok') && b.covers(e.detail)) b.set(e.detail.id); }));

function trackJob(jid, label) {
  const box = $('#toasts') || document.body.appendChild(h('div', { id: 'toasts', 'aria-live': 'polite' }));
  const t = box.appendChild(h('div', { class: 'toast' }, `⏳ ${label}`));
  const tick = async () => {
    const j = await api('/api/jobs/' + jid);
    if (!j.finished) return setTimeout(tick, 1500);
    if (j.errors?.length || !j.clip) { t.replaceChildren(h('span', { class: 'err' }, `Échec : ${label} — ${j.errors?.join(' ') || j.error}`), h('button', { class: 'ghost', onclick: () => t.remove() }, 'OK')); return; }
    t.replaceChildren(icon('check', 'okc'), ` ${label}`);
    document.dispatchEvent(new CustomEvent('clip', { detail: j.clip }));
    setTimeout(() => t.remove(), 6000);
  };
  tick();
}

const wordCache = {};
const getWords = vid => wordCache[vid] ||= api(`/api/videos/${encodeURIComponent(vid)}/words`);

// Choix de la plage à télécharger : poignées sur la timeline ou timecodes précis, sous-titres en direct.
async function openDownload({ vid, title, dur, start, end, ticks = [] }) {
  const words = await getWords(vid);
  dur = dur || (words.length ? words[words.length - 1][0] + 5 : 60);
  let a = Math.max(0, start ?? 0), b = Math.min(dur, end ?? dur);
  const idx = t => { let lo = 0, hi = words.length - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; words[m][0] <= t ? lo = m : hi = m - 1; } return lo; };
  const caption = t => {
    if (!words.length) return ['(pas de sous-titres)'];
    const i = idx(t), lo = Math.max(0, i - 6);
    return words.slice(lo, i + 10).map(([, w], k) => [lo + k === i ? h('mark', {}, w) : w, ' ']);
  };
  const sel = h('div', { class: 'sel' });
  const ha = h('div', { class: 'handle', tabindex: 0, role: 'slider', 'aria-label': 'Début de l’extrait' });
  const hb = h('div', { class: 'handle', tabindex: 0, role: 'slider', 'aria-label': 'Fin de l’extrait' });
  const bar = h('div', { class: 'bar range' }, sel, ...ticks.map(t => h('div', { class: 'tick', style: `left:${100 * t / dur}%`, title: fmt(t) })), ha, hb);
  const ia = h('input', { 'aria-label': 'Début (hh:mm:ss.d)', size: 11 }), ib = h('input', { 'aria-label': 'Fin (hh:mm:ss.d)', size: 11 });
  const len = h('span', { class: 'muted' }), ca = h('div', { class: 'cap' }), cb = h('div', { class: 'cap' }), err = h('div', { class: 'err' });
  const update = (typing) => {
    sel.style.left = ha.style.left = `${100 * a / dur}%`;
    hb.style.left = `${100 * b / dur}%`;
    sel.style.width = `${100 * (b - a) / dur}%`;
    ha.setAttribute('aria-valuenow', a); ha.setAttribute('aria-valuetext', fmtp(a));
    hb.setAttribute('aria-valuenow', b); hb.setAttribute('aria-valuetext', fmtp(b));
    if (typing !== ia) ia.value = fmtp(a);
    if (typing !== ib) ib.value = fmtp(b);
    len.textContent = `durée ${fmtp(b - a)}`;
    ca.replaceChildren(h('b', {}, 'Début : '), '… ', ...caption(a).flat(), '…');
    cb.replaceChildren(h('b', {}, 'Fin : '), '… ', ...caption(b).flat(), '…');
  };
  const setA = t => { a = Math.max(0, Math.min(t, b - 0.5)); }, setB = t => { b = Math.min(dur, Math.max(t, a + 0.5)); };
  const at = e => { const r = bar.getBoundingClientRect(); return dur * Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)); };
  for (const [hd, set] of [[ha, setA], [hb, setB]]) {
    hd.onpointerdown = e => { e.stopPropagation(); hd.setPointerCapture(e.pointerId); hd.focus(); };
    hd.onpointermove = e => { if (hd.hasPointerCapture(e.pointerId)) { set(at(e)); update(); } };
    hd.onkeydown = e => { const s = { ArrowLeft: -1, ArrowRight: 1, ArrowDown: -1, ArrowUp: 1 }[e.key]; if (s) { e.preventDefault(); set((hd === ha ? a : b) + s * (e.shiftKey ? 10 : e.altKey ? 0.1 : 1)); update(); } };
  }
  bar.onpointerdown = e => { const t = at(e); Math.abs(t - a) < Math.abs(t - b) ? setA(t) : setB(t); update(); };
  ia.oninput = () => { const t = parseT(ia.value); if (!isNaN(t)) { setA(t); update(ia); } };
  ib.oninput = () => { const t = parseT(ib.value); if (!isNaN(t)) { setB(t); update(ib); } };
  const go = async full => {
    const r = await api('/api/clips', { video_id: vid, start: a, end: b, full });
    if (r.error) return err.textContent = r.error;
    trackJob(r.id, `${title} — ${full ? 'vidéo entière' : `${fmt(a)} → ${fmt(b)}`}`);
    d.close();
  };
  const d = modal(h('div', { class: 'dlbox' },
    h('h3', {}, 'Télécharger — ', title),
    h('p', { class: 'muted' }, 'Glisser les poignées sur la timeline (flèches du clavier : ±1 s, Maj : ±10 s, Alt : ±0,1 s) ou saisir les timecodes.'),
    bar,
    h('div', { class: 'row' }, h('label', {}, 'Début ', ia), h('label', {}, 'Fin ', ib), len),
    ca, cb, err,
    h('div', { class: 'row end' },
      h('button', { type: 'button', class: 'ghost', onclick: () => d.close() }, 'Annuler'),
      h('button', { type: 'button', class: 'ghost', onclick: () => go(true) }, 'Vidéo entière'),
      h('button', { type: 'button', onclick: () => go(false) }, icon('download'), ' Télécharger l’extrait'))));
  update();
}
