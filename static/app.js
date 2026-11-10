const $ = s => document.querySelector(s);
function h(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null && v !== false) k.startsWith('on') ? e.addEventListener(k.slice(2), v) : e.setAttribute(k, v);
  for (const k of kids.flat(Infinity)) if (k != null && k !== false) e.append(k);
  return e;
}
// replaceChildren qui accepte des tableaux imbriqués et ignore null/false (comme h()).
const fill = (el, ...kids) => el.replaceChildren(...kids.flat(Infinity).filter(k => k != null && k !== false));
const fmt = t => { t = Math.floor(t); const p = n => String(n).padStart(2, '0'); return `${p(Math.floor(t / 3600))}:${p(Math.floor(t % 3600 / 60))}:${p(t % 60)}`; };
const fmtShort = t => fmt(t).replace(/^00:/, '');
const fmtp = t => `${fmt(t)}.${Math.floor(t * 10) % 10}`;
const parseT = s => s.trim().split(':').reverse().reduce((a, x, i) => a + parseFloat(x.replace(',', '.')) * 60 ** i, 0);
const fmtNum = n => n == null ? '—' : n.toLocaleString('fr-FR');
const fmtDate = d => d ? new Date(+d.slice(0, 4), +d.slice(4, 6) - 1, +d.slice(6)).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }) : 'inconnue';
const fmtSize = b => b > 1e9 ? `${(b / 1e9).toFixed(1).replace('.', ',')} Go` : `${(b / 1e6).toFixed(1).replace('.', ',')} Mo`;
const thumbUrl = id => `https://i.ytimg.com/vi/${encodeURIComponent(id)}/mqdefault.jpg`;
const api = (url, body, method) => fetch(url, body === undefined ? { method: method || 'GET' } : { method: method || 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json());

// Icônes Lucide (ISC) en SVG inline.
const ICONS = {
  bookmark: '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
  check: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>',
  folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
  pencil: '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  files: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 3v18"/><path d="M3 7.5h4"/><path d="M3 12h18"/><path d="M3 16.5h4"/><path d="M17 3v18"/><path d="M17 7.5h4"/><path d="M17 16.5h4"/>',
  settings: '<path d="M20 7h-9"/><path d="M14 17H5"/><circle cx="17" cy="17" r="3"/><circle cx="7" cy="7" r="3"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  external: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  alert: '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
  film: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 3v18"/><path d="M3 7.5h4"/><path d="M3 12h4"/><path d="M3 16.5h4"/><path d="M17 3v18"/><path d="M17 7.5h4"/><path d="M17 12h4"/><path d="M17 16.5h4"/>',
  user: '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>',
  calendar: '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  left: '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
  text: '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/>',
};
function icon(name, cls = '') {
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  s.setAttribute('viewBox', '0 0 24 24');
  s.setAttribute('class', 'icon ' + cls);
  s.setAttribute('aria-hidden', 'true');
  s.innerHTML = ICONS[name];
  return s;
}

// Logo : une onde sonore dont une barre est surlignée.
const LOGO = '<svg viewBox="0 0 26 26" aria-hidden="true"><rect width="26" height="26" rx="7" fill="#1a1d24"/><g stroke-linecap="round" stroke-width="2.4"><path d="M6 11v4M10 8v10M18 9v8M22 12v2" stroke="#fff"/><path d="M14 5v16" stroke="#ffe45c"/></g></svg>';
const PAGES = [['search', 'Recherche', 'search'], ['bookmarks', 'Signets', 'bookmark'], ['files', 'Vidéos', 'files'], ['upload', 'Ajouter', 'plus'], ['settings', 'Paramètres', 'settings']];
const here = location.pathname === '/video' ? '/files' : location.pathname;
const brand = h('a', { class: 'brand', href: '/search' }, h('span', {}, 'Audio-search'));
brand.insertAdjacentHTML('afterbegin', LOGO);
document.body.prepend(h('header', { class: 'top' }, h('div', { class: 'in' }, brand,
  h('nav', { 'aria-label': 'Navigation' }, PAGES.map(([p, l, i]) => h('a', { href: '/' + p, class: here === '/' + p ? 'on' : null, 'aria-current': here === '/' + p ? 'page' : null }, icon(i), h('span', {}, l)))))));

function modal(...kids) {
  const d = h('dialog', {}, ...kids);
  d.addEventListener('close', () => d.remove());
  document.body.append(d);
  d.showModal();
  return d;
}

function thumb(id, title, onclick, dur) {
  const b = h(onclick ? 'button' : 'div', { class: 'thumb', type: onclick ? 'button' : null, onclick, 'aria-label': onclick ? `Lire « ${title} »` : null },
    h('img', { src: thumbUrl(id), alt: '', loading: 'lazy', onerror: e => e.target.remove() }),
    onclick && h('span', { class: 'play' }, icon('play')),
    dur ? h('span', { class: 'dur' }, fmtShort(dur)) : null);
  return b;
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
  const sel = h('select', { id: 'bmcat' }, h('option', { value: '' }, 'Sans catégorie'), cats.map(c => h('option', { value: c.id }, c.name)), h('option', { value: 'new' }, 'Nouvelle catégorie…'));
  const name = h('input', { placeholder: 'Nom de la catégorie', 'aria-label': 'Nom de la nouvelle catégorie', class: 'grow' });
  const showName = () => { name.hidden = sel.value !== 'new'; if (!name.hidden) name.focus(); };
  sel.onchange = showName;
  sel.value = cats.length ? (cats.some(c => c.id == localStorage.lastCat) ? localStorage.lastCat : '') : 'new';
  const err = h('div', { class: 'err', role: 'alert' });
  const d = modal(h('form', { onsubmit: async e => {
    e.preventDefault();
    let cid = sel.value || null;
    if (cid === 'new') {
      const r = await api('/api/categories', { name: name.value });
      if (r.error) return err.textContent = 'Donnez un nom à la catégorie.';
      cid = r.id;
    }
    const r = await api('/api/bookmarks', { ...data, category_id: cid && +cid });
    if (r.error) return err.textContent = r.error;
    localStorage.lastCat = cid || '';
    onSaved(r.id);
    d.close();
  } },
    h('h3', {}, 'Ajouter aux signets'),
    h('p', { class: 'quote' }, h('span', { class: 'tc' }, fmt(data.start)), ' ', data.text),
    h('label', { class: 'muted', for: 'bmcat' }, 'Catégorie'),
    h('div', { class: 'row' }, sel, name), err,
    h('div', { class: 'row end' }, h('button', { type: 'button', class: 'ghost', onclick: () => d.close() }, 'Annuler'), h('button', {}, icon('bookmark'), 'Ajouter aux signets'))));
  showName();
}

// --- Hors ligne ---
// a, b : passage qui doit être contenu dans un fichier téléchargé pour être dispo hors ligne.
function offlineBtn(vid, a, b, clipId, openDl) {
  const btn = h('button', { type: 'button', class: 'iconbtn dl', 'data-vid': vid });
  btn.covers = c => c.video_id === vid && c.start - 0.05 <= a && b <= c.end + 0.05;
  btn.set = id => { clipId = id; btn.replaceChildren(icon(id ? 'check' : 'download')); btn.classList.toggle('ok', !!id); btn.title = id ? 'Disponible hors ligne : afficher le fichier' : 'Télécharger ce passage'; btn.setAttribute('aria-label', btn.title); };
  btn.onclick = () => clipId ? reveal(clipId) : openDl();
  btn.set(clipId);
  return btn;
}
const reveal = id => api(`/api/clips/${id}/reveal`, {});

document.addEventListener('clip', e => document.querySelectorAll(`button.dl[data-vid="${CSS.escape(e.detail.video_id)}"]`).forEach(b => { if (!b.classList.contains('ok') && b.covers(e.detail)) b.set(e.detail.id); }));

// --- Notifications de téléchargement : suivies côté serveur, donc visibles sur toutes les pages ---
const announced = new Set(JSON.parse(sessionStorage.announced || '[]'));
const toasts = {};
let polling = false;
async function pollDownloads() {
  if (polling) return;
  polling = true;
  try {
    for (;;) {
      const js = await api('/api/clip-jobs');
      js.forEach(renderToast);
      if (!js.some(j => !j.finished)) break;
      await new Promise(r => setTimeout(r, 700));
    }
  } catch { /* serveur arrêté */ } finally { polling = false; }
}
function renderToast(j) {
  if (j.finished && announced.has(j.id) && !toasts[j.id]) return;
  const box = $('#toasts') || document.body.appendChild(h('div', { id: 'toasts', role: 'status', 'aria-live': 'polite' }));
  const el = toasts[j.id] ||= box.appendChild(h('div', { class: 'toast' }));
  const close = () => { el.remove(); delete toasts[j.id]; };
  const head = (ic, text) => h('div', { class: 'toast-head' }, icon(ic), h('b', { title: j.title }, text), h('button', { class: 'iconbtn', 'aria-label': 'Fermer', onclick: close }, icon('x')));
  if (!j.finished) {
    const pct = j.progress == null ? null : Math.round(j.progress * 100);
    el.replaceChildren(head('download', j.title), h('div', { class: 'toast-sub' }, j.label),
      h('div', { class: 'bar' + (pct == null ? ' indet' : ''), role: 'progressbar', 'aria-label': `Téléchargement de ${j.title}`, 'aria-valuenow': pct }, h('span', { style: `width:${pct ?? 0}%` })),
      h('div', { class: 'toast-foot' },
        h('span', {}, pct == null ? (j.phase === 'Préparation' && !j.full ? 'Découpage de l’extrait…' : `${j.phase}…`) : `${pct} %  ${fmtSize(j.done_bytes)} sur ${fmtSize(j.total_bytes)}`),
        h('span', {}, `${Math.round(j.elapsed)} s`)));
    return;
  }
  announced.add(j.id);
  sessionStorage.announced = JSON.stringify([...announced].slice(-200));
  if (j.errors.length || !j.clip) {
    el.className = 'toast fail';
    el.replaceChildren(head('alert', 'Échec du téléchargement'), h('div', { class: 'toast-sub' }, `${j.title}, ${j.label.toLowerCase()} : ${j.errors.join(' ') || 'erreur inconnue'}`));
    return;
  }
  el.className = 'toast done';
  el.replaceChildren(head('check', 'Téléchargé'), h('div', { class: 'toast-sub' }, `${j.title}`, h('br'), j.label),
    h('button', { class: 'btn ghost small', onclick: () => reveal(j.clip.id) }, icon('folder'), 'Afficher dans le dossier'));
  document.dispatchEvent(new CustomEvent('clip', { detail: j.clip }));
  setTimeout(close, 9000);
}
pollDownloads();

async function startDownload(body) {
  const r = await api('/api/clips', body);
  if (!r.error) pollDownloads();
  return r;
}

const QUALITIES = [['best', 'Meilleure qualité (le plus lent)'], ['1080', '1080p'], ['720', '720p'], ['480', '480p'], ['360', '360p (rapide)'], ['audio', 'Audio seul (le plus rapide)']];
const qualitySelect = (id, value) => { const s = h('select', { id }, QUALITIES.map(([v, l]) => h('option', { value: v }, l))); s.value = value; return s; };

const wordCache = {};
const getWords = vid => wordCache[vid] ||= api(`/api/videos/${encodeURIComponent(vid)}/words`);

// Choix de la plage à télécharger : poignées sur la timeline ou timecodes, sous-titres affichés en direct.
async function openDownload({ vid, title, dur, start, end, ticks = [] }) {
  const [words, prefs] = await Promise.all([getWords(vid), api('/api/settings')]);
  const quality = qualitySelect('dlq', prefs.quality);
  dur = dur || (words.length ? words[words.length - 1][0] + 5 : 60);
  let a = Math.max(0, start ?? 0), b = Math.min(dur, end ?? dur);
  const idx = t => { let lo = 0, hi = words.length - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; words[m][0] <= t ? lo = m : hi = m - 1; } return lo; };
  const caption = t => {
    if (!words.length) return ['Pas de sous-titres.'];
    const i = idx(t), lo = Math.max(0, i - 6);
    return words.slice(lo, i + 10).map(([, w], k) => [lo + k === i ? h('mark', {}, w) : w, ' ']);
  };
  const sel = h('div', { class: 'sel' });
  const ha = h('div', { class: 'handle', tabindex: 0, role: 'slider', 'aria-label': 'Début de l’extrait', 'aria-valuemin': 0, 'aria-valuemax': dur });
  const hb = h('div', { class: 'handle', tabindex: 0, role: 'slider', 'aria-label': 'Fin de l’extrait', 'aria-valuemin': 0, 'aria-valuemax': dur });
  const bar = h('div', { class: 'range' }, sel, ticks.map(t => h('div', { class: 'tick', style: `left:${100 * t / dur}%` })), ha, hb);
  const ia = h('input', { id: 'dla', inputmode: 'decimal' }), ib = h('input', { id: 'dlb', inputmode: 'decimal' });
  const len = h('span', { class: 'muted' }), ca = h('div', { class: 'cap' }), cb = h('div', { class: 'cap' }), err = h('div', { class: 'err', role: 'alert' });
  const update = typing => {
    sel.style.left = ha.style.left = `${100 * a / dur}%`;
    hb.style.left = `${100 * b / dur}%`;
    sel.style.width = `${100 * (b - a) / dur}%`;
    ha.setAttribute('aria-valuenow', a); ha.setAttribute('aria-valuetext', fmtp(a));
    hb.setAttribute('aria-valuenow', b); hb.setAttribute('aria-valuetext', fmtp(b));
    if (typing !== ia) ia.value = fmtp(a);
    if (typing !== ib) ib.value = fmtp(b);
    len.textContent = `Durée de l’extrait : ${fmtp(b - a)}`;
    ca.replaceChildren(...[h('b', {}, `Début, ${fmtp(a)}`), '… ', caption(a), '…'].flat(2));
    cb.replaceChildren(...[h('b', {}, `Fin, ${fmtp(b)}`), '… ', caption(b), '…'].flat(2));
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
    const r = await startDownload({ video_id: vid, start: a, end: b, full, quality: quality.value });
    if (r.error) return err.textContent = r.error;
    d.close();
  };
  const d = modal(h('div', {},
    h('h3', {}, 'Télécharger un passage'),
    h('div', { class: 'muted' }, title),
    bar,
    h('div', { class: 'timefields' }, h('label', { for: 'dla' }, 'Début', ia), h('label', { for: 'dlb' }, 'Fin', ib), h('label', { for: 'dlq' }, 'Qualité', quality), len),
    h('div', { class: 'caps' }, ca, cb),
    h('p', { class: 'muted' }, 'Faites glisser les poignées ou tapez les timecodes. Au clavier : flèches ±1 s, Maj ±10 s, Alt ±0,1 s.'),
    err,
    h('div', { class: 'row end' },
      h('button', { type: 'button', class: 'ghost', onclick: () => d.close() }, 'Annuler'),
      h('button', { type: 'button', class: 'ghost', onclick: () => go(true) }, 'Télécharger la vidéo entière'),
      h('button', { type: 'button', onclick: () => go(false) }, icon('download'), 'Télécharger l’extrait'))));
  update();
}

