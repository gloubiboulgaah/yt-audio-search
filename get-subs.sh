#!/usr/bin/env bash
set -euo pipefail

command -v yt-dlp >/dev/null || { echo "yt-dlp manquant : brew install yt-dlp"; exit 1; }

read -rp "URL de la vidéo : " url
[ -n "$url" ] || { echo "URL vide"; exit 1; }

dir="$(cd "$(dirname "$0")" && pwd)/subtitles"
mkdir -p "$dir"

yt-dlp --write-subs --write-auto-subs --sub-langs "fr" --sub-format vtt \
  --skip-download -o "$dir/%(id)s.%(ext)s" "$url"

# Sous-titres auto YouTube = texte "déroulant" : chaque bloc répète la ligne précédente.
# On garde uniquement la nouvelle ligne de chaque bloc -> fichier .txt "timecode<TAB>texte".
for vtt in "$dir"/*.vtt; do
  auto=0; grep -q '<c>' "$vtt" && auto=1
  awk -v auto="$auto" '
    function ms(t, a) { split(t, a, /[:.]/); return ((a[1]*60 + a[2])*60 + a[3])*1000 + a[4] }  # entiers: awk FR lit "00.990" comme 0
    function flush() {
      if (start != "" && (auto ? (dur > 50 && last != "") : text != ""))
        print substr(start, 1, 8) "\t" (auto ? last : text)
      start = ""; last = ""; text = ""
    }
    /-->/ { flush(); start = $1; dur = ms($3) - ms($1); next }
    start != "" && NF > 0 {
      gsub(/<[^>]*>/, ""); sub(/^ +/, ""); last = $0
      text = (text == "" ? $0 : text " " $0)
    }
    END { flush() }
  ' "$vtt" > "${vtt%.vtt}.txt"
done

echo "Fichiers dans $dir :"
ls "$dir"
