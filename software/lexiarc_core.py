# -*- coding: utf-8 -*-
"""
lexiarc_core.py -- logique metier de LexiARC (aucune dependance a tkinter).

Contient :
  * la gestion des chemins (script Python OU executable PyInstaller)
  * le wrapper mtools (mformat / mmd / mcopy / mdir)
  * la creation d'une carte SD virtuelle FAT32 a partir de la carte originale
  * la verification / le telechargement des dependances (emu293 + DLL)
  * la lecture / ecriture des fichiers .larc
  * le lancement reel d'emu293
"""
import datetime
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
FROZEN = getattr(sys, "frozen", False)

# Dossier "utilisateur" : la ou vivent bin/, emulations/, logs/ (modifiable).
# En .exe PyInstaller (onefile), __file__ pointe vers un dossier temporaire,
# donc on se base sur l'emplacement de l'executable.

APP_DIR = (
    Path(sys.executable).resolve().parent
    if FROZEN
    else Path(__file__).resolve().parent
)

RES_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))

# Ressources embarquées dans l'EXE PyInstaller
BIN_DIR = APP_DIR / "bin"
MTOOLS_DIR = (
    RES_DIR / "bin" / "mtools"
    if FROZEN
    else BIN_DIR / "mtools"
)

# emu293 et ses DLL restent dans le dossier utilisateur
EMU293_EXE = BIN_DIR / "emu293.exe" if os.name == "nt" else BIN_DIR / "emu293"
BUNDLED_LEAD_SYS = APP_DIR / "core" / "windows" / "Lead.sys"
EMULATIONS_DIR = APP_DIR / "emulations"
LOGS_DIR = APP_DIR / "logs"
DEPS_MANIFEST = APP_DIR / "dependencies.json"

IS_WIN = os.name == "nt"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WIN else 0

# DLL dont emu293.exe a besoin (lues dans sa table d'imports) et qui doivent
# se trouver a cote de lui. Sans elles : crash immediat, log vide.
REQUIRED_DLLS = [
    "SDL2.dll",
    "libgcc_s_seh-1.dll",
    "libstdc++-6.dll",
    "libwinpthread-1.dll",
    "wxbase32u_gcc_custom.dll",
    "wxmsw32u_core_gcc_custom.dll",
    "zlib1.dll",
]

# Dependances telechargeables. Surchargeable via dependencies.json.
#  - emu293 : AUCUN binaire Windows precompile n'est publie par gatecat/emu293
#    (seulement le code source). Il faut donc publier un zip
#    "emu293_win64.zip" (emu293.exe + les 7 DLL) dans une release de ton depot.
DEFAULT_DEPS = {
    "emu293": {
        "nom": "emu293 + DLL (moteur d'emulation)",
        "url": "https://github.com/maxlware-fr/LexiARC/raw/refs/heads/main/software/bin/emu293_win64.zip",
    },
    "mtools": {
        "nom": "mtools (creation de la carte SD)",
        "url": None,  # fourni avec le package (bin/mtools/mtools.exe)
    },
}

SIZES_GB = [1, 2, 4, 8, 16]
SECTOR = 512
IGNORED_NAMES = {"system volume information", "$recycle.bin", "thumbs.db", "desktop.ini", ".ds_store"}


class CoreError(Exception):
    pass


# ---------------------------------------------------------------------------
# mtools
# ---------------------------------------------------------------------------
def ensure_mtools():
    """mtools.exe est un binaire 'multi-appel' : il choisit la commande selon son
    propre nom. On cree donc mcopy.exe / mdir.exe / mformat.exe / mmd.exe par
    copie (pas de lien symbolique sans droits admin sous Windows)."""
    if not IS_WIN:
        return all(shutil.which(c) for c in ("mformat", "mmd", "mcopy", "mdir"))
    base = MTOOLS_DIR / "mtools.exe"
    if not base.exists():
        return all((MTOOLS_DIR / f"{c}.exe").exists() for c in ("mformat", "mmd", "mcopy", "mdir"))
    for cmd in ("mformat", "mmd", "mcopy", "mdir"):
        dst = MTOOLS_DIR / f"{cmd}.exe"
        if not dst.exists():
            try:
                shutil.copy2(base, dst)
            except OSError:
                return False
    return True


