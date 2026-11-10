"""Sauvegarde / restauration de data.db + fichiers texte des sous-titres (pas les vidéos téléchargées). Stdlib uniquement : marche sans .venv.
python3 backup.py save | restore [fichier.zip] | reset   (sans argument : menu)"""
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data.db"
# Hors du dossier du projet, pour survivre à une réinstallation.
OUT = Path.home() / "audio-search-sauvegardes"


def copy_db(src, dst):
    # API backup de SQLite : copie cohérente même avec le WAL ou l'appli ouverte.
    s, d = sqlite3.connect(src), sqlite3.connect(dst)
    try:
        s.backup(d)
    finally:  # fermer explicitement, sinon Windows bloque la suppression du dossier temporaire
        s.close()
        d.close()


def sub_files():
    """Dossier des sous-titres (réglable dans Paramètres) et nos fichiers dedans, d'après data.db."""
    sub, ids = ROOT / "subtitles", []
    if DB.exists():
        c = sqlite3.connect(DB)
        try:
            ids = [r[0] for r in c.execute("SELECT id FROM videos")]
            sub = Path((c.execute("SELECT value FROM settings WHERE key='subs_dir'").fetchone() or [sub])[0])
        except sqlite3.Error:
            pass
        finally:
            c.close()
    # Le dossier peut être partagé avec d'autres fichiers : on ne touche qu'aux <id>.<langue>.txt connus.
    files = [f for f in sub.glob("*.txt") if f.name.split(".")[0] in ids] if sub.exists() else []
    return sub, files


def save():
    OUT.mkdir(exist_ok=True)
    zpath = OUT / f"audio-search-{time.strftime('%Y-%m-%d_%H-%M-%S')}.zip"
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        if DB.exists():
            copy_db(DB, Path(tmp) / "data.db")
            z.write(Path(tmp) / "data.db", "data.db")
        for f in sub_files()[1]:
            z.write(f, f"subtitles/{f.name}")
    print(f"Sauvegarde créée : {zpath}")
    return zpath


def restore(zpath=None):
    if zpath is None:
        found = sorted(OUT.glob("audio-search-*.zip"))
        if not found:
            sys.exit(f"Aucune sauvegarde trouvée dans {OUT}")
        zpath = found[-1]
    zpath = Path(zpath)
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        # Refuse tout fichier inattendu (chemins ../, absolus...) avant de toucher aux données.
        bad = [n for n in names if n != "data.db" and not (n.startswith("subtitles/") and "/" not in n[10:] and ".." not in n and len(n) > 10)]
        if bad or "data.db" not in names:
            sys.exit(f"{zpath} n'est pas une sauvegarde valide ({bad or 'data.db manquant'})")
        if DB.exists():
            print("Données actuelles mises de côté d'abord :")
            save()
        for f in sub_files()[1]:
            f.unlink()
        with tempfile.TemporaryDirectory() as tmp:
            z.extract("data.db", tmp)
            copy_db(Path(tmp) / "data.db", DB)
        sub = sub_files()[0]  # dossier choisi dans la sauvegarde restaurée
        sub.mkdir(parents=True, exist_ok=True)
        for n in names:
            if n.startswith("subtitles/"):
                (sub / n[10:]).write_bytes(z.read(n))
    print(f"Restauré depuis : {zpath}")


def reset():
    if DB.exists():
        print("Données actuelles mises de côté d'abord :")
        save()
    for f in [*sub_files()[1], DB, ROOT / "data.db-wal", ROOT / "data.db-shm"]:
        f.unlink(missing_ok=True)
    print("Appli remise à zéro (relancer l'appli pour repartir d'une base vide).")


if __name__ == "__main__":
    arg = sys.argv[1:]
    if not arg:
        print(f"Sauvegardes dans : {OUT}\n1) Sauvegarder\n2) Restaurer la plus récente\n3) Restaurer un fichier précis\n4) Tout réinitialiser (une sauvegarde est faite avant)")
        c = input("Choix : ").strip()
        arg = {"1": ["save"], "2": ["restore"]}.get(c) or (["restore", input("Chemin du .zip (glisser-déposer) : ").strip().strip("'\"").replace("\\ ", " ")] if c == "3" else [])
        if c == "4":
            arg = ["reset"] if input("Effacer toutes les vidéos et signets ? (oui/non) : ").strip().lower() in ("o", "oui", "y", "yes") else []
    if arg[:1] == ["save"]:
        save()
    elif arg[:1] == ["restore"]:
        restore(arg[1] if len(arg) > 1 else None)
    elif arg[:1] == ["reset"]:
        reset()
    elif not arg:
        print("Annulé.")
    else:
        sys.exit(__doc__)
