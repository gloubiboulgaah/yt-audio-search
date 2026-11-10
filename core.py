import html
import json
import re
import shutil
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz, process

ROOT = Path(__file__).resolve().parent
DEFAULT_SUB = ROOT / "subtitles"
DEFAULT_VIDEOS = ROOT / "videos"
SUB = DEFAULT_SUB  # remplacé par load_settings() / save_settings()
DB = ROOT / "data.db"

_lock = threading.Lock()
_vocab = {"version": -1, "list": [], "set": set()}
_version = [0]
_schema = [None]


def db():
    c = sqlite3.connect(DB, timeout=30)
    if _schema[0] != DB:
        _schema[0] = DB
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS videos(id TEXT PRIMARY KEY, title TEXT, url TEXT, duration REAL, lang TEXT, added REAL, nwords INTEGER);
        CREATE TABLE IF NOT EXISTS words(video_id TEXT, wi INTEGER, t REAL, text TEXT, PRIMARY KEY(video_id, wi)) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS tokens(video_id TEXT, pos INTEGER, wi INTEGER, t REAL, norm TEXT);
        CREATE INDEX IF NOT EXISTS tokens_norm ON tokens(norm, video_id);
        CREATE INDEX IF NOT EXISTS tokens_video ON tokens(video_id);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS bookmarks(id INTEGER PRIMARY KEY, video_id TEXT, start REAL, end REAL, text TEXT, category_id INTEGER, added REAL);
        CREATE TABLE IF NOT EXISTS clips(id INTEGER PRIMARY KEY, video_id TEXT, start REAL, end REAL, path TEXT, added REAL);
        """)
        cols = [r[1] for r in c.execute("PRAGMA table_info(videos)")]
        for col in ("upload_date", "meta"):
            if col not in cols:
                c.execute(f"ALTER TABLE videos ADD COLUMN {col} TEXT")
    return c


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower().replace("œ", "oe").replace("æ", "ae"))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.findall(r"[^\W_]+", s)


def secs(s):
    p = s.strip().split(":")
    return sum(float(x) * 60 ** i for i, x in enumerate(reversed(p)))


def parse_vtt(text):
    text = text.replace("\r", "")
    auto = "<c>" in text
    lines, prev = [], None
    for block in re.split(r"\n\n+", text):
        rows = block.split("\n")
        i = next((k for k, r in enumerate(rows) if "-->" in r), None)
        if i is None:
            continue
        a, _, b = rows[i].partition("-->")
        start, end = secs(a), secs(b.split()[0])
        body = [r for r in rows[i + 1:] if r.strip()]
        if not body:
            continue
        words = []
        if auto:
            if end - start <= 0.05:
                continue
            raw = body[-1]
            plain = " ".join(html.unescape(re.sub(r"<[^>]+>", "", raw)).split())
            if plain == prev:
                continue
            prev = plain
            t = start
            for k, part in enumerate(re.split(r"<(\d[\d:.]*)>", raw)):
                if k % 2:
                    t = secs(part)
                    continue
                words += [(t, w) for w in html.unescape(re.sub(r"<[^>]+>", "", part)).split()]
        else:
            ws = html.unescape(re.sub(r"<[^>]+>", "", " ".join(body))).split()
            words = [(start + (end - start) * k / len(ws), w) for k, w in enumerate(ws)]
        if words:
            lines.append(words)
    return lines


def hms(t):
    t = int(t)
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def index_lines(vid, lines, title, url, duration, lang, upload_date=None, meta=None):
    words = [w for line in lines for w in line]
    wrows, trows, pos = [], [], 0
    for wi, (t, w) in enumerate(words):
        wrows.append((vid, wi, t, w))
        for n in norm(w):
            trows.append((vid, pos, wi, t, n))
            pos += 1
    duration = duration or (words[-1][0] + 5 if words else 0)
    with _lock, db() as c:
        c.execute("DELETE FROM videos WHERE id=?", (vid,))
        c.execute("DELETE FROM words WHERE video_id=?", (vid,))
        c.execute("DELETE FROM tokens WHERE video_id=?", (vid,))
        c.execute("INSERT INTO videos(id, title, url, duration, lang, added, nwords, upload_date, meta) VALUES(?,?,?,?,?,?,?,?,?)",
                  (vid, title or vid, url, duration, lang, time.time(), len(words), upload_date, json.dumps(meta) if meta else None))
        c.executemany("INSERT INTO words VALUES(?,?,?,?)", wrows)
        c.executemany("INSERT INTO tokens VALUES(?,?,?,?,?)", trows)
        _version[0] += 1


def index_file(path, vid, title=None, duration=None, lang="fr", url=None, upload_date=None, meta=None):
    path = Path(path)
    lines = parse_vtt(path.read_text(encoding="utf-8", errors="replace"))
    index_lines(vid, lines, title, url or f"https://www.youtube.com/watch?v={vid}", duration, lang, upload_date, meta)
    write_txt(vid, "".join(f"{hms(l[0][0])}\t{' '.join(w for _, w in l)}\n" for l in lines), path.with_suffix(".txt"))
    path.unlink()


def txt_file(vid):
    return next(iter(sorted(SUB.glob(f"{glob_escape(vid)}.*.txt"))), None)


def write_txt(vid, body=None, path=None):
    """Réécrit le fichier texte : en-tête « # » (source, signets, téléchargements) + sous-titres."""
    path = path or txt_file(vid)
    if path is None:
        return
    if body is None:
        body = "".join(l for l in path.read_text(encoding="utf-8").splitlines(True) if not l.startswith("#"))
    with db() as c:
        c.row_factory = sqlite3.Row
        v = c.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
        bms = c.execute("SELECT b.start, b.end, b.text, k.name FROM bookmarks b LEFT JOIN categories k ON k.id=b.category_id WHERE video_id=? ORDER BY start", (vid,)).fetchall()
        cls = c.execute("SELECT start, end, path FROM clips WHERE video_id=? ORDER BY start", (vid,)).fetchall()
    d = v["upload_date"]
    head = [
        f"Titre : {v['title']}",
        f"Lien : {v['url']}",
        f"Chaîne : {json.loads(v['meta'] or '{}').get('channel') or 'inconnue'}",
        f"Date de publication : {d[:4]}-{d[4:6]}-{d[6:]}" if d else "Date de publication : inconnue",
        f"Durée : {hms(v['duration'] or 0)}",
        f"Ajoutée le : {time.strftime('%Y-%m-%d %H:%M', time.localtime(v['added']))}",
        f"Langue : {v['lang']}",
        f"Signets ({len(bms)}) :",
        *(f"  [{b['name'] or 'Sans catégorie'}] {hms(b['start'])} → {hms(b['end'])} : {b['text']}" for b in bms),
        f"Téléchargements ({len(cls)}) :",
        *(f"  {hms(c['start'])} → {hms(c['end'])} : {c['path']}" for c in cls),
    ]
    path.write_text("".join(f"# {l}\n" for l in head) + "#\n" + body, encoding="utf-8")


