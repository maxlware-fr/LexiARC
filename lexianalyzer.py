#!/usr/bin/env python3
"""
lexianalyzer.py — Outil d'analyse pour reverse engineering de la console
Lexibook JG7420AV (et SoC Sunplus/unSP similaires).

Usage:
    python3 lexianalyzer.py scan <dossier>                  # scan complet de la carte SD
    python3 lexianalyzer.py elf <fichier.elf>                # analyse détaillée d'un ELF
    python3 lexianalyzer.py entropy <fichier>                 # entropie globale + par bloc
    python3 lexianalyzer.py decompress <fichier> [--offset N] # tentatives multi-algo
    python3 lexianalyzer.py hexdump <fichier> [--offset N] [--len N]
    python3 lexianalyzer.py strings <fichier> [--min 6]
    python3 lexianalyzer.py export <dossier> --format json|md|html -o out.ext
    python3 lexianalyzer.py compare <fichierA> <fichierB>

Dépendances: pyelftools (pip install pyelftools), numpy (optionnel, accélère l'entropie).
"""
import argparse
import hashlib
import io
import json
import math
import os
import struct
import sys
import zlib
import gzip
import lzma
import bz2
from collections import Counter
from pathlib import Path

try:
    from elftools.elf.elffile import ELFFile
    HAVE_ELFTOOLS = True
except ImportError:
    HAVE_ELFTOOLS = False

try:
    import lz4.frame as lz4frame
    HAVE_LZ4 = True
except ImportError:
    HAVE_LZ4 = False

KNOWN_EXTENSIONS = {".wxn", ".bin", ".64", ".elf", ".sys", ".dot", ".mp3"}

KNOWN_SIGNATURES = [
    (b"\x7fELF", "ELF binary"),
    (b"mfc\x00", "Format propriétaire 'mfc' (probable .wxn)"),
    (b"\x1f\x8b", "gzip"),
    (b"BZh", "bzip2"),
    (b"\xfd7zXZ\x00", "xz/lzma2"),
    (b"PK\x03\x04", "ZIP"),
    (b"RIFF", "RIFF container (WAV/AVI)"),
    (b"ID3", "MP3 (ID3 tag)"),
    (b"\xff\xfb", "MP3 (frame sync, no ID3)"),
    (b"GIF8", "GIF"),
    (b"\x89PNG", "PNG"),
    (b"BM", "BMP"),
]

# ---------------------------------------------------------------------------
# Utilitaires génériques
# ---------------------------------------------------------------------------

def read_bytes(path, offset=0, length=None):
    with open(path, "rb") as f:
        f.seek(offset)
        return f.read(length) if length else f.read()


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    length = len(data)
    entropy = 0.0
    for c in counts.values():
        p = c / length
        entropy -= p * math.log2(p)
    return entropy


def entropy_by_blocks(data: bytes, block_size=256):
    blocks = []
    for i in range(0, len(data), block_size):
        chunk = data[i:i + block_size]
        blocks.append((i, round(shannon_entropy(chunk), 3)))
    return blocks


def detect_signature(data: bytes):
    matches = []
    for sig, name in KNOWN_SIGNATURES:
        if data.startswith(sig):
            matches.append(name)
    # recherche non ancrée sur les 64 premiers octets (headers décalés)
    head = data[:64]
    for sig, name in KNOWN_SIGNATURES:
        if sig in head and name not in matches:
            matches.append(f"{name} (offset non nul)")
    return matches


def hexdump(data: bytes, offset=0, length=256, base_offset=0):
    chunk = data[offset:offset + length]
    lines = []
    for i in range(0, len(chunk), 16):
        row = chunk[i:i + 16]
        hex_part = " ".join(f"{b:02x}" for b in row)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        lines.append(f"{base_offset + offset + i:08x}  {hex_part:<47}  {ascii_part}")
    return "\n".join(lines)


def extract_strings(data: bytes, min_len=6):
    result = []
    current = []
    start = 0
    for i, b in enumerate(data):
        if 32 <= b < 127:
            if not current:
                start = i
            current.append(chr(b))
        else:
            if len(current) >= min_len:
                result.append((start, "".join(current)))
            current = []
    if len(current) >= min_len:
        result.append((start, "".join(current)))
    return result