def _tool(name):
    if IS_WIN:
        p = MTOOLS_DIR / f"{name}.exe"
        if p.exists():
            return str(p)
    found = shutil.which(name)
    if found:
        return found
    raise CoreError(f"Outil mtools introuvable : {name}")


def mt(cmd, *args, timeout=120):
    """Execute une commande mtools. Retourne CompletedProcess (texte, jamais d'exception sur rc != 0)."""
    return subprocess.run(
        [_tool(cmd), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, creationflags=NO_WINDOW,
    )


# ---------------------------------------------------------------------------
# Dependances
# ---------------------------------------------------------------------------
def load_manifest():
    deps = {k: dict(v) for k, v in DEFAULT_DEPS.items()}
    if DEPS_MANIFEST.exists():
        try:
            user = json.loads(DEPS_MANIFEST.read_text(encoding="utf-8"))
            for k, v in user.items():
                deps.setdefault(k, {}).update(v)
        except Exception:
            pass
    return deps


def check_dependencies():
    """Retourne une liste de dicts : id, nom, ok, manquants, url."""
    manifest = load_manifest()
    res = []

    mt_ok = ensure_mtools()
    res.append({"id": "mtools", "nom": manifest["mtools"]["nom"], "ok": mt_ok,
                "manquants": [] if mt_ok else ["mtools.exe"], "url": manifest["mtools"].get("url")})

    manquants = []
    if not EMU293_EXE.exists():
        manquants.append(EMU293_EXE.name)
    if IS_WIN:
        manquants += [d for d in REQUIRED_DLLS if not (BIN_DIR / d).exists()]
    res.append({"id": "emu293", "nom": manifest["emu293"]["nom"], "ok": not manquants,
                "manquants": manquants, "url": manifest["emu293"].get("url")})
    return res


def download_dependency(dep_id, progress_cb=None):
    """Telecharge un zip et en extrait les fichiers a plat dans bin/. Leve CoreError avec un message clair."""
    url = load_manifest().get(dep_id, {}).get("url")
    if not url:
        raise CoreError("Aucune URL de telechargement n'est configuree pour cette dependance.\n"
                        "Utilise 'Choisir manuellement' ou renseigne dependencies.json.")
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    tmp = BIN_DIR / f"_dl_{dep_id}.zip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LexiARC"})
        with urllib.request.urlopen(req, timeout=30) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
    except urllib.error.HTTPError as e:
        tmp.unlink(missing_ok=True)
        if e.code == 404:
            raise CoreError(f"Fichier introuvable (404) :\n{url}\n\nAucun asset n'est publie a cette adresse. "
                            "Publie emu293_win64.zip dans une release GitHub, ou utilise 'Choisir manuellement'.")
        raise CoreError(f"Erreur HTTP {e.code} sur {url}")
    except Exception as e:
        tmp.unlink(missing_ok=True)
        raise CoreError(f"Telechargement impossible : {e}")

    try:
        if not zipfile.is_zipfile(tmp):
            raise CoreError("Le fichier telecharge n'est pas une archive zip valide.")
        with zipfile.ZipFile(tmp) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = Path(info.filename).name  # a plat : evite tout zip-slip
                if not name:
                    continue
                with z.open(info) as src, open(BIN_DIR / name, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    finally:
        tmp.unlink(missing_ok=True)


def import_emu293_from_folder(folder):
    """Copie emu293.exe + les DLL depuis un dossier choisi par l'utilisateur. Retourne la liste des fichiers copies."""
    folder = Path(folder)
    exe = folder / EMU293_EXE.name
    if not exe.exists():
        raise CoreError(f"{EMU293_EXE.name} introuvable dans :\n{folder}")
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    copies = []
    wanted = [EMU293_EXE.name] + (REQUIRED_DLLS if IS_WIN else [])
    for n in wanted:
        s = folder / n
        if s.exists():
            if s.resolve() != (BIN_DIR / n).resolve():
                shutil.copy2(s, BIN_DIR / n)
            copies.append(n)
    return copies


# ---------------------------------------------------------------------------
# Carte SD : validation
# ---------------------------------------------------------------------------
def _find_ci(base: Path, *parts):
    """Chemin insensible a la casse (windows/Lead.sys vs Windows/lead.sys)."""
    cur = base
    for part in parts:
        if not cur.is_dir():
            return None
        match = next((c for c in cur.iterdir() if c.name.lower() == part.lower()), None)
        if match is None:
            return None
        cur = match
    return cur


def scan_source(src):
    """Compte dossiers / fichiers / octets a copier."""
    n_files = n_dirs = total = 0
    non_ascii = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d.lower() not in IGNORED_NAMES]
        n_dirs += len(dirs)
        for d in dirs:
            if not d.isascii():
                non_ascii += 1
        for f in files:
            if f.lower() in IGNORED_NAMES:
                continue
            n_files += 1
            if not f.isascii():
                non_ascii += 1
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return {"files": n_files, "dirs": n_dirs, "bytes": total, "non_ascii": non_ascii}