def video(vid):
    with db() as c:
        c.row_factory = sqlite3.Row
        r = c.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
    if not r:
        return None
    v = dict(r)
    v["meta"] = json.loads(v["meta"] or "{}")
    return v


def set_meta(vid, upload_date, meta):
    with db() as c:
        c.execute("UPDATE videos SET upload_date=?, meta=? WHERE id=?", (upload_date, json.dumps(meta), vid))
    write_txt(vid)


def is_full(cl, duration):
    """Id d'un fichier qui couvre toute la vidéo (à 2 s près à la fin)."""
    return covering(cl, 0, max(0, (duration or 0) - 2))


def words(vid):
    with db() as c:
        return c.execute("SELECT t, text FROM words WHERE video_id=? ORDER BY wi", (vid,)).fetchall()


# --- Paramètres ---

def setting(key, default):
    with db() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r[0] if r else default


QUALITIES = ("best", "1080", "720", "480", "360", "audio")


def settings():
    return {"subs_dir": setting("subs_dir", str(DEFAULT_SUB)), "videos_dir": setting("videos_dir", str(DEFAULT_VIDEOS)), "quality": setting("quality", "best")}


def load_settings():
    global SUB
    SUB = Path(settings()["subs_dir"])


def save_settings(subs_dir, videos_dir, quality="best"):
    global SUB
    if quality not in QUALITIES:
        raise ValueError(f"Qualité inconnue : {quality}")
    new, vids = Path(subs_dir).expanduser(), Path(videos_dir).expanduser()
    for p in (new, vids):
        if not p.is_absolute():
            raise ValueError(f"Il faut un chemin complet : {p}")
        p.mkdir(parents=True, exist_ok=True)
    if new.resolve() != SUB.resolve():
        # On ne déplace que nos fichiers : le dossier choisi peut contenir autre chose.
        for v in list_videos():
            for f in SUB.glob(f"{glob_escape(v['id'])}.*.txt"):
                shutil.move(str(f), str(new / f.name))
        SUB = new
    with db() as c:
        c.executemany("INSERT OR REPLACE INTO settings VALUES(?,?)", [("subs_dir", str(new)), ("videos_dir", str(vids)), ("quality", quality)])


