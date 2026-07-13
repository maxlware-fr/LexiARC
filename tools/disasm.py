#!/usr/bin/env python3
"""
disasm.py — Désassembleur Score7 (Sunplus/GeneralPlus S+core), reconstruction.

IMPORTANT — ce qui est reconstruit vs ce qui manque :

[OK] La segmentation en instructions (16 bits / 32 bits / PCE) est l'algorithme
     déjà validé en session précédente (cf CLAUDE.md §2) :
       - bit15(low) == 0                -> instruction 16 bits
       - bit15(low) == 1 et bit15(high) == 1 -> instruction 32 bits
       - bit15(low) == 1 et bit15(high) == 0 -> PCE (deux 16 bits parallèles)
     C'est la partie qui avait été "validée par les cibles de branchement" :
     tous les branchements retombaient pile sur des débuts d'instructions.

[MANQUE] Les tables de décodage exactes (quels bits = quel registre, quel
     opcode = quelle mnémonique) venaient de la session précédente et n'ont
     PAS été sauvegardées dans un fichier — seulement leur sortie dans le
     chat, aujourd'hui perdue. Je ne les invente pas ici : `decode_fields()`
     reste un stub explicite (voir plus bas) tant qu'on ne les a pas
     reconstruites pour de vrai, soit en retrouvant une source fiable
     (MAME/Ghidra), soit en re-dérivant à la main depuis les binaires connus.

Usage:
    python3 disasm.py <fichier.bin> [--base 0xa0e4a14c]
    python3 disasm.py decipher_real.bin --base 0xa0e4a14c
"""
import argparse
import struct


def instruction_stream(data: bytes, base_addr: int = 0):
    """Découpe un flux d'octets en instructions 16/32/PCE.
    Retourne une liste de dicts: addr, kind, size, raw (bytes), words (tuple d'int)."""
    out = []
    i = 0
    n = len(data)
    while i + 2 <= n:
        low = struct.unpack_from("<H", data, i)[0]
        if (low & 0x8000) == 0:
            out.append({
                "addr": base_addr + i, "kind": "16", "size": 2,
                "raw": data[i:i + 2], "words": (low,),
            })
            i += 2
            continue
        if i + 4 > n:
            # halfword orphelin en fin de buffer — pas assez de données pour trancher
            out.append({
                "addr": base_addr + i, "kind": "16?(tronque)", "size": 2,
                "raw": data[i:i + 2], "words": (low,),
            })
            i += 2
            continue
        high = struct.unpack_from("<H", data, i + 2)[0]
        if (high & 0x8000) != 0:
            out.append({
                "addr": base_addr + i, "kind": "32", "size": 4,
                "raw": data[i:i + 4], "words": (low, high),
            })
        else:
            out.append({
                "addr": base_addr + i, "kind": "pce", "size": 4,
                "raw": data[i:i + 4], "words": (low, high),
            })
        i += 4
    return out


def decode_fields(instr):
    """STUB VOLONTAIRE. Retourne None tant que les vraies tables de décodage
    (registres/immédiats/mnémoniques) n'ont pas été reconstruites. Ne pas
    remplir avec des valeurs devinées — mieux vaut 'inconnu' que faux."""
    return None


def format_instruction(instr):
    words_hex = " ".join(f"{w:04x}" for w in instr["words"])
    fields = decode_fields(instr)
    mnem = fields["mnemonic"] if fields else "?"
    return f"{instr['addr']:08x}  [{instr['kind']:>12}]  {words_hex:<12}  {mnem}"


def guess_branch_targets(instrs):
    """Heuristique de validation utilisée en session précédente : repère les
    halfwords bas dont le motif ressemble à un branchement/jump connu du RISC
    Score (approx. générique — PAS une vraie table d'opcodes) et vérifie que
    l'adresse cible calculée retombe bien sur un début d'instruction décodée.
    Sert à re-valider empiriquement le découpage 16/32/PCE sur un nouveau
    binaire, pas à identifier les mnémoniques."""
    valid_addrs = {ins["addr"] for ins in instrs}
    return valid_addrs  # exposé pour usage interactif / futurs scripts de check


def main():
    ap = argparse.ArgumentParser(description="Désassembleur Score7 (segmentation validée, décodage en attente)")
    ap.add_argument("file")
    ap.add_argument("--base", default="0x0", help="Adresse virtuelle de base (hex)")
    args = ap.parse_args()

    base = int(args.base, 16)
    with open(args.file, "rb") as f:
        data = f.read()

    instrs = instruction_stream(data, base)
    for ins in instrs:
        print(format_instruction(ins))

    counts = {}
    for ins in instrs:
        counts[ins["kind"]] = counts.get(ins["kind"], 0) + 1
    print(f"\n--- {len(instrs)} instructions décodées (taille seulement) : {counts} ---")
    print("Mnémoniques = '?' partout : les tables de décodage réelles restent à reconstruire.")


if __name__ == "__main__":
    main()