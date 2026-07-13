import json
import sys
from lexianalyzer import dump_addr, hexdump

LEAD_SYS_PATH = "core/windows/Lead.sys"
TARGET_VADDR = 0xa0e4a14c
EXTRACT_LEN = 256 

print(f"[*] Extraction à l'adresse : {hex(TARGET_VADDR)}...")

try:
    data, meta = dump_addr(LEAD_SYS_PATH, TARGET_VADDR, EXTRACT_LEN)
    if data is None:
        print(f"[-] Échec : {json.dumps(meta)}")
    else:
        with open("decipher_real.bin", "wb") as f:
            f.write(data)
        print(f"[+] Extraction réussie dans 'decipher_real.bin'")
        print("\n[*] Premier aperçu des octets machine bruts :")
        print(hexdump(data, 0, 64))
except Exception as e:
    print(f"[-] Erreur : {e}")