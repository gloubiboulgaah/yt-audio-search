# Audio-search

Recherche dans les sous-titres YouTube (vidéos et playlists).

1. Installer Python 3.10+ (https://www.python.org/downloads/, sous Windows cocher « Add Python to PATH »).
2. Mac : double-clic sur `start.command` (la 1re fois : clic droit > Ouvrir). Windows : double-clic sur `start.bat`.
3. Le navigateur s'ouvre sur http://127.0.0.1:8765.

Syntaxe de recherche : `mot`, `plusieurs mots`, `"phrase exacte"`, `préfixe*`, `-exclu` (exclut les vidéos qui contiennent le mot).
Pages :
- **Recherche** : sur chaque citation, l'icône signet l'enregistre dans une catégorie, l'icône téléchargement ouvre le choix de l'extrait (poignées sur la timeline ou timecodes, sous-titres affichés en direct). Le bouton « Télécharger… » de la vidéo permet aussi de la prendre en entier. Une coche verte = passage disponible hors ligne (clic : ouvre le dossier). Si YouTube ne répond pas ou que la vidéo a été retirée, la lecture se fait depuis le fichier téléchargé, avec ses sous-titres.
- **Signets** : catégories (créer, renommer, supprimer) et extraits enregistrés.
- **Vidéos** : liste des vidéos ; un clic ouvre leur fiche (chaîne, date, vues, j'aime, description, état hors ligne, citations enregistrées, fichiers téléchargés).
- **Paramètres** : dossier des fichiers texte des sous-titres, dossier des vidéos (par défaut `subtitles/` et `videos/`, un sous-dossier par vidéo) et qualité de téléchargement par défaut (de 360p à la meilleure, ou audio seul ; modifiable à chaque téléchargement).

Les téléchargements en cours s'affichent en bas à droite, sur toutes les pages, avec une barre de progression.

Chaque fichier texte commence par un en-tête `#` : titre, lien, date de publication, durée, signets et fichiers téléchargés.

Self-test : `.venv/bin/python test.py` (Windows : `.venv\Scripts\python test.py`).

Sauvegarde / restauration : fermer l'appli, puis double-clic sur `backup.command` (Mac) ou `backup.bat` (Windows). Les sauvegardes vont dans `audio-search-sauvegardes` du dossier utilisateur, donc elles survivent à une réinstallation : réinstaller, lancer `backup`, choisir « Restaurer ». Le choix « Tout réinitialiser » vide l'appli (après une sauvegarde automatique).
La sauvegarde ne contient pas les vidéos téléchargées (trop lourdes) : pour les garder lors d'une réinstallation, choisir dans Paramètres un dossier vidéos hors du dossier de l'appli, ou le copier à part.
