# -*- coding: utf-8 -*-
"""
build.py — compilation complète de LexiARC pour Windows, sans droits admin.

À placer dans le dossier logiciel contenant :
  lexiarc_gui.py
  lexiarc_core.py
  logo.ico
  bin/mtools/...
  core/windows/Lead.sys
  requirements.txt (facultatif)

Produit dist/LexiARC.exe en mode PyInstaller --onefile.
"""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Configuration
APP_NAME = "LexiARC"
ENTRY_POINT = "lexiarc_gui.py"
ICON_NAME = "logo.ico"
VENV_NAME = ".venv"
REQUIREMENTS_NAME = "requirements.txt"

MTOOLS_REL = Path("bin") / "mtools"
LEAD_REL = Path("core") / "windows" / "Lead.sys"


def run(command: list[str | Path]) -> None:
    command = [str(x) for x in command]
    print("\n>", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    if sys.platform != "win32":
        print("ERREUR : ce script de build est prévu pour Windows.")
        return 1

    entry = ROOT / ENTRY_POINT
    if not entry.is_file():
        print(f"ERREUR : point d'entrée introuvable : {entry}")
        print("Modifie ENTRY_POINT en haut de build.py si nécessaire.")
        return 1

    lead_sys = ROOT / LEAD_REL
    if not lead_sys.is_file():
        print(f"ERREUR : fichier obligatoire introuvable : {lead_sys}")
        return 1

    mtools_dir = ROOT / MTOOLS_REL
    if not mtools_dir.is_dir():
        print(f"ERREUR : dossier obligatoire introuvable : {mtools_dir}")
        return 1

    mtools_files = sorted(p for p in mtools_dir.rglob("*") if p.is_file())
    mtools_exes = [p for p in mtools_files if p.suffix.lower() == ".exe"]
    if not any(p.name.lower() == "mtools.exe" for p in mtools_exes) and not all(
        any(p.name.lower() == f"{name}.exe" for p in mtools_exes)
        for name in ("mformat", "mmd", "mcopy", "mdir")
    ):
        print("ERREUR : bin/mtools doit contenir mtools.exe ou les quatre outils")
        print("mformat.exe, mmd.exe, mcopy.exe et mdir.exe.")
        return 1

    venv_dir = ROOT / VENV_NAME
    python = venv_dir / "Scripts" / "python.exe"

    if not python.is_file():
        print(f"Création de l'environnement virtuel : {venv_dir}")
        venv.create(venv_dir, with_pip=True)

    if not python.is_file():
        print("ERREUR : impossible de créer l'environnement Python.")
        return 1

    try:
        run([python, "-m", "pip", "install", "--upgrade", "pip"])

        requirements = ROOT / REQUIREMENTS_NAME
        if requirements.is_file():
            run([python, "-m", "pip", "install", "-r", requirements])

        # Pillow est requis par le GUI si celui-ci utilise PIL.
        run([python, "-m", "pip", "install", "--upgrade", "pyinstaller", "Pillow"])

        cmd: list[str | Path] = [
            python, "-m", "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name", APP_NAME,
            "--distpath", ROOT / "dist",
            "--workpath", ROOT / "build" / "pyinstaller",
            "--specpath", ROOT / "build",
        ]

        icon = ROOT / ICON_NAME
        if icon.is_file():
            cmd.extend(["--icon", icon])
        else:
            print(f"AVERTISSEMENT : icône absente : {icon}")

        # Embarque chaque fichier de bin/mtools, y compris les EXE, DLL et configs.
        # Les chemins relatifs sont conservés sous _MEIPASS/bin/mtools/.
        for file in mtools_files:
            relative_parent = file.parent.relative_to(mtools_dir)
            destination = Path("bin") / "mtools" / relative_parent
            option = "--add-binary" if file.suffix.lower() == ".exe" or file.suffix.lower() == ".dll" else "--add-data"
            cmd.extend([option, f"{file};{destination.as_posix()}"])

        # Embarque core/windows/Lead.sys sous _MEIPASS/core/windows/Lead.sys.
        cmd.extend([
            "--add-data",
            f"{lead_sys};core/windows",
        ])

        # Imports directs du GUI/core : PyInstaller les détecte automatiquement.
        cmd.append(entry)
        run(cmd)

        output = ROOT / "dist" / f"{APP_NAME}.exe"
        if not output.is_file():
            print(f"ERREUR : EXE final introuvable : {output}")
            return 1

        print("\n" + "=" * 64)
        print("COMPILATION TERMINÉE")
        print(f"EXE : {output}")
        print(f"Taille : {output.stat().st_size / (1024 * 1024):.1f} Mio")
        print("=" * 64)
        print(
            "\nÀ vérifier dans lexiarc_core.py : en mode EXE, MTOOLS_DIR doit pointer "
            "vers Path(sys._MEIPASS) / 'bin' / 'mtools', et BUNDLED_LEAD_SYS vers "
            "Path(sys._MEIPASS) / 'core' / 'windows' / 'Lead.sys'."
        )
        return 0

    except subprocess.CalledProcessError as exc:
        print(f"\nÉCHEC : une commande a retourné le code {exc.returncode}.")
        return exc.returncode or 1
    except KeyboardInterrupt:
        print("\nCompilation interrompue.")
        return 130
    except OSError as exc:
        print(f"\nErreur système : {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