def validate_source_folder(path):
    """La carte originale doit contenir windows/Lead.sys (boot application d'emu293)."""
    p = Path(path)
    if not p.is_dir():
        return False, "Ce dossier / lecteur n'existe pas.", None, None
    lead = _find_ci(p, "windows", "Lead.sys")
    if lead is None:
        return False, ("windows/Lead.sys est introuvable dans ce dossier.\n"
                       "Ce n'est pas la carte SD d'origine de la console (ou un dossier incomplet)."), None, None
    info = scan_source(p)
    return True, "", lead, info


def validate_sd_image(img):
    p = Path(img)
    if not p.is_file():
        return False, "Fichier introuvable."
    if p.stat().st_size < 8 * 1024 * 1024:
        return False, "Ce fichier est trop petit pour etre une carte SD."
    r = mt("mdir", "-i", p, "::/")
    if r.returncode != 0:
        return False, ("Image illisible comme FAT : " + (r.stderr.strip() or r.stdout.strip() or "erreur inconnue"))
    r = mt("mdir", "-i", p, "::/windows")
    if r.returncode != 0:
        return False, "Image FAT valide, mais le dossier /windows est absent (carte non conforme)."
    return True, ""


def extract_lead_sys(img, dest_dir):
    """Extrait ::/windows/Lead.sys de l'image vers dest_dir ; retourne le chemin ou None."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "Lead.sys"
    for cand in ("::/windows/Lead.sys", "::/Windows/Lead.sys", "::/windows/lead.sys"):
        r = mt("mcopy", "-i", img, "-D", "o", cand, str(dest))
        if r.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
            return dest
    return None


def suggest_size_gb(total_bytes):
    need = total_bytes * 1.15 + 64 * 1024 * 1024
    for g in SIZES_GB:
        if g * 1024 ** 3 >= need:
            return g
    return SIZES_GB[-1]


# ---------------------------------------------------------------------------
# Carte SD : creation de l'image virtuelle
# ---------------------------------------------------------------------------
def _chunks(items, max_chars=6000, max_items=60):
    cur, cur_len = [], 0
    for it in items:
        l = len(it) + 3
        if cur and (cur_len + l > max_chars or len(cur) >= max_items):
            yield cur
            cur, cur_len = [], 0
        cur.append(it)
        cur_len += l
    if cur:
        yield cur


def create_virtual_sd(src, img, size_gb, label="LEXIBOOK", progress_cb=None, cancel_event=None):
    """
    Cree img (FAT32, size_gb Go) et y copie tout le contenu de src.
    Copie par LOTS (un appel mcopy par dossier et par groupe de fichiers), avec repli
    fichier par fichier en cas d'echec du lot. N'utilise JAMAIS mcopy -s (bug du build 2019).

    progress_cb(done_files, total_files, texte)
    Retourne {"copied": n, "total": n, "errors": [(chemin, message)], "cancelled": bool}
    """
    src, img = Path(src), Path(img)
    info = scan_source(src)
    size_bytes = int(size_gb * 1024 ** 3)
    if info["bytes"] * 1.05 > size_bytes:
        raise CoreError("La taille choisie est trop petite pour le contenu de la carte "
                        f"({info['bytes'] / 1024 ** 3:.2f} Go a copier).")
    img.parent.mkdir(parents=True, exist_ok=True)

    # 1) fichier image + formatage FAT32
    with open(img, "wb") as f:
        f.truncate(size_bytes)
    r = mt("mformat", "-i", img, "-F", "-T", size_bytes // SECTOR, "-v", label[:11].upper(), "::")
    if r.returncode != 0:
        img.unlink(missing_ok=True)
        raise CoreError("Echec du formatage FAT32 : " + (r.stderr.strip() or r.stdout.strip()))

    errors = []
    copied = 0
    total = info["files"]

    def cancelled():
        return cancel_event is not None and cancel_event.is_set()

    def target(rel_parts):
        return "::/" + "/".join(rel_parts) + ("/" if rel_parts else "")

    # 2) dossiers (parents d'abord)
    all_dirs = []
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d.lower() not in IGNORED_NAMES)
        for d in dirs:
            rel = Path(root, d).relative_to(src)
            all_dirs.append("::/" + "/".join(rel.parts))
    for group in _chunks(all_dirs):
        if cancelled():
            return {"copied": copied, "total": total, "errors": errors, "cancelled": True}
        r = mt("mmd", "-i", img, *group)
        if r.returncode != 0 and "exist" not in (r.stderr + r.stdout).lower():
            # repli dossier par dossier
            for d in group:
                r1 = mt("mmd", "-i", img, d)
                if r1.returncode != 0 and "exist" not in (r1.stderr + r1.stdout).lower():
                    errors.append((d, r1.stderr.strip() or r1.stdout.strip()))
        if progress_cb:
            progress_cb(copied, total, "Creation de l'arborescence...")

    # 3) fichiers, dossier par dossier
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d.lower() not in IGNORED_NAMES)
        rel_parts = Path(root).relative_to(src).parts
        paths = [os.path.join(root, f) for f in sorted(files) if f.lower() not in IGNORED_NAMES]
        if not paths:
            continue
        dest = target(rel_parts)
        for group in _chunks(paths):
            if cancelled():
                return {"copied": copied, "total": total, "errors": errors, "cancelled": True}
            r = mt("mcopy", "-i", img, "-D", "o", *group, dest, timeout=600)
            if r.returncode == 0:
                copied += len(group)
            else:
                for p in group:  # repli : un par un pour isoler le(s) fichier(s) fautif(s)
                    r1 = mt("mcopy", "-i", img, "-D", "o", p, dest, timeout=600)
                    if r1.returncode == 0:
                        copied += 1
                    else:
                        errors.append((os.path.relpath(p, src), r1.stderr.strip() or r1.stdout.strip()))
            if progress_cb:
                progress_cb(copied, total, "/" + "/".join(rel_parts))
    return {"copied": copied, "total": total, "errors": errors, "cancelled": False}


def check_unicode_names(src, img, limit=5):
    """Verification indicative : les dossiers non-ASCII ont-ils garde leur nom long dans l'image ?
    Retourne la liste des dossiers dont le nom n'a pas ete retrouve."""
    bad, checked = [], 0
    for root, dirs, _ in os.walk(src):
        for d in dirs:
            if d.isascii():
                continue
            checked += 1
            if checked > limit:
                return bad
            rel = Path(root).relative_to(src).parts
            r = mt("mdir", "-i", img, "::/" + "/".join(rel) if rel else "::/")
            if d not in r.stdout:
                bad.append("/".join(rel + (d,)))
    return bad