# ---------------------------------------------------------------------------
# Décompression multi-algorithme
# ---------------------------------------------------------------------------

def try_decompress(data: bytes, max_offset_scan=64):
    """Essaie plusieurs algorithmes à plusieurs offsets de départ.
    Retourne la liste des tentatives réussies avec offset/algo/taille."""
    results = []

    def attempt(name, fn, off):
        try:
            out = fn(data[off:])
            if out and len(out) > 32:
                results.append({
                    "algo": name,
                    "offset": off,
                    "decompressed_size": len(out),
                    "sha256_prefix": hashlib.sha256(out[:4096]).hexdigest()[:16],
                })
        except Exception:
            pass

    algos = {
        "zlib": lambda d: zlib.decompress(d),
        "zlib_raw(-15)": lambda d: zlib.decompressobj(-15).decompress(d),
        "gzip": lambda d: gzip.decompress(d),
        "lzma": lambda d: lzma.decompress(d),
        "lzma_raw": lambda d: lzma.decompress(d, format=lzma.FORMAT_RAW,
                                               filters=[{"id": lzma.FILTER_LZMA2}]),
        "bz2": lambda d: bz2.decompress(d),
    }
    if HAVE_LZ4:
        algos["lz4"] = lambda d: lz4frame.decompress(d)

    for off in range(0, min(max_offset_scan, len(data))):
        for name, fn in algos.items():
            attempt(name, fn, off)

    return results


# ---------------------------------------------------------------------------
# Analyse ELF
# ---------------------------------------------------------------------------

def analyze_elf(path):
    info = {"path": str(path), "size": os.path.getsize(path)}
    raw = read_bytes(path, 0, 64)
    if not raw.startswith(b"\x7fELF"):
        info["error"] = "Pas un fichier ELF (magic manquant)"
        return info

    ei_class = raw[4]
    ei_data = raw[5]
    info["class"] = "ELF32" if ei_class == 1 else ("ELF64" if ei_class == 2 else f"unknown({ei_class})")
    info["endianness"] = "little" if ei_data == 1 else ("big" if ei_data == 2 else f"unknown({ei_data})")

    # e_machine est aux offsets 18-19 (ELF32/64, même position), little/big endian dépendant
    fmt = "<H" if ei_data == 1 else ">H"
    e_machine = struct.unpack(fmt, raw[18:20])[0]
    info["e_machine_raw"] = e_machine
    info["e_machine_hex"] = hex(e_machine)

    KNOWN_MACHINES = {
        0x03: "x86", 0x08: "MIPS", 0x28: "ARM", 0x2A: "SuperH",
        0x3E: "x86-64", 0xB7: "AArch64", 0x14: "PowerPC",
        0x87: "Sunplus/GeneralPlus S+core (Score7) — SoC SPG29x/SPG293 (confirme JG7420AV/JG7425)",
    }
    info["e_machine_guess"] = KNOWN_MACHINES.get(e_machine, "INCONNU (probable ISA custom, ex: Sunplus unSP)")

    if HAVE_ELFTOOLS:
        try:
            with open(path, "rb") as f:
                elf = ELFFile(f)
                info["entry_point"] = hex(elf.header["e_entry"])
                info["sections"] = []
                for sec in elf.iter_sections():
                    info["sections"].append({
                        "name": sec.name,
                        "type": sec["sh_type"],
                        "addr": hex(sec["sh_addr"]),
                        "size": sec["sh_size"],
                    })
                info["segments"] = []
                for seg in elf.iter_segments():
                    info["segments"].append({
                        "type": seg["p_type"],
                        "vaddr": hex(seg["p_vaddr"]),
                        "filesz": seg["p_filesz"],
                        "memsz": seg["p_memsz"],
                    })
                symtab = elf.get_section_by_name(".symtab")
                if symtab is not None:
                    info["symbol_count"] = symtab.num_symbols()
                    info["symbols_sample"] = [
                        s.name for s in list(symtab.iter_symbols())[:50] if s.name
                    ]
                else:
                    info["symbol_count"] = 0
                    info["note"] = "Pas de .symtab — binaire probablement strippé"
        except Exception as e:
            info["elftools_error"] = f"e_machine {hex(e_machine)} non reconnu par pyelftools ({e}). " \
                                      "Analyse manuelle des headers recommandée (voir champs bruts ci-dessus)."
    else:
        info["note"] = "pyelftools non installé — analyse limitée aux headers bruts"

    return info