# --- Signets ---

def categories():
    with db() as c:
        return [{"id": i, "name": n, "count": k} for i, n, k in c.execute(
            "SELECT k.id, k.name, COUNT(b.id) FROM categories k LEFT JOIN bookmarks b ON b.category_id=k.id GROUP BY k.id ORDER BY k.name COLLATE NOCASE")]


def add_category(name):
    name = name.strip()
    if not name:
        raise ValueError("Nom vide")
    with db() as c:
        c.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (name,))
        return c.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone()[0]


def _category_videos(cid):
    with db() as c:
        vids = [r[0] for r in c.execute("SELECT DISTINCT video_id FROM bookmarks WHERE category_id=?", (cid,))]
    return vids


def rename_category(cid, name):
    if not name.strip():
        raise ValueError("Nom vide")
    with db() as c:
        c.execute("UPDATE categories SET name=? WHERE id=?", (name.strip(), cid))
    for vid in _category_videos(cid):
        write_txt(vid)


def delete_category(cid):
    vids = _category_videos(cid)
    with db() as c:
        c.execute("UPDATE bookmarks SET category_id=NULL WHERE category_id=?", (cid,))
        c.execute("DELETE FROM categories WHERE id=?", (cid,))
    for vid in vids:
        write_txt(vid)


def list_bookmarks(vid=None):
    with db() as c:
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT b.*, v.title, v.url, v.duration, k.name AS category FROM bookmarks b JOIN videos v ON v.id=b.video_id "
            "LEFT JOIN categories k ON k.id=b.category_id" + (" WHERE b.video_id=? ORDER BY b.start" if vid else " ORDER BY b.added DESC"), (vid,) if vid else ())]
    cl = clips()
    for b in rows:
        b["clip"] = covering(cl.get(b["video_id"], []), b["start"], b["end"])
        b["clips"] = cl.get(b["video_id"], [])
    return rows


def add_bookmark(vid, start, end, text, category_id=None):
    with db() as c:
        bid = c.execute("INSERT INTO bookmarks(video_id, start, end, text, category_id, added) VALUES(?,?,?,?,?,?)",
                        (vid, float(start), float(end), text, category_id, time.time())).lastrowid
    write_txt(vid)
    return bid


def _bookmark_video(bid):
    with db() as c:
        r = c.execute("SELECT video_id FROM bookmarks WHERE id=?", (bid,)).fetchone()
    return r and r[0]


def move_bookmark(bid, category_id):
    with db() as c:
        c.execute("UPDATE bookmarks SET category_id=? WHERE id=?", (category_id, bid))
    if vid := _bookmark_video(bid):
        write_txt(vid)


def delete_bookmark(bid):
    vid = _bookmark_video(bid)
    with db() as c:
        c.execute("DELETE FROM bookmarks WHERE id=?", (bid,))
    if vid:
        write_txt(vid)


# --- Vidéos / extraits téléchargés ---

def clips(vid=None):
    """{video_id: [clip, ...]} des fichiers encore présents sur le disque."""
    with db() as c:
        rows = c.execute("SELECT id, video_id, start, end, path FROM clips" + (" WHERE video_id=?" if vid else "") + " ORDER BY end - start DESC", (vid,) if vid else ()).fetchall()
    out = {}
    for i, v, a, b, p in rows:
        if Path(p).exists():
            out.setdefault(v, []).append({"id": i, "start": a, "end": b, "path": p})
    return out


def clip(cid):
    with db() as c:
        r = c.execute("SELECT id, video_id, start, end, path FROM clips WHERE id=?", (cid,)).fetchone()
    return r and dict(zip(("id", "video_id", "start", "end", "path"), r))


def covering(cl, a, b):
    """Id du premier extrait téléchargé qui contient tout le passage [a, b]."""
    return next((c["id"] for c in cl if c["start"] - 0.05 <= a and b <= c["end"] + 0.05), None)


def add_clip(vid, start, end, path):
    with db() as c:
        c.execute("DELETE FROM clips WHERE path=?", (str(path),))
        cid = c.execute("INSERT INTO clips(video_id, start, end, path, added) VALUES(?,?,?,?,?)", (vid, start, end, str(path), time.time())).lastrowid
    write_txt(vid)
    return cid


def clip_vtt(vid, start, end):
    """Sous-titres WebVTT recalés sur le début de l'extrait."""
    with db() as c:
        ws = c.execute("SELECT t, text FROM words WHERE video_id=? AND t>=? AND t<? ORDER BY wi", (vid, start, end)).fetchall()
    ts = lambda x: f"{hms(x)}.{int(round(x % 1 * 1000)) % 1000:03d}"
    out = ["WEBVTT", ""]
    for i in range(0, len(ws), 8):
        g = ws[i:i + 8]
        b = ws[i + 8][0] if i + 8 < len(ws) else end
        out += [f"{ts(g[0][0] - start)} --> {ts(min(b, end) - start)}", " ".join(w for _, w in g), ""]
    return "\n".join(out)


def has_video(vid):
    with db() as c:
        return c.execute("SELECT 1 FROM videos WHERE id=?", (vid,)).fetchone() is not None


def list_videos():
    with db() as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute("SELECT * FROM videos ORDER BY added DESC")]


def delete_video(vid):
    with _lock, db() as c:
        c.execute("DELETE FROM videos WHERE id=?", (vid,))
        c.execute("DELETE FROM words WHERE video_id=?", (vid,))
        c.execute("DELETE FROM tokens WHERE video_id=?", (vid,))
        c.execute("DELETE FROM bookmarks WHERE video_id=?", (vid,))
        c.execute("DELETE FROM clips WHERE video_id=?", (vid,))  # les fichiers vidéo restent sur le disque
        _version[0] += 1
    for f in SUB.glob(f"{glob_escape(vid)}.*"):
        f.unlink()


def glob_escape(s):
    return re.sub(r"([\[\]*?])", r"[\1]", s)


def vocab():
    if _vocab["version"] != _version[0]:
        with db() as c:
            v = [r[0] for r in c.execute("SELECT DISTINCT norm FROM tokens")]
        _vocab.update(version=_version[0], list=v, set=set(v))
    return _vocab


def expand(tok, prefix, exact, tol, partial):
    V = vocab()
    out = {}
    if prefix:
        out.update({v: 100.0 for v in V["list"] if v.startswith(tok)})
    if not exact and tol < 100:
        scorer = fuzz.partial_ratio if partial else fuzz.ratio
        for v, s, _ in process.extract(tok, V["list"], scorer=scorer, score_cutoff=tol, limit=None):
            if partial and len(v) < len(tok) - 1:
                continue
            out[v] = max(out.get(v, 0), s)
    elif partial and not exact:
        out.update({v: 100.0 for v in V["list"] if tok in v})
    if tok in V["set"]:
        out[tok] = 100.0
    return out


def parse_query(q, mode):
    terms, neg = [], []
    for m in re.finditer(r'(-?)"([^"]*)"|(-?)(\S+)', q):
        quoted = m.group(2) is not None
        minus = m.group(1) if quoted else m.group(3)
        raw = m.group(2) if quoted else m.group(4)
        toks = norm(raw)
        if not toks:
            continue
        term = [{"tok": t, "prefix": False, "exact": quoted} for t in toks]
        if not quoted and raw.endswith("*"):
            term[-1]["prefix"] = True
        (neg if minus else terms).append({"toks": term, "quoted": quoted})
    if mode == "phrase" and len(terms) > 1:
        terms = [{"toks": [t for term in terms for t in term["toks"]], "quoted": False}]
    return terms, neg


def occurrences(P, sorted_pos, exps, gap):
    res = []
    for pos in sorted_pos:
        n, t, wi = P[pos]
        if n not in exps[0]:
            continue
        cur, ps, sc = pos, [pos], exps[0][n]
        for e in exps[1:]:
            nxt = next((p for p in range(cur + 1, cur + 2 + gap) if p in P and P[p][0] in e), None)
            if nxt is None:
                break
            ps.append(nxt)
            sc += e[P[nxt][0]]
            cur = nxt
        else:
            res.append({"t": t, "pos": ps, "score": sc / len(exps)})
    return res