// --- Lecteur : YouTube, ou fichier téléchargé si YouTube est injoignable / la vidéo a été retirée ---
const ytFailed = new Set();
function createPlayer(slot, v, onTime) {
  let yt = null, vid = null, clip = null;
  const timer = setInterval(() => {
    if (!slot.isConnected) return clearInterval(timer);
    const t = vid ? clip.start + vid.currentTime : yt?.getCurrentTime?.();
    if (t != null && onTime) onTime(t);
  }, 300);
  const local = (t, c) => {
    c ||= v.clips.find(c => c.start - 0.05 <= t + 1 && t < c.end);
    yt = null;
    if (!c) {
      vid = null;
      return slot.replaceChildren(h('div', { class: 'player-msg' }, h('div', {}, 'YouTube ne répond pas et ce passage n’est pas téléchargé.', h('br'), h('a', { href: v.url, target: '_blank' }, 'Ouvrir sur YouTube'))));
    }
    if (!vid || clip !== c) {
      clip = c;
      vid = h('video', { controls: '', autoplay: '', src: `/api/clips/${c.id}/file` }, h('track', { kind: 'subtitles', srclang: 'fr', label: 'Sous-titres', src: `/api/clips/${c.id}/vtt`, default: '' }));
      slot.replaceChildren(vid);
    }
    vid.currentTime = Math.max(0, t - c.start);
    vid.play().catch(() => {});
  };
  return {
    play(t) {
      t = Math.max(0, t - 1);
      slot.hidden = false;
      if (!window.YT?.Player || ytFailed.has(v.id)) return local(t);
      if (yt?.seekTo) { yt.seekTo(t, true); yt.playVideo(); return; }
      vid = null;
      const div = h('div');
      slot.replaceChildren(div);
      yt = new YT.Player(div, { videoId: v.id, playerVars: { start: Math.floor(t), autoplay: 1, rel: 0 }, events: {
        onReady: e => { e.target.seekTo(t, true); e.target.playVideo(); },
        onError: () => { ytFailed.add(v.id); local(t); },
      } });
    },
    playClip(c) { slot.hidden = false; local(c.start, c); },
  };
}

// Timeline : repères des résultats, zones hors ligne, curseur de lecture.
function timeline(dur, ticks, clips, go) {
  const cursor = h('div', { class: 'cursor', hidden: '' });
  const el = h('div', { class: 'timeline', title: 'Cliquer pour lire à partir de ce moment', onclick: e => { const r = el.getBoundingClientRect(); go(dur * (e.clientX - r.left) / r.width + 1); } },
    clips.map(c => h('div', { class: 'offline', style: `left:${100 * c.start / dur}%;width:${100 * (c.end - c.start) / dur}%`, title: 'Disponible hors ligne' })),
    ticks.map(t => h('div', { class: 'tick', style: `left:${100 * t / dur}%`, title: fmt(t), onclick: e => { e.stopPropagation(); go(t); } })),
    cursor);
  el.addClip = c => el.prepend(h('div', { class: 'offline', style: `left:${100 * c.start / dur}%;width:${100 * (c.end - c.start) / dur}%` }));
  el.setTime = t => { cursor.hidden = false; cursor.style.left = `${100 * Math.min(1, t / dur)}%`; };
  return el;
}