def dump_symbol_bytes(path, symbol_name):
    """Localise un symbole (fonction/objet) et extrait ses octets bruts via le mapping segment->fichier."""
    if not HAVE_ELFTOOLS:
        return None, {"error": "pyelftools non installe"}
    with open(path, "rb") as f:
        elf = ELFFile(f)
        symtab = elf.get_section_by_name(".symtab")
        if symtab is None:
            return None, {"error": "Pas de .symtab"}
        target = None
        for s in symtab.iter_symbols():
            if s.name == symbol_name:
                target = s
                break
        if target is None:
            return None, {"error": f"Symbole '{symbol_name}' introuvable"}
        vaddr = target["st_value"]
        size = target["st_size"] or 64
        segs = list(elf.iter_segments())
        for seg in segs:
            if seg["p_type"] != "PT_LOAD":
                continue
            seg_vaddr = seg["p_vaddr"]
            seg_filesz = seg["p_filesz"]
            if seg_vaddr <= vaddr < seg_vaddr + seg_filesz:
                file_off = seg["p_offset"] + (vaddr - seg_vaddr)
                f.seek(file_off)
                data = f.read(size)
                return data, {"symbol": symbol_name, "vaddr": hex(vaddr), "size": size, "file_offset": hex(file_off)}
        return None, {"error": "Adresse hors de tout segment PT_LOAD charge (peut-etre .bss/non initialise)"}


def dump_addr(path, vaddr, length):
    """Extrait des octets bruts a une adresse virtuelle arbitraire (fonction anonyme,
    pas de symbole associe). Complement a dump_symbol_bytes qui exige un nom de symbole."""
    if not HAVE_ELFTOOLS:
        return None, {"error": "pyelftools non installe"}
    with open(path, "rb") as f:
        elf = ELFFile(f)
        for seg in elf.iter_segments():
            if seg["p_type"] != "PT_LOAD":
                continue
            seg_vaddr = seg["p_vaddr"]
            seg_filesz = seg["p_filesz"]
            if seg_vaddr <= vaddr < seg_vaddr + seg_filesz:
                file_off = seg["p_offset"] + (vaddr - seg_vaddr)
                max_len = seg["p_offset"] + seg_filesz - file_off
                read_len = min(length, max_len)
                f.seek(file_off)
                data = f.read(read_len)
                return data, {"vaddr": hex(vaddr), "size": len(data), "file_offset": hex(file_off)}
        return None, {"error": "Adresse hors de tout segment PT_LOAD charge"}


def dump_section(path, section_name):
    """Extrait les octets bruts d'une section ELF nommée."""
    if not HAVE_ELFTOOLS:
        return None, {"error": "pyelftools non installe"}
    with open(path, "rb") as f:
        elf = ELFFile(f)
        sec = elf.get_section_by_name(section_name)
        if sec is None:
            return None, {"error": f"Section '{section_name}' introuvable"}
        return sec.data(), {"name": section_name, "size": sec["sh_size"], "addr": hex(sec["sh_addr"])}


def list_symbols(path, grep=None, show_all=False, addr_min=None, addr_max=None):
    """Liste (ou filtre) tous les symboles d'un ELF non-strippé."""
    if not HAVE_ELFTOOLS:
        return {"error": "pyelftools non installe"}
    results = []
    with open(path, "rb") as f:
        elf = ELFFile(f)
        symtab = elf.get_section_by_name(".symtab")
        if symtab is None:
            return {"error": "Pas de .symtab (binaire strippe)"}
        for s in symtab.iter_symbols():
            if not s.name:
                continue
            if grep and grep.lower() not in s.name.lower():
                continue
            value = s["st_value"]
            if addr_min is not None and value < addr_min:
                continue
            if addr_max is not None and value > addr_max:
                continue
            results.append({
                "name": s.name,
                "value": hex(value),
                "size": s["st_size"],
                "type": s["st_info"]["type"],
            })
    results.sort(key=lambda r: int(r["value"], 16))
    return {"total_matching": len(results), "symbols": results if (grep or show_all or addr_min is not None) else results[:100]}


