import json
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from pathlib import Path

import imageio_ffmpeg
from flask import Flask, abort, jsonify, redirect, request, send_file, send_from_directory
from yt_dlp import YoutubeDL
from yt_dlp.utils import download_range_func

import core

PORT = 8765
app = Flask(__name__, static_folder="static")
jobs = {}


def find_vtt(vid):
    return next(iter(sorted(core.SUB.glob(f"{core.glob_escape(vid)}.*.vtt"))), None)


def fetch(entries, job, lang):
    opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [lang],
        "subtitlesformat": "vtt",
        "outtmpl": str(core.SUB / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    with YoutubeDL(opts) as y:
        for e in entries:
            vid = e.get("id")
            job["current"] = e.get("title") or vid
            try:
                if not vid:
                    raise ValueError("entrée sans id")
                if core.has_video(vid) and not e.get("reimport"):
                    job["skipped"] += 1
                    continue
                f = find_vtt(vid)
                try:
                    info = y.extract_info(e.get("webpage_url") or e.get("url") or f"https://www.youtube.com/watch?v={vid}", download=f is None)
                except Exception:
                    if not f:
                        raise
                    info = {}
                f = f or find_vtt(vid)
                if not f:
                    raise ValueError(f"pas de sous-titres « {lang} »")
                core.index_file(f, vid, info.get("title"), info.get("duration"), f.name.split(".")[-2], info.get("webpage_url"), info.get("upload_date"), meta_of(info))
                job["done"] += 1
            except Exception as ex:
                job["errors"].append(f"{e.get('title') or vid}: {ex}")
    job["current"] = None


def run_job(job, url, lang):
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": "in_playlist"}) as y:
            info = y.extract_info(url, download=False)
        entries = [e for e in (info.get("entries") or [info]) if e]
        job["total"] = len(entries)
        fetch(entries, job, lang)
    except Exception as ex:
        job["errors"].append(str(ex))
    job["finished"] = True


META = ("channel", "channel_url", "uploader", "view_count", "like_count", "comment_count", "channel_follower_count",
        "categories", "tags", "description", "thumbnail")


def meta_of(info):
    return {k: info[k] for k in META if info.get(k) is not None} or None


def refresh_meta(vid, y=None):
    v = core.video(vid)
    info = (y or YoutubeDL({"quiet": True, "no_warnings": True})).extract_info(v["url"], download=False, process=False)
    core.set_meta(vid, info.get("upload_date") or v["upload_date"], {**v["meta"], **(meta_of(info) or {})})


def safe(s):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s).strip(" .")[:100] or "video"


def stamp(t):
    return f"{core.hms(t).replace(':', '-')}.{int(t * 10) % 10}"


QUALITY_LABEL = {"best": "meilleure qualité", "1080": "1080p", "720": "720p", "480": "480p", "360": "360p", "audio": "audio seul"}


def fmt_for(q):
    """Sélecteur yt-dlp : mp4 h264/aac d'abord (lisible dans le navigateur), plafonné à la hauteur choisie."""
    if q == "audio":
        return "ba[ext=m4a]/ba/b"
    cap = "" if q == "best" else f"[height<={q}]"
    return f"bv*{cap}[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/b{cap}[ext=mp4]/bv*{cap}+ba/b{cap}/b"


def run_clip(job, vid, start, end, quality):
    """Télécharge la vidéo entière (end None) ou l'extrait [start, end] dans videos/<titre [id]>/."""
    sizes = {}

    def progress(d):
        # Vidéo entière : octets reçus (vidéo puis audio). Extrait : ffmpeg ne donne rien avant la fin.
        if d["status"] == "downloading" and (tot := d.get("total_bytes") or d.get("total_bytes_estimate")):
            sizes[d["info_dict"].get("format_id")] = (d.get("downloaded_bytes") or 0, tot)
            job.update(done_bytes=sum(a for a, _ in sizes.values()), total_bytes=sum(b for _, b in sizes.values()), phase="Téléchargement")
            job["progress"] = job["done_bytes"] / job["total_bytes"]

    def post(d):
        if d["status"] == "started" and d["postprocessor"] == "Merger":
            job.update(phase="Assemblage audio + vidéo", progress=None)

    try:
        v = core.video(vid)
        full = end is None
        root = Path(core.settings()["videos_dir"])
        # Un seul dossier par vidéo : on réutilise celui qui finit par [id], même si le titre a changé.
        folder = next((d for d in root.glob("*" + core.glob_escape(f"[{vid}]")) if d.is_dir()), None) \
            or root / safe(f"{v['title'][:80]} [{vid}]")  # titre coupé : limite de 260 caractères des chemins Windows
        name = safe(v["title"][:40]) + (" [complet]" if full else f" [{stamp(start)} - {stamp(end)}]") + ("" if quality == "best" else f" [{quality if quality == 'audio' else quality + 'p'}]")
        opts = {
            "format": fmt_for(quality),
            "merge_output_format": "mp4",
            "outtmpl": str(folder / f"{name}.%(ext)s"),
            "ffmpeg_location": shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe(),
            "quiet": True, "no_warnings": True, "noprogress": True,
            "progress_hooks": [progress], "postprocessor_hooks": [post],
        }
        if not full:
            opts.update(download_ranges=download_range_func(None, [(start, end)]), force_keyframes_at_cuts=True)
        with YoutubeDL(opts) as y:
            info = y.extract_info(v["url"], download=True)
        path = Path(info["requested_downloads"][0]["filepath"])
        if full:
            start, end = 0, info.get("duration") or v["duration"]
        path.with_suffix(".vtt").write_text(core.clip_vtt(vid, start, end), encoding="utf-8")
        job["clip"] = core.clip(core.add_clip(vid, start, end, path))
    except Exception as ex:
        job["errors"].append(str(ex))
    job.update(finished=True, finished_at=time.time())


