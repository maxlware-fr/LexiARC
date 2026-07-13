import os
import subprocess
import re
from pathlib import Path

MTOOLS_DIR = Path(r"C:\Users\maxlw\Downloads\mtools")
MFORMAT = MTOOLS_DIR / "mformat.exe"
MCOPY = MTOOLS_DIR / "mcopy.exe"
MMD = MTOOLS_DIR / "mmd.exe"

SRC_DIR = Path("core")
IMG_PATH = Path("sd_card.img")

def clean_name(path_str):
    """Remplace les caractères non-ASCII (chinois, accents) par des équivalents
    sûrs pour éviter que mtools ne freeze de désespoir."""
    # On garde les lettres, chiffres, slashes, backslashes, points et underscores
    cleaned = ""
    for char in path_str:
        if char.isalnum() and ord(char) < 128:
            cleaned += char
        elif char in ['/', '\\', '.', '_', '-']:
            cleaned += char
        else:
            # Remplace le caractère chinois par son code hex (ex: _u4e2d)
            cleaned += f"_u{ord(char):04x}"
    return cleaned

def run_cmd(args):
    try:
        subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        return True
    except subprocess.TimeoutExpired:
        print(f" [!] Timeout sur la commande : {' '.join(args)} (sauté)")
        return False
    except subprocess.CalledProcessError as e:
        if b"File exists" not in e.stderr:
            print(f" [!] Erreur commande {' '.join(args)} : {e.stderr.decode('utf-8', errors='replace').strip()}")
        return False

print("[*] Étape 1 : Création et formatage de l'image de 4 Go via mformat...")
run_cmd([str(MFORMAT), "-i", str(IMG_PATH), "-C", "-T", "8388608", "::"])

print("[*] Étape 2 : Parcours et copie avec nettoyage Unicode automatique...")
all_entries = sorted(list(SRC_DIR.rglob('*')))
total = len(all_entries)

for idx, entry in enumerate(all_entries, 1):
    rel_path = entry.relative_to(SRC_DIR)
    
    # On nettoie le chemin de destination pour mtools
    safe_rel_path = clean_name(str(rel_path))
    target_path = "::/" + safe_rel_path.replace("\\", "/")
    
    if idx % 50 == 0 or idx == total or "Classroom" in str(rel_path):
        print(f"[{idx}/{total}] Traitement : {rel_path} -> {safe_rel_path}")
    
    if entry.is_dir():
        run_cmd([str(MMD), "-i", str(IMG_PATH), target_path])
    elif entry.is_file():
        run_cmd([str(MCOPY), "-i", str(IMG_PATH), str(entry), target_path])

print("[+] Opération terminée ! L'image 'sd_card.img' a survécu aux caractères chinois.")