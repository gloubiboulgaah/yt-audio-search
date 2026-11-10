#!/bin/bash
cd "$(dirname "$0")"
python3 backup.py
read -p "Entrée pour fermer"