def import_existing():
    core.SUB.mkdir(exist_ok=True)
    entries = [{"id": f.name.split(".")[0], "reimport": True} for f in core.SUB.glob("*.vtt")]
    if entries:
        job = jobs.setdefault("import", {"total": len(entries), "done": 0, "skipped": 0, "errors": [], "finished": False, "current": None})
        fetch(entries, job, "fr")
        job["finished"] = True


def backfill():
    """Anciennes vidéos : récupère date, chaîne, vues… et met à jour l'en-tête des fichiers texte."""
    y = YoutubeDL({"quiet": True, "no_warnings": True})
    for v in core.list_videos():
        if not v["meta"]:
            try:
                refresh_meta(v["id"], y)
            except Exception:
                pass  # hors ligne ou vidéo retirée : on réessaiera au prochain lancement


@app.get("/")
def home():
    return redirect("/search")


@app.get("/<page>")
def page(page):
    if page not in ("upload", "search", "files", "bookmarks", "settings", "video"):
        return "Not found", 404
    return send_from_directory("static", f"{page}.html")


@app.post("/api/download")
def download():
    d = request.get_json(force=True)
    url = (d.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return jsonify(error="URL invalide"), 400
    jid = uuid.uuid4().hex[:8]
    jobs[jid] = {"total": 0, "done": 0, "skipped": 0, "errors": [], "finished": False, "current": None, "url": url}
    threading.Thread(target=run_job, args=(jobs[jid], url, (d.get("lang") or "fr").strip()), daemon=True).start()
    return jsonify(id=jid)


@app.get("/api/jobs/<jid>")
def job(jid):
    return jsonify(jobs.get(jid) or {"error": "inconnu"})


@app.get("/api/videos")
def videos():
    cl = core.clips()
    out = []
    for v in core.list_videos():
        m = json.loads(v.pop("meta") or "{}")
        out.append({**v, "channel": m.get("channel"), "full": core.is_full(cl.get(v["id"], []), v["duration"]), "nclips": len(cl.get(v["id"], []))})
    return jsonify(out)


@app.get("/api/videos/<vid>")
def video_info(vid):
    v = core.video(vid)
    if not v:
        return jsonify(error="Vidéo inconnue"), 404
    cl = core.clips(vid).get(vid, [])
    for c in cl:
        c["name"], c["size"] = Path(c["path"]).name, Path(c["path"]).stat().st_size
    return jsonify({**v, "clips": sorted(cl, key=lambda c: c["start"]), "full": core.is_full(cl, v["duration"]), "bookmarks": core.list_bookmarks(vid), "txt": str(core.txt_file(vid) or "")})


@app.post("/api/videos/<vid>/refresh")
def video_refresh(vid):
    if not core.video(vid):
        return jsonify(error="Vidéo inconnue"), 404
    try:
        refresh_meta(vid)
    except Exception as ex:
        return jsonify(error=f"Impossible de joindre YouTube : {ex}"), 502
    return jsonify(ok=True)


@app.delete("/api/videos/<vid>")
def delete(vid):
    core.delete_video(vid)
    return jsonify(ok=True)


@app.get("/api/videos/<vid>/words")
def video_words(vid):
    return jsonify(core.words(vid))


@app.get("/api/settings")
def get_settings():
    return jsonify(core.settings())


@app.post("/api/settings")
def set_settings():
    d = request.get_json(force=True)
    try:
        core.save_settings(str(d["subs_dir"]), str(d["videos_dir"]), str(d.get("quality") or "best"))
    except (ValueError, OSError, KeyError) as ex:
        return jsonify(error=str(ex)), 400
    return jsonify(core.settings())


@app.post("/api/pick-folder")
def pick_folder():
    """Ouvre le sélecteur de dossier natif (l'appli tourne en local)."""
    if sys.platform == "darwin":
        cmd = ["osascript", "-e", 'POSIX path of (choose folder with prompt "Choisir un dossier")']
    elif sys.platform == "win32":
        cmd = ["powershell", "-NoProfile", "-STA", "-Command",
               "Add-Type -AssemblyName System.Windows.Forms; $d = New-Object System.Windows.Forms.FolderBrowserDialog; "
               "if ($d.ShowDialog((New-Object System.Windows.Forms.Form -Property @{TopMost=$true})) -eq 'OK') { $d.SelectedPath }"]
    else:
        cmd = ["zenity", "--file-selection", "--directory"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=600).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    return jsonify(path=out.rstrip("/\\") or None)


@app.get("/api/categories")
def get_categories():
    return jsonify(core.categories())


@app.post("/api/categories")
def new_category():
    try:
        return jsonify(id=core.add_category(str(request.get_json(force=True).get("name", ""))))
    except ValueError as ex:
        return jsonify(error=str(ex)), 400


@app.patch("/api/categories/<int:cid>")
def rename_category(cid):
    try:
        core.rename_category(cid, str(request.get_json(force=True).get("name", "")))
    except (ValueError, core.sqlite3.IntegrityError):
        return jsonify(error="Nom vide ou déjà utilisé"), 400
    return jsonify(ok=True)


@app.delete("/api/categories/<int:cid>")
def delete_category(cid):
    core.delete_category(cid)
    return jsonify(ok=True)


@app.get("/api/bookmarks")
def get_bookmarks():
    return jsonify(core.list_bookmarks())


@app.post("/api/bookmarks")
def new_bookmark():
    d = request.get_json(force=True)
    if not core.video(str(d.get("video_id"))):
        return jsonify(error="Vidéo inconnue"), 400
    return jsonify(id=core.add_bookmark(d["video_id"], d["start"], d["end"], str(d.get("text", "")), d.get("category_id")))


@app.patch("/api/bookmarks/<int:bid>")
def move_bookmark(bid):
    core.move_bookmark(bid, request.get_json(force=True).get("category_id"))
    return jsonify(ok=True)


@app.delete("/api/bookmarks/<int:bid>")
def delete_bookmark(bid):
    core.delete_bookmark(bid)
    return jsonify(ok=True)


@app.post("/api/clips")
def new_clip():
    d = request.get_json(force=True)
    vid = str(d.get("video_id"))
    if not core.video(vid):
        return jsonify(error="Vidéo inconnue"), 400
    start, end = (None, None) if d.get("full") else (max(0.0, float(d["start"])), float(d["end"]))
    if start is not None and end - start < 0.5:
        return jsonify(error="Extrait trop court"), 400
    quality = str(d.get("quality") or core.settings()["quality"])
    if quality not in core.QUALITIES:
        return jsonify(error="Qualité inconnue"), 400
    jid = uuid.uuid4().hex[:8]
    v = core.video(vid)
    jobs[jid] = {"kind": "clip", "id": jid, "video_id": vid, "title": v["title"], "errors": [], "finished": False, "clip": None, "progress": None,
                 "phase": "Préparation", "full": start is None, "started": time.time(), "finished_at": 0,
                 "label": ("Vidéo entière" if start is None else f"Extrait {core.hms(start)} → {core.hms(end)}") + ("" if quality == "best" else f", {QUALITY_LABEL[quality]}")}
    threading.Thread(target=run_clip, args=(jobs[jid], vid, start, end, quality), daemon=True).start()
    return jsonify(id=jid)


@app.get("/api/clip-jobs")
def clip_jobs():
    """Téléchargements en cours + terminés depuis moins d'une minute (pour les notifications de toutes les pages)."""
    now = time.time()
    return jsonify([{**j, "elapsed": (j["finished_at"] or now) - j["started"]} for j in jobs.values()
                    if j.get("kind") == "clip" and (not j["finished"] or now - j["finished_at"] < 60)])


def get_clip(cid):
    c = core.clip(cid)
    if not c or not Path(c["path"]).exists():
        abort(404)
    return c


@app.get("/api/clips/<int:cid>/file")
def clip_file(cid):
    return send_file(get_clip(cid)["path"], conditional=True)


@app.get("/api/clips/<int:cid>/vtt")
def clip_subs(cid):
    c = get_clip(cid)
    return core.clip_vtt(c["video_id"], c["start"], c["end"]), {"Content-Type": "text/vtt; charset=utf-8"}


@app.post("/api/clips/<int:cid>/reveal")
def reveal(cid):
    p = get_clip(cid)["path"]
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", p])
    elif sys.platform == "win32":
        subprocess.Popen(f'explorer /select,"{p}"')
    else:
        subprocess.Popen(["xdg-open", str(Path(p).parent)])
    return jsonify(ok=True)


@app.post("/api/search")
def search():
    d = request.get_json(force=True)
    return jsonify(core.search(
        str(d.get("q", "")),
        mode=d.get("mode", "all"),
        tol=max(0, min(100, float(d.get("tol", 85)))),
        window=float(d.get("window", 30)),
        gap=max(0, int(d.get("gap", 1))),
        partial=bool(d.get("partial")),
        videos=d.get("videos") or None,
        sort=d.get("sort", "score"),
        limit=max(0, int(d.get("limit", 0))),
        context=max(0, min(60, int(d.get("context", 10)))),
    ))


if __name__ == "__main__":
    core.load_settings()
    threading.Thread(target=lambda: (import_existing(), backfill()), daemon=True).start()
    threading.Timer(1, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}/search")).start()
    app.run(host="127.0.0.1", port=PORT, threaded=True)
