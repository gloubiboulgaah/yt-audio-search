import tempfile
from pathlib import Path

import core

AUTO = """WEBVTT
Kind: captions

00:00:15.000 --> 00:00:16.670 align:start position:0%
 
Coucou<00:00:15.440><c> la</c><00:00:15.719><c> team.</c>

00:00:16.670 --> 00:00:16.680 align:start position:0%
Coucou la team.
 

00:00:16.680 --> 00:00:18.349 align:start position:0%
Coucou la team.
Salut<00:00:17.039><c> !</c><00:00:17.359><c> J'espère</c><00:00:17.680><c> que</c><00:00:17.800><c> tout</c><00:00:18.000><c> le</c><00:00:18.160><c> monde</c>

00:00:18.349 --> 00:00:18.359 align:start position:0%
Salut ! J'espère que tout le monde
 

00:00:18.359 --> 00:00:19.189 align:start position:0%
Salut ! J'espère que tout le monde
va bien et j'ai peur.
"""

MANUAL = """WEBVTT

00:01:00.000 --> 00:01:04.000
Le <i>chat</i> mange &amp; dort

00:01:04.000 --> 00:01:06.000
la souris rouge
"""

tmp = Path(tempfile.mkdtemp())
core.DB, core.SUB = tmp / "t.db", tmp
lines = core.parse_vtt(AUTO)
assert [" ".join(w for _, w in l) for l in lines] == ["Coucou la team.", "Salut ! J'espère que tout le monde", "va bien et j'ai peur."], lines
assert lines[1][2] == (17.359, "J'espère"), lines[1]
m = core.parse_vtt(MANUAL)
assert [w for _, w in m[0]] == ["Le", "chat", "mange", "&", "dort"] and m[0][1][0] == 60.8, m
assert core.norm("J'espère Œuvre") == ["j", "espere", "oeuvre"]

(tmp / "aaa.fr.vtt").write_text(AUTO)
(tmp / "bbb.fr.vtt").write_text(MANUAL)
core.index_file(tmp / "aaa.fr.vtt", "aaa", "Vidéo A", 60)
core.index_file(tmp / "bbb.fr.vtt", "bbb", "Vidéo B", 120)
txt = (tmp / "aaa.fr.txt").read_text().splitlines()
assert txt[0] == "# Titre : Vidéo A" and "# Lien : https://www.youtube.com/watch?v=aaa" in txt, txt
assert [l for l in txt if not l.startswith("#")][1] == "00:00:16\tSalut ! J'espère que tout le monde", txt
assert not (tmp / "aaa.fr.vtt").exists()

S = lambda q, **k: {r["id"]: [round(h["t"], 2) for h in r["hits"]] for r in core.search(q, **k)["results"]}
assert S("espere", tol=100) == {"aaa": [17.36]}
assert S("esperre", tol=100) == {}
assert S("esperre", tol=80) == {"aaa": [17.36]}
assert S("PEUR") == {"aaa": [18.36]}
assert S('"tout monde"') == {}
assert S("tout monde", mode="phrase", gap=1) == {"aaa": [17.8]}
assert S("tout monde", mode="phrase", gap=0) == {}
assert S("chat souris", window=3) == {}
assert S("chat souris", window=10) == {"bbb": [60.8]}
assert S("chat souris", mode="any") == {"bbb": [60.8, 64.67]}
assert S("le -souris", tol=100) == {"aaa": [18.0]}
assert S("sour*", tol=100) == {"bbb": [64.67]}
assert S("espe", tol=100, partial=True) == {"aaa": [17.36]}
assert S("chat", videos=["aaa"]) == {}
q = core.search("tout le", tol=100)["results"][0]["hits"][0]["quote"]
assert [w for w, hl, t in q if hl] == ["tout", "le"], q

# Signets : en-tête du .txt mis à jour, marqués dans la recherche
cid = core.add_category("Drôle")
assert core.add_category(" Drôle ") == cid
hit = core.search("peur", tol=100)["results"][0]["hits"][0]
bid = core.add_bookmark("aaa", hit["quote"][0][2], hit["end"], "va bien et j'ai peur.", cid)
assert core.search("peur", tol=100)["results"][0]["hits"][0]["bookmark"] == bid
assert any("[Drôle]" in l and "peur" in l for l in (tmp / "aaa.fr.txt").read_text().splitlines())
core.rename_category(cid, "Triste")
assert "# Signets (1) :" in (tmp / "aaa.fr.txt").read_text() and "[Triste]" in (tmp / "aaa.fr.txt").read_text()
core.delete_category(cid)
assert core.list_bookmarks()[0]["category_id"] is None and "[Sans catégorie]" in (tmp / "aaa.fr.txt").read_text()

# Extraits : un mot trouvé dans un extrait téléchargé => dispo hors ligne
clipf = tmp / "clip.mp4"
clipf.write_bytes(b"x")
assert core.search("monde", tol=100)["results"][0]["hits"][0]["clip"] is None
k = core.add_clip("aaa", 16.0, 18.2, clipf)
assert core.search("monde", tol=100)["results"][0]["hits"][0]["clip"] == k  # monde à 18.16
assert core.search("peur", tol=100)["results"][0]["hits"][0]["clip"] is None  # peur à 18.36, hors extrait
assert core.list_bookmarks()[0]["clip"] is None
assert "Téléchargements (1)" in (tmp / "aaa.fr.txt").read_text() and str(clipf) in (tmp / "aaa.fr.txt").read_text()
vtt = core.clip_vtt("aaa", 16.0, 18.2)
assert vtt.startswith("WEBVTT") and "00:00:00.680 --> 00:00:02.200" in vtt and "Salut" in vtt, vtt
clipf.unlink()
assert core.clips() == {}  # fichier supprimé => plus hors ligne

# Changer le dossier des sous-titres déplace nos fichiers, pas les autres
(tmp / "autre.txt").write_text("à moi")
core.save_settings(str(tmp / "subs2"), str(tmp / "vids"), "720")
try:
    core.save_settings(str(tmp / "subs2"), str(tmp / "vids"), "8k")
    raise AssertionError("qualité invalide acceptée")
except ValueError:
    pass
assert (tmp / "subs2" / "bbb.fr.txt").exists() and not (tmp / "bbb.fr.txt").exists() and (tmp / "autre.txt").exists()
assert core.settings()["videos_dir"] == str(tmp / "vids") and core.settings()["quality"] == "720" and core.txt_file("bbb")
core.delete_video("aaa")
assert S("peur") == {} and not core.txt_file("aaa") and core.list_bookmarks() == []
print("ok")