# ---------------------------------------------------------------------------
# Navigation / ecriture dans une carte SD (implementation de fichiers)
# ---------------------------------------------------------------------------
def sd_join(base, name):
    return base.rstrip("/") + "/" + name


def sd_parent(path):
    path = path.rstrip("/")
    if path in ("::", ""):
        return "::/"
    parent = path.rsplit("/", 1)[0]
    return parent if parent not in ("::", "") else "::/"


def list_sd_dir(img, path="::/"):
    """Liste un dossier de l'image avec les NOMS LONGS. Retourne (dossiers, fichiers) tries,
    ou None si le dossier est illisible. S'appuie sur 'mdir -b' (chemins complets, '/' final = dossier)."""
    r = mt("mdir", "-b", "-i", img, path)
    if r.returncode != 0:
        return None
    dirs, files = [], []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line.startswith("::"):
            continue
        is_dir = line.endswith("/")
        name = line.rstrip("/").rsplit("/", 1)[-1]
        if not name or name in (".", ".."):
            continue
        (dirs if is_dir else files).append(name)
    return sorted(dirs, key=str.lower), sorted(files, key=str.lower)


def make_sd_dir(img, path):
    r = mt("mmd", "-i", img, path)
    ok = r.returncode == 0
    return ok, ("" if ok else (r.stderr.strip() or r.stdout.strip() or "erreur inconnue"))


def copy_file_to_sd(img, src_file, dest_dir, name=None):
    """Copie un fichier (n'importe quel type) dans dest_dir de l'image. name = nom sur la carte."""
    name = name or os.path.basename(src_file)
    r = mt("mcopy", "-i", img, "-D", "o", src_file, sd_join(dest_dir, name), timeout=600)
    ok = r.returncode == 0
    return ok, ("" if ok else (r.stderr.strip() or r.stdout.strip() or "erreur inconnue"))


# ---------------------------------------------------------------------------
# Fichiers .larc
# ---------------------------------------------------------------------------
LARC_VERSION = 2


def slugify(name):
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip()).strip("_").lower()
    return s or "emulation"


def save_larc(path, nom, cpu, ram, auteur, sd_path, lead_sys_path, origine):
    path = Path(path)
    data = {
        "version_larc": LARC_VERSION,
        "nom_emulateur": nom,
        "auteur_profil": auteur,
        "architecture_cpu": cpu,
        "taille_ram": ram,
        "image_sd_path": str(sd_path).replace("\\", "/"),
        "lead_sys_path": str(lead_sys_path).replace("\\", "/") if lead_sys_path else "",
        "origine_sd": origine,
        "date_creation": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    # chemins relatifs au .larc : le projet reste deplacable
    try:
        data["image_sd_relatif"] = os.path.relpath(sd_path, path.parent).replace("\\", "/")
        if lead_sys_path:
            data["lead_sys_relatif"] = os.path.relpath(lead_sys_path, path.parent).replace("\\", "/")
    except ValueError:  # autre lecteur sous Windows
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
    return data


def load_larc(path):
    """Lit un .larc (v1 ou v2) et resout les chemins (absolu puis relatif au .larc)."""
    path = Path(path)
    cfg = json.loads(path.read_text(encoding="utf-8-sig"))

    def resolve(abs_key, rel_key):
        a = cfg.get(abs_key) or ""
        if a and Path(a).exists():
            return Path(a)
        r = cfg.get(rel_key) or ""
        if r and (path.parent / r).exists():
            return (path.parent / r).resolve()
        return Path(a) if a else None

    cfg["_sd"] = resolve("image_sd_path", "image_sd_relatif")
    cfg["_lead"] = resolve("lead_sys_path", "lead_sys_relatif")
    if cfg["_lead"] is None or not Path(cfg["_lead"]).exists():
        # v1 sans lead_sys_path : a cote de l'image, sinon Lead.sys du package
        guess = Path(cfg["_sd"]).parent / "Lead.sys" if cfg["_sd"] else None
        if guess and guess.exists():
            cfg["_lead"] = guess
        elif BUNDLED_LEAD_SYS.exists():
            cfg["_lead"] = BUNDLED_LEAD_SYS
    return cfg


# ---------------------------------------------------------------------------
# Lancement
# ---------------------------------------------------------------------------
def pre_launch_check(cfg):
    """Retourne une liste de problemes bloquants (vide = on peut lancer)."""
    problems = []
    dep = next(d for d in check_dependencies() if d["id"] == "emu293")
    if not dep["ok"]:
        problems.append("emu293 incomplet, fichiers manquants dans bin/ : " + ", ".join(dep["manquants"]))
    if not cfg.get("_sd") or not Path(cfg["_sd"]).exists():
        problems.append(f"Image SD introuvable : {cfg.get('image_sd_path', '?')}")
    if not cfg.get("_lead") or not Path(cfg["_lead"]).exists():
        problems.append("Lead.sys introuvable (ni dans le .larc, ni a cote de l'image, ni dans le package).")
    return problems


def ascii_path(p):
    """emu293 (MinGW) ouvre les fichiers en codage ANSI : un chemin avec un accent (L'Ete avec accent)
    n'est pas retrouve. On renvoie donc un chemin 100 % ASCII equivalent :
      1) le nom court Windows 8.3 (GetShortPathNameW), sans droits admin ;
      2) sinon une jonction de dossier (mklink /J, sans droits admin) dans le dossier temporaire.
    Si rien n'est possible, retourne le chemin d'origine."""
    p = Path(p)
    s = str(p)
    if s.isascii() or not IS_WIN:
        return s
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.kernel32.GetShortPathNameW(s, buf, len(buf)) and buf.value.isascii():
            return buf.value
    except Exception:
        pass
    try:
        import hashlib
        import tempfile
        if not p.name.isascii():
            return s
        tmp = Path(tempfile.gettempdir())
        if not str(tmp).isascii():
            return s
        link = tmp / ("lexiarc_" + hashlib.md5(str(p.parent).encode("utf-8")).hexdigest()[:10])
        if not link.exists():
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(p.parent)],
                           capture_output=True, creationflags=NO_WINDOW)
        if link.exists():
            return str(link / p.name)
    except Exception:
        pass
    return s


EXIT_HINTS = {
    0xC0000135: "DLL introuvable : il manque une DLL a cote d'emu293.exe (etape 4 de l'assistant).",
    0xC000007B: "DLL de mauvaise architecture (32 bits / 64 bits melanges, ex. mingw64 + ucrt64).",
    0xC0000005: "Violation d'acces memoire : plantage d'emu293.",
}


def explain_exit(code):
    if code is None:
        return ""
    c = code & 0xFFFFFFFF
    if c == 0:
        return "Arret normal."
    return EXIT_HINTS.get(c, "")


class EmuSession:
    """Processus emu293 + copie en direct de sa sortie : fichier de log ET file d'attente (pour la GUI)."""

    def __init__(self, cfg):
        LOGS_DIR.mkdir(exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = LOGS_DIR / f"emu293_{stamp}.log"
        self.lead, self.sd = ascii_path(cfg["_lead"]), ascii_path(cfg["_sd"])
        self.q = queue.Queue()
        self._log = open(self.log_path, "w", encoding="utf-8", errors="replace")
        self._emit(f"# LexiARC : lead={self.lead}\n# LexiARC : sd={self.sd}\n")
        if not (str(self.lead).isascii() and str(self.sd).isascii()):
            self._emit("# LexiARC : ATTENTION, chemin non-ASCII impossible a convertir : "
                       "deplace le projet dans un dossier sans accent (ex. C:\\emu).\n")
        self.proc = subprocess.Popen(
            [str(EMU293_EXE), self.lead, self.sd], cwd=str(EMU293_EXE.parent),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NO_WINDOW,
        )
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _emit(self, text):
        try:
            self._log.write(text)
            self._log.flush()
        except ValueError:
            pass
        self.q.put(text)

    def _pump(self):
        try:
            while True:
                chunk = self.proc.stdout.read1(4096)
                if not chunk:
                    break
                self._emit(chunk.decode("utf-8", errors="replace"))
        finally:
            code = self.proc.wait()
            self.q.put(("exit", code))

    def poll(self):
        return self.proc.poll()

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()

    def close(self):
        try:
            self._log.close()
        except Exception:
            pass


def launch_emulation(cfg):
    """Lance emu293 pour de vrai et retourne une EmuSession."""
    return EmuSession(cfg)