def combine(occs, mode, window):
    if mode == "any" or len(occs) == 1 or window <= 0:
        hits = [o for oc in occs for o in oc]
    else:
        anchor = min(range(len(occs)), key=lambda i: len(occs[i]))
        hits = []
        for a in occs[anchor]:
            group = [a]
            for i, oc in enumerate(occs):
                if i == anchor:
                    continue
                best = min(oc, key=lambda o: abs(o["t"] - a["t"]))
                if abs(best["t"] - a["t"]) > window:
                    break
                group.append(best)
            else:
                hits.append({"t": min(g["t"] for g in group), "pos": sorted({p for g in group for p in g["pos"]}), "score": sum(g["score"] for g in group) / len(group)})
    seen, out = set(), []
    for h in sorted(hits, key=lambda h: (h["t"], -h["score"])):
        k = tuple(h["pos"])
        if k not in seen:
            seen.add(k)
            out.append(h)
    return out


def search(q, mode="all", tol=85, window=30, gap=1, partial=False, videos=None, sort="score", limit=0, context=10):
    terms, neg = parse_query(q, mode)
    if not terms:
        return {"results": [], "total_hits": 0, "expansions": {}}
    allterms = terms + neg
    for term in allterms:
        for t in term["toks"]:
            t["exp"] = expand(t["tok"], t["prefix"], t["exact"], tol, partial)
    keys = list({k for term in allterms for t in term["toks"] for k in t["exp"]})
    with db() as c:
        sql = "SELECT video_id, pos, t, wi, norm FROM tokens WHERE norm IN (SELECT value FROM json_each(?))"
        args = [json.dumps(keys)]
        if videos:
            sql += " AND video_id IN (SELECT value FROM json_each(?))"
            args.append(json.dumps(videos))
        per = {}
        for vid, pos, t, wi, n in c.execute(sql, args):
            per.setdefault(vid, {})[pos] = (n, t, wi)
        bms = {(v, round(a, 2)): i for i, v, a in c.execute("SELECT id, video_id, start FROM bookmarks")}
        cl = clips()
        results = []
        for vid, P in per.items():
            sp = sorted(P)
            if any(occurrences(P, sp, [t["exp"] for t in term["toks"]], 0 if term["quoted"] else gap) for term in neg):
                continue
            occs = [occurrences(P, sp, [t["exp"] for t in term["toks"]], 0 if term["quoted"] else gap) for term in terms]
            if mode != "any" and not all(occs):
                continue
            hits = combine([o for o in occs if o], mode, window)
            if not hits:
                continue
            for h in hits:
                wis = {P[p][2] for p in h["pos"]}
                hi = max(wis) + context
                rows = c.execute("SELECT wi, text, t FROM words WHERE video_id=? AND wi BETWEEN ? AND ? ORDER BY wi", (vid, min(wis) - context, hi + 1)).fetchall()
                nxt = rows.pop() if rows[-1][0] == hi + 1 else None  # mot suivant = fin de la citation
                h["quote"] = [[w, wi in wis, t] for wi, w, t in rows]
                h["end"] = nxt[2] if nxt else rows[-1][2] + 2
                ts = [P[p][1] for p in h["pos"]]
                h["clip"] = covering(cl.get(vid, []), min(ts), max(ts))
                h["bookmark"] = bms.get((vid, round(rows[0][2], 2)))
                del h["pos"]
            results.append({"id": vid, "hits": hits, "score": sum(h["score"] for h in hits), "clips": cl.get(vid, [])})
        meta = {r[0]: r for r in c.execute("SELECT id, title, url, duration, added, upload_date, json_extract(meta, '$.channel') FROM videos")}
    for r in results:
        m = meta.get(r["id"]) or (r["id"], r["id"], "", 0, 0, None, None)
        r.update(title=m[1], url=m[2], duration=m[3], added=m[4], upload_date=m[5], channel=m[6], full=is_full(r["clips"], m[3]))
    key = {"score": lambda r: -r["score"], "hits": lambda r: -len(r["hits"]), "recent": lambda r: -r["added"], "title": lambda r: r["title"].lower()}.get(sort, lambda r: -r["score"])
    results.sort(key=key)
    if limit:
        results = results[:limit]
    expansions = {t["tok"]: sorted(t["exp"], key=lambda k: -t["exp"][k])[:30] for term in terms for t in term["toks"]}
    return {"results": results, "total_hits": sum(len(r["hits"]) for r in results), "expansions": expansions}