def dwarf_source_files(path):
    """Extrait la liste des fichiers source d'origine depuis les infos DWARF."""
    if not HAVE_ELFTOOLS:
        return {"error": "pyelftools non installe"}
    files = set()
    with open(path, "rb") as f:
        elf = ELFFile(f)
        if not elf.has_dwarf_info():
            return {"error": "Pas d'infos DWARF dans ce binaire"}
        dwarf = elf.get_dwarf_info()
        for cu in dwarf.iter_CUs():
            top_die = cu.get_top_DIE()
            name = top_die.attributes.get("DW_AT_name")
            comp_dir = top_die.attributes.get("DW_AT_comp_dir")
            if name:
                n = name.value.decode("utf-8", errors="replace")
                d = comp_dir.value.decode("utf-8", errors="replace") if comp_dir else ""
                files.add(f"{d}\\{n}" if d else n)
    return {"count": len(files), "files": sorted(files)}


# ---------------------------------------------------------------------------
# Scan complet
# ---------------------------------------------------------------------------

def scan_directory(root):
    root = Path(root)
    report = {"root": str(root), "files": []}
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        entry = {
            "path": str(path.relative_to(root)),
            "size": size,
            "ext": path.suffix.lower(),
        }
        if size > 0:
            head = read_bytes(path, 0, min(512, size))
            entry["entropy_head"] = round(shannon_entropy(head), 3)
            entry["signatures"] = detect_signature(head)
            entry["hex_header"] = head[:16].hex()
            if path.suffix.lower() == ".elf" or head.startswith(b"\x7fELF"):
                entry["elf_summary"] = {
                    "class": "ELF32" if head[4] == 1 else "ELF64" if head[4] == 2 else "?",
                    "e_machine_hex": hex(struct.unpack("<H", head[18:20])[0]) if len(head) >= 20 else None,
                }
        report["files"].append(entry)
    report["total_files"] = len(report["files"])
    report["by_extension"] = dict(Counter(f["ext"] for f in report["files"]))
    return report


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_json(report, out_path):
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def export_markdown(report, out_path):
    lines = [f"# Rapport d'analyse — {report['root']}", ""]
    lines.append(f"**Fichiers totaux :** {report['total_files']}")
    lines.append("")
    lines.append("## Répartition par extension")
    lines.append("")
    lines.append("| Extension | Nombre |")
    lines.append("|---|---|")
    for ext, count in sorted(report["by_extension"].items(), key=lambda x: -x[1]):
        lines.append(f"| `{ext or '(sans extension)'}` | {count} |")
    lines.append("")
    lines.append("## Détail des fichiers")
    lines.append("")
    lines.append("| Fichier | Taille | Entropie (tête) | Signatures |")
    lines.append("|---|---|---|---|")
    for entry in report["files"]:
        sig = ", ".join(entry.get("signatures", [])) or "-"
        lines.append(f"| `{entry['path']}` | {entry['size']} | {entry.get('entropy_head', '-')} | {sig} |")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def export_html(report, out_path):
    rows = "\n".join(
        f"<tr><td>{e['path']}</td><td>{e['size']}</td>"
        f"<td>{e.get('entropy_head', '-')}</td>"
        f"<td>{', '.join(e.get('signatures', [])) or '-'}</td></tr>"
        for e in report["files"]
    )
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Rapport — {report['root']}</title>
<style>
body {{ font-family: monospace; margin: 2rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; font-size: 13px; }}
th {{ background: #222; color: #fff; }}
</style></head><body>
<h1>Rapport d'analyse — {report['root']}</h1>
<p>Fichiers totaux : {report['total_files']}</p>
<table><tr><th>Fichier</th><th>Taille</th><th>Entropie</th><th>Signatures</th></tr>
{rows}
</table></body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyseur pour reverse engineering Lexibook JG7420AV")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Scan complet d'un dossier / carte SD")
    p_scan.add_argument("directory")
    p_scan.add_argument("-o", "--output", help="Fichier JSON de sortie (sinon stdout)")

    p_elf = sub.add_parser("elf", help="Analyse détaillée d'un fichier ELF")
    p_elf.add_argument("file")

    p_ent = sub.add_parser("entropy", help="Entropie globale + par blocs")
    p_ent.add_argument("file")
    p_ent.add_argument("--block", type=int, default=256)

    p_dec = sub.add_parser("decompress", help="Essaie plusieurs algos/offsets de décompression")
    p_dec.add_argument("file")
    p_dec.add_argument("--max-offset", type=int, default=64)

    p_hex = sub.add_parser("hexdump", help="Affiche un hexdump")
    p_hex.add_argument("file")
    p_hex.add_argument("--offset", type=int, default=0)
    p_hex.add_argument("--len", type=int, default=256)

    p_str = sub.add_parser("strings", help="Extrait les chaînes ASCII")
    p_str.add_argument("file")
    p_str.add_argument("--min", type=int, default=6)

    p_exp = sub.add_parser("export", help="Scan + export JSON/Markdown/HTML")
    p_exp.add_argument("directory")
    p_exp.add_argument("--format", choices=["json", "md", "html"], default="json")
    p_exp.add_argument("-o", "--output", required=True)

    p_sym = sub.add_parser("symbols", help="Liste/filtre les symboles d'un ELF non-strippé")
    p_sym.add_argument("file")
    p_sym.add_argument("--grep", help="Filtre par sous-chaîne (insensible à la casse)")
    p_sym.add_argument("--all", action="store_true", help="Affiche tout (sinon limité à 100 sans --grep)")
    p_sym.add_argument("--addr-min", help="Adresse min (hex, ex: 0xa0e44000)")
    p_sym.add_argument("--addr-max", help="Adresse max (hex, ex: 0xa0e45000)")

    p_dwarf = sub.add_parser("dwarf-files", help="Liste les fichiers source d'origine (DWARF)")
    p_dwarf.add_argument("file")

    p_sec = sub.add_parser("section-dump", help="Extrait/hexdump une section ELF nommée")
    p_sec.add_argument("file")
    p_sec.add_argument("section")
    p_sec.add_argument("-o", "--output", help="Ecrit les octets bruts dans ce fichier (sinon hexdump stdout)")
    p_sec.add_argument("--len", type=int, default=1216, help="Longueur max affichée en hexdump")

    p_symdump = sub.add_parser("symbol-dump", help="Extrait/hexdump les octets bruts d'une fonction/objet par son nom de symbole")
    p_symdump.add_argument("file")
    p_symdump.add_argument("symbol")
    p_symdump.add_argument("-o", "--output", help="Ecrit les octets bruts dans ce fichier (sinon hexdump stdout)")

    p_addr = sub.add_parser("addr-dump", help="Extrait/hexdump des octets bruts a une adresse virtuelle (fonction sans symbole)")
    p_addr.add_argument("file")
    p_addr.add_argument("vaddr", help="Adresse virtuelle hex, ex: 0xa0e4a14c")
    p_addr.add_argument("-o", "--output", help="Ecrit les octets bruts dans ce fichier (sinon hexdump stdout)")
    p_addr.add_argument("--len", type=int, default=256, help="Nombre d'octets a extraire")

    p_cmp = sub.add_parser("compare", help="Compare deux fichiers (diff structurel simple)")
    p_cmp.add_argument("file_a")
    p_cmp.add_argument("file_b")

    args = parser.parse_args()

    if args.command == "scan":
        report = scan_directory(args.directory)
        out = json.dumps(report, indent=2, ensure_ascii=False)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(out)
            print(f"Rapport écrit dans {args.output} ({report['total_files']} fichiers)")
        else:
            print(out)

    elif args.command == "elf":
        info = analyze_elf(args.file)
        print(json.dumps(info, indent=2, ensure_ascii=False))

    elif args.command == "entropy":
        data = read_bytes(args.file)
        print(f"Entropie globale: {shannon_entropy(data):.4f} bits/octet (max 8.0)")
        print(f"Taille: {len(data)} octets")
        print("\nEntropie par bloc (offset, entropie):")
        for off, e in entropy_by_blocks(data, args.block)[:80]:
            bar = "#" * int(e * 5)
            print(f"  {off:08x}  {e:5.2f}  {bar}")

    elif args.command == "decompress":
        data = read_bytes(args.file)
        results = try_decompress(data, args.max_offset)
        if not results:
            print("Aucune décompression réussie avec les algos/offsets testés.")
            print("Suggestions: format custom (LZ maison), pré-traitement XOR, ou offset > "
                  f"{args.max_offset} (augmentez --max-offset).")
        else:
            print(json.dumps(results, indent=2))

    elif args.command == "hexdump":
        data = read_bytes(args.file)
        print(hexdump(data, args.offset, args.len))

    elif args.command == "strings":
        data = read_bytes(args.file)
        for off, s in extract_strings(data, args.min):
            print(f"{off:08x}  {s}")

    elif args.command == "export":
        report = scan_directory(args.directory)
        if args.format == "json":
            export_json(report, args.output)
        elif args.format == "md":
            export_markdown(report, args.output)
        elif args.format == "html":
            export_html(report, args.output)
        print(f"Export {args.format} écrit dans {args.output}")

    elif args.command == "symbols":
        amin = int(args.addr_min, 16) if args.addr_min else None
        amax = int(args.addr_max, 16) if args.addr_max else None
        result = list_symbols(args.file, grep=args.grep, show_all=args.all, addr_min=amin, addr_max=amax)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.command == "dwarf-files":
        result = dwarf_source_files(args.file)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.command == "section-dump":
        data, meta = dump_section(args.file, args.section)
        if data is None:
            print(json.dumps(meta, indent=2, ensure_ascii=False))
        elif args.output:
            with open(args.output, "wb") as f:
                f.write(data)
            print(f"Section '{args.section}' ({len(data)} octets) ecrite dans {args.output}")
        else:
            print(f"Section '{args.section}' - taille {meta['size']} - addr {meta['addr']}")
            print(hexdump(data, 0, min(args.len, len(data))))

    elif args.command == "symbol-dump":
        data, meta = dump_symbol_bytes(args.file, args.symbol)
        if data is None:
            print(json.dumps(meta, indent=2, ensure_ascii=False))
        elif args.output:
            with open(args.output, "wb") as f:
                f.write(data)
            print(f"Symbole '{args.symbol}' ({len(data)} octets) ecrit dans {args.output}")
        else:
            print(json.dumps(meta, indent=2, ensure_ascii=False))
            print(hexdump(data, 0, len(data)))

    elif args.command == "addr-dump":
        vaddr = int(args.vaddr, 16)
        data, meta = dump_addr(args.file, vaddr, args.len)
        if data is None:
            print(json.dumps(meta, indent=2, ensure_ascii=False))
        elif args.output:
            with open(args.output, "wb") as f:
                f.write(data)
            print(f"Adresse {args.vaddr} ({len(data)} octets) ecrite dans {args.output}")
        else:
            print(json.dumps(meta, indent=2, ensure_ascii=False))
            print(hexdump(data, 0, len(data)))

    elif args.command == "compare":
        a = read_bytes(args.file_a)
        b = read_bytes(args.file_b)
        print(f"{args.file_a}: {len(a)} octets, sha256={hashlib.sha256(a).hexdigest()[:16]}")
        print(f"{args.file_b}: {len(b)} octets, sha256={hashlib.sha256(b).hexdigest()[:16]}")
        common_len = min(len(a), len(b))
        diffs = sum(1 for i in range(common_len) if a[i] != b[i])
        print(f"Octets différents sur la zone commune ({common_len}): {diffs} "
              f"({100*diffs/common_len:.1f}% si tailles comparables)")
        # premier offset de divergence
        for i in range(common_len):
            if a[i] != b[i]:
                print(f"Première divergence à l'offset {i:#x}")
                break


if __name__ == "__main__":
    main()