# CLAUDE.md — Reverse Engineering Lexibook JG7420AV

Document de suivi du projet. Objectif de test : documenter l'architecture complète de la console, comprendre/extraire le format `.wxn`, et (à terme) alimenter un émulateur ou un meilleur support MAME.

Objectif final : Créer un émulateur fonctionnel de la console, et pouvoir créer des ROMs de jeux.

---

## 1. Le début — contexte et matériel de départ

- **Matériel** : dump complet de la carte SD d'origine (dossier local `core/`), organisé par catégories de jeux (`Fun`, `Sports`, `Classroom`, `System`, `windows`...).
- **Fichiers rencontrés** :
  - `spg.elf` (et variantes : `123.elf`, `rom.elf`, `zls.elf`, etc.) — un par dossier de jeu "lourd" avec ressources `.bin` dans un sous-dossier (ex: `PIG/`)
  - `.wxn` — fichiers standalone sans ELF associé, dans `Fun\Game Player\` (89 fichiers)
  - `.bin`, `.64`, `.drm`, `.km`, `.jp`, `.mxb0` — ressources diverses
  - `windows\Lead.sys` — gros ELF (1.6 Mo) à la racine de `windows\`, hors arborescence de jeu
- **Outil construit** : `lexianalyzer.py`, script Python CLI dédié (scan récursif, analyse ELF, entropie, signatures, décompression multi-algo, extraction de symboles/DWARF/sections/octets de symbole). Fourni et mis à jour au fil de la session — dernière version toujours disponible en sortie du chat.

---

## 2. Le présent — ce qui est confirmé

### Architecture matérielle
- **CPU confirmé** : `e_machine = 0x87` = `EM_SCORE` → cœur **Sunplus/GeneralPlus S+core (Score7)**, RISC 32 bits.
- **SoC confirmé** : **SPG293** (famille SPG29x), via les chemins DWARF (`SPG293_Change_Clk.c`, `SPG293_NANDDriver_1.2.0.2`).
- **Modèle confirmé dans les métadonnées de compilation** : chemin `H:\Work_0\spg\Lexibook_JG7420\HK_Workspace\...` — équipe de dev basée à Hong Kong, nom de projet = votre console exacte.
- **SDK constructeur** : `SPGLib29x`, avec des traces d'un toolchain antérieur nommé `SUBOR29X` (Subor, fabricant chinois bien connu de ce type de SoC — leur SDK a été relicencié à d'autres marques, ce qui explique les similitudes avec le pilote MAME `spg29x_lexibook_jg7425.cpp`, console cousine déjà documentée par la communauté MAME).
- **Toolchain d'origine** : GCC + binutils avec target `score-elf` (support existant dans binutils/gcc entre ~2009 et ~2015, retiré depuis pour désuétude — le mirroir GitHub `bminor/binutils-gdb` s'est avéré introuvable, à revérifier avec un autre mirroir type `gnutools/binutils-gdb` si besoin de reconstruire un désassembleur).

### Formats de fichiers
| Format | Statut | Détail |
|---|---|---|
| `.elf` (jeux autonomes) | ✅ Compris | ELF32 Score7 standard, souvent **non strippé avec DWARF complet** (symboles + fichiers source d'origine visibles) |
| `.wxn` avec header `4e 45 53 1a` (7 fichiers) | ✅ Résolu | **ROMs NES brutes (header iNES standard)**, jouées par un émulateur NES embarqué dans `Lead.sys` (`load_nes`, `Entry_Single_Nes`) |
| `.wxn` avec header `6d 66 63 00` "mfc" (82 fichiers) | 🔶 En cours | Hypothèse forte : **conteneur chiffré contenant un ELF Score7 compact**, décodé à la volée par `Lead.sys` |
| `.drm` (1383 fichiers) | ✅ Résolu | Header `"SP_ToneMaker"` — format audio Sunplus documenté (partiellement) par le projet communautaire [SPG2xx-sound-engines](https://github.com/BLiNXthetimesweeperGOD/SPG2xx-sound-engines) |
| `.km`, `.jp` | 🔶 Hypothèse | Probablement liés à l'app piano/notation musicale (`Classroom\Music\...\简谱表` = "table de jianpu/notation numérique chinoise") |
| `.mxb0` | 🔶 Hypothèse | Entropie quasi nulle (1.317) — possible sortie décompressée d'un `.wxn` correspondant (`stubgame.wxn` + `stubgame.mxb0`), jamais confirmée dynamiquement |

### Fonction anonyme 0xa0e4a14c (analyse structurelle, sans mnémoniques)
- Taille réelle : **210 octets utiles** (0xa0e4a14c → 0xa0e4a21e), les 2 derniers octets
  étant du padding d'alignement avant `Deciphering_Data_And_DMA` (0xa0e4a220).
- Motif répété 9× : `901a 94fa` + `80XX 84f4`, `XX` multiple de 8 (10,18,28,30,40,48,b0)
  → signature probable d'écriture de champs successifs d'une structure alignée 8 octets
  (table de descripteurs DMA scatter-gather).
- 2 valeurs répétées identiques sans variation : `8000 c0c6` (×3), `8000 d0c7` (×4)
  → probables accès fixes à des registres MMIO.
- **Hypothèse révisée** : cette fonction initialise une table de descripteurs DMA plutôt
  que d'implémenter elle-même l'algo de déchiffrement — le déchiffrement réel serait fait
  par le contrôleur DMA matériel via ces descripteurs. À vérifier en recoupant avec les
  registres DMA du SPG293 documentés dans le code source d'`emu293` (voir découverte ci-dessous).
- Outils utilisés : `lexianalyzer.py addr-dump` (nouvelle commande ajoutée cette session)
  + `disasm.py` (segmentation 16/32/PCE bits, validée, mais SANS table de mnémoniques —
  volontairement laissée en stub, voir `score7_emu/disasm.py`).

### Le pipeline de chargement `.wxn` (reconstruit par analyse statique de `Lead.sys`)
Chaîne de fonctions identifiées, dans l'ordre probable d'exécution :
```
public_Init_mxb / public_Open_mxb   (0xa0e44738 / 0xa0e44780 — trampolines C, mxb_public.c)
        ↓
Deciphering_Data_And_DMA            (0xa0e4a220, 108 octets — "déchiffrement + DMA")
        ↓
set_mxb_disk                        (0xa0e4a28c, 148 octets — monte un disque virtuel temp)
        ↓
Entry_Single_Elf  /  Entry_Single_Nes   (dispatch selon le type de contenu déchiffré)
        ↓
load_elf  /  load_nes
```
- Preuve textuelle à l'appui : chaînes `\tempmxb\`, `\tempmxb\1`, `\tempmxb\2` trouvées dans `.rodata` de `Lead.sys` — la console extrait physiquement les `.wxn` vers un dossier temporaire avant exécution.
- `Deciphering_Data_And_DMA` ne fait que 108 octets → quasi certainement un **XOR/LFSR simple** lié au contrôleur DMA matériel (pas un vrai algorithme cryptographique), cohérent avec le "descrambler" léger courant sur les puces Sunplus/GeneralPlus.
- La section ELF custom `.mxb` (1216 octets, dans `Lead.sys`) contient du **code machine Score7 brut** (pas une table de config comme supposé initialement) — probablement un petit overlay copié en RAM à l'exécution.

### Fausses pistes écartées
- Décompression zlib/gzip/lzma/bz2/lz4 par balayage d'offsets sur `.wxn` → résultats obtenus étaient du **bruit statistique** (entropie source trop élevée pour distinguer un vrai flux Deflate d'un faux positif).
- `decompile_wxn.py` et `stubgame.mxb0` trouvés dans `Game Player\` → ancien test personnel de l'utilisateur, pas une trace du développeur d'origine.
- Tentative de compiler un `objdump` Score7 via `bminor/binutils-gdb` → dépôt introuvable/inaccessible, abandonné.

---

## 3. Le futur — prochaines étapes, par ordre de priorité

### 🔴 DÉCOUVERTE MAJEURE (12/07) — un émulateur SPG293 existe déjà et fonctionne
[`gatecat/emu293`](https://github.com/gatecat/emu293) — émulateur C++ complet, GPL, ciblant
spécifiquement le **Lexibook JG7425** (console cousine de la JG7420AV, même OEM **Subor**)
sur SoC **Sunplus SPG293**. Il accepte `Lead.sys` directement en entrée :
```
./emu293 Lead.sys sd_card.img
```
- Cœur CPU S+core basé sur `LiraNura/hyperscan-emulator` (crédité dans le README, réutilisable)
- Déjà fonctionnel : CPU, MIU (mémoire), VDU (vidéo), timers, SPU (son wavetable — imparfait), IRQ
- Limites connues (assumées par l'auteur) : quelques bugs graphiques, timing vsync imprécis, SPU imparfait
- Supporte aussi Subor A21 et Zone 3D (autres systèmes du même OEM)

**Ça change la priorité n°1** : au lieu de reconstruire un cœur Score7 + désassembleur +
carte mémoire depuis zéro, la vraie priorité devient de **tester si `Lead.sys` + la carte SD
(JG7420AV) tournent tel quel dans emu293**, vu le même OEM/SoC. Reste à vérifier :
- `sd_card.img` doit être une image brute (raw/dd) de la carte SD, pas juste le dossier
  `core/` extrait — à reconstruire si on n'a que les fichiers extraits (FAT32 + recopie).
- Compatibilité JG7420AV vs JG7425 (probable mais pas garantie — différences possibles
  au niveau des jeux/ressources spécifiques).
- Si ça tourne : objectif "émulateur" en grande partie déjà atteint, effort à réorienter
  vers correction de bugs spécifiques JG7420AV plutôt que réécriture de zéro.
- Si ça ne tourne pas : le code source d'emu293 reste une référence directe et fiable
  pour le cœur CPU S+core et la carte mémoire SPG293 (bien plus fiable que de deviner).

---

### Priorité 1 — Obtenir un désassembleur Score7 fonctionnel
C'est le vrai goulot d'étranglement actuel : on a localisé les fonctions clés mais pas leur contenu en assembleur lisible.
- Chercher un autre mirroir binutils avec support `score-elf` encore présent (ex. `gnutools/binutils-gdb`, ou un tag spécifique < 2015 sur le mirroir officiel `sourceware.org` en dehors du bac à sable)
- Alternative : chercher si un module Ghidra communautaire "Score" existe déjà (recherche à relancer, rien de confirmé pour l'instant)
- Alternative : utiliser le core CPU **Score dans MAME** (`src/devices/cpu/score/`) comme référence d'encodage pour un mini-désassembleur Python fait maison, ciblé uniquement sur les ~5 fonctions qui nous intéressent (pas besoin d'un désassembleur complet)

### Priorité 2 — Extraire et examiner le code des fonctions clés
Une fois un désassembleur dispo, désassembler dans cet ordre :
1. `Deciphering_Data_And_DMA` (0xa0e4a220, 108 octets) — **la cible n°1**, c'est probablement là que vit la clé/l'algo de désembrouillage
2. `set_mxb_disk` (0xa0e4a28c, 148 octets)
3. `public_Open_mxb` / `public_Init_mxb` (mxb_public.c)
4. Le contenu de la section `.mxb` (1216 octets, code Score7 brut)

Commandes déjà prêtes dans l'outil pour extraire les octets bruts de ces fonctions :
```powershell
python lexianalyzer.py symbol-dump "core/windows/Lead.sys" Deciphering_Data_And_DMA -o deciphering.bin
python lexianalyzer.py symbol-dump "core/windows/Lead.sys" set_mxb_disk -o setmxbdisk.bin
python lexianalyzer.py section-dump "core/windows/Lead.sys" .mxb -o mxb_section.bin
```

### Priorité 3 — Vérifier l'hypothèse "wxn = ELF chiffré"
- Une fois l'algo de `Deciphering_Data_And_DMA` connu, déchiffrer un `.wxn` "mfc" (ex: `alienis.wxn`) et vérifier si le résultat commence par `7F 45 4C 46` (magic ELF)
- Si confirmé : écrire un script `wxn_to_elf.py` de conversion automatique pour toute la bibliothèque de 82 jeux

### Priorité 4 — Compléter la documentation du reste de l'écosystème (secondaire, en parallèle si utile)
- `.drm` / SP_ToneMaker : contribuer les échantillons Lexibook au projet [SPG2xx-sound-engines](https://github.com/BLiNXthetimesweeperGOD/SPG2xx-sound-engines) (non couvert par eux actuellement)
- `.km` / `.jp` : investigation basse priorité, format probablement propre à l'appli piano/notation musicale
- `.mxb0` : à ré-analyser une fois l'algo de déchiffrement connu (test de cohérence : `stubgame.mxb0` devrait correspondre au contenu déchiffré de `stubgame.wxn`)

### Rappel — ce qui est délibérément écarté
- Pas d'extraction dynamique sur la console physique (risque de dommage sur un modèle qui n'est plus commercialisé — décision de l'utilisateur, à respecter)

---

## Annexe — outil `lexianalyzer.py`, commandes disponibles à ce stade
```
scan <dossier> [-o out.json]                          Scan complet + entropie + signatures
elf <fichier.elf>                                      Headers, sections, segments, symboles (aperçu)
entropy <fichier> [--block N]                           Entropie globale + par blocs
decompress <fichier> [--max-offset N]                   Essai multi-algo/multi-offset (zlib/gzip/lzma/bz2/lz4)
hexdump <fichier> [--offset N] [--len N]
strings <fichier> [--min N]
symbols <fichier> [--grep MOT] [--all] [--addr-min HEX] [--addr-max HEX]   Symboles filtrés par nom ou plage d'adresse
dwarf-files <fichier>                                   Liste des fichiers source d'origine (DWARF)
section-dump <fichier> <section> [-o out.bin] [--len N] Extrait une section ELF nommée
symbol-dump <fichier> <symbole> [-o out.bin]            Extrait les octets bruts d'une fonction/objet précis
export <dossier> --format json|md|html -o out           Export scan complet
compare <fichierA> <fichierB>                           Diff structurel simple
```

## 4. Retranscription des instructions, de ces recherches etc.

```
CLAUDE.md
114 lignes

md


The user prompt is empty, so I cannot determine the primary language. However, based on the thinking block being in English, here is my summary: Unearthed specialized plugin and verified its relevance
The user prompt is empty, so I cannot determine the primary language. However, based on the thinking block being in English, here is my summary: Unearthed specialized plugin and verified its relevance
Trouvé — il existe déjà un module Ghidra communautaire pour le S+core7 : sronco/ghidra-score7 ("Ghidra Sunplus S+core7"), ce qui répond directement à la Priorité 1 de ton doc. Ça évite de repartir de zéro avec le mini-désassembleur Python fait maison basé sur MAME.

Côté binutils, la piste gnutools/binutils-gdb (miroir GitHub) existe bien et est à jour quotidiennement — et score-*-elf apparaît toujours dans gas/configure.tgt sur les miroirs actuels, donc le support n'a pas totalement disparu du code source, même s'il faudra probablement remonter à un tag antérieur à ~2015 pour avoir un binaire qui le compile réellement (le support a été retiré depuis, comme noté dans ton doc).

Je te propose de vérifier tout de suite si ghidra-score7 couvre les instructions dont tu as besoin pour désassembler Deciphering_Data_And_DMA (108 octets seulement — probablement une poignée d'instructions arithmétiques/logiques + boucle), plutôt que de te lancer dans la compilation binutils qui est plus lourde. Tu veux que je regarde le contenu du dépôt (état d'avancement, instructions couvertes, dernière mise à jour) pour évaluer s'il est utilisable tel quel ?

essaye mais je veux faire un émulateur propre


Évalué l'ampleur du projet d'émulateur et proposé approche progressive
Évalué l'ampleur du projet d'émulateur et proposé approche progressive
Bon, j'ai deux pistes concrètes, et une des deux change pas mal le plan pour un émulateur propre :

1. ghidra-score7 — utilisable mais limité. C'est un module pour le Score7 du Mattel HyperScan (pas ta console, mais même cœur CPU), écrit en Java/SLEIGH + scripts Python. Manques connus dans le README : exécution parallèle 16-bit, et les opcodes rorc/rolc/roric/rolic/lcb/lcw/lce/scb/scw/sce. Pour tes ~5 fonctions cibles (108-1216 octets), risque faible d'y tomber, mais pas garanti — à vérifier au cas par cas.

2. Découverte plus importante : MAME a déjà un désassembleur Score complet et maintenu (src/devices/cpu/score/scoredsm.h, intégré à l'outil unidasm). C'est probablement plus fiable que le module Ghidra communautaire partiel, et surtout utilisable immédiatement sans rien compiler côté Ghidra :

bash
# compiler juste l'outil unidasm depuis les sources MAME (pas tout MAME)
make SUBTARGET=unidasm SOURCES= TOOLS=1 REGENIE=1
./unidasm -arch score deciphering.bin
Ce que je n'ai pas encore confirmé : est-ce que MAME a aussi un vrai cœur d'exécution Score (interpréteur avec registres, cycles, etc.), ou seulement le désassembleur ? Je n'ai trouvé que la trace du désassembleur pour l'instant. C'est la question clé pour ton objectif "émulateur propre" — si le core d'exécution existe déjà et est solide, autant s'en inspirer directement (licence GPL-2.0, donc réutilisable en credit) plutôt que de réinventer un interpréteur Score7 à partir de zéro.

Pour un émulateur propre, la portée réelle est plus large que juste déchiffrer les .wxn :

Cœur CPU Score7 (interpréteur ou JIT)
Carte mémoire + registres du SoC SPG293 (vidéo, son SP_ToneMaker, DMA, timers, GPIO)
Chargeur rejouant le pipeline .wxn → tempmxb → load_elf/load_nes que tu as déjà reconstruit
Je te propose de vérifier maintenant si MAME a un vrai core d'exécution Score (pas juste le désasm) — ça détermine si Priorité 1 se résout en une commande ou s'il faut repartir sur Ghidra/écriture manuelle. Je lance la recherche ?


lexianalyzer.py
py

vsy je peux t'aider car j'ai le fichier de la carte SD contenant tout les fichiers. Voici aussi le .py utilisé pour faire les tests


Acknowledged limitations, pivoted toward concrete data analysis
Acknowledged limitations, pivoted toward concrete data analysis
Bien reçu — j'ai le script. Je peux directement exécuter lexianalyzer.py ici si tu m'envoies les fichiers correspondants (j'ai un environnement bash/Python).

Côté MAME : je n'ai confirmé que le désassembleur Score (cpu/score/scoredsm.h, utilisé par unidasm). Je n'ai pas trouvé de trace claire d'un vrai cœur d'exécution (score.cpp avec execute_run, registres, etc.) dans mes recherches — soit il n'existe pas dans MAME, soit il est ailleurs/pas assez documenté publiquement pour apparaître dans les résultats. Je préfère être honnête là-dessus plutôt que d'assumer : à vérifier en clonant le dépôt et en cherchant EM_SCORE / "score" dans src/mame/*.cpp (drivers) pour voir si un système l'utilise réellement, ce qui confirmerait un core complet.

En attendant, pour avancer concrètement sur la Priorité 2 de ton doc (désassembler les 3 fonctions clés), le plus efficace c'est que tu m'envoies directement les fichiers plutôt que je devine :

core/windows/Lead.sys — pour que je lance symbol-dump sur Deciphering_Data_And_DMA, set_mxb_disk, public_Open_mxb/public_Init_mxb, et section-dump .mxb
Un .wxn avec header mfc\x00 (ex: alienis.wxn) — pour tester le déchiffrement une fois l'algo compris
stubgame.wxn + stubgame.mxb0 — pour la vérification croisée déchiffré/attendu
Si tu peux uploader au moins Lead.sys, je lance tout de suite symbol-dump + hexdump + strings dessus et on regarde ce qu'on a en clair avant même de se soucier d'un désassembleur — ça va déjà révéler pas mal (structure de la fonction, constantes, éventuelles tables XOR visibles en dur).


Lead.sys
sys


Exécuté 2 commandes
Exécuté 2 commandes
Confirmé — même fichier, 6538 symboles, DWARF complet. Extrayons les 3 cibles.


Extraire les fonctions cibles et lister les symboles mxb
Extraire les fonctions cibles et lister les symboles mxb
Bon, on a bien tout. Extrayons aussi public_Init_mxb, public_Open_mxb, la section .mxb, et regardons le contenu brut.


Identified encoding inconsistencies and pivoted toward authoritative source code
Identified encoding inconsistencies and pivoted toward authoritative source code
Le brute-force ne converge pas vers une hypothèse cohérente entre les deux fonctions (règles différentes trouvées pour chacune) — signe que je devine mal la logique de split 16/32-bit plutôt que de l'avoir. Plutôt que de te sortir un désassemblage non fiable, je vais chercher la fonction s7_print_insn elle-même (celle qui décide vraiment comment lire le flux d'instructions), qui se trouve juste après ce que j'ai déjà récupéré.


The user prompt is empty, so there is no primary language specified. However, based on the thinking block being in English, here is the summary: Architected instruction decoding algorithm leveraging bit patterns
The user prompt is empty, so there is no primary language specified. However, based on the thinking block being in English, here is the summary: Architected instruction decoding algorithm leveraging bit patterns
Voilà, j'ai l'algorithme exact de s7_print_insn. La règle : bit15 du halfword bas ET bit15 du halfword haut tous deux à 1 → instruction 32 bits (avec dépouillement de parité) ; bit15 bas à 0 → instruction 16 bits simple ; bit15 bas=1/haut=0 → PCE (deux 16-bit parallèles). Implémentons ça correctement.


Deciphered assembly functions and validated disassembly accuracy
Deciphered assembly functions and validated disassembly accuracy
Le désassembleur fonctionne — et il est validé de façon fiable : toutes les cibles de branchement (beq, j, jl) tombent exactement sur des débuts d'instructions décodées, ce qui confirme que l'algorithme est correct. Complétons avec les 2 fonctions restantes et la section .mxb.


The user prompt is empty, so there is no primary language established. However, following the instruction to write in the language of the prompt, and given that no prompt exists, I'll provide a summary based on the thinking block's content: Investigated memory routines and revised initial decryption hypothesis
The user prompt is empty, so there is no primary language established. However, following the instruction to write in the language of the prompt, and given that no prompt exists, I'll provide a summary based on the thinking block's content: Investigated memory routines and revised initial decryption hypothesis
Le désassembleur fonctionne parfaitement — toutes les cibles de saut tombent pile sur des débuts d'instructions valides, aucune erreur de décodage. Et ça bouscule pas mal l'hypothèse de départ.

set_mxb_disk confirme exactement ton hypothèse : un switch à 3 branches sur la valeur [r2+12] (0, 1 ou 2), chacune construisant une chaîne via deux registres (r4/r5) puis appelant une fonction à 0xa0e916e4 (probablement un sprintf/constructeur de chemin) — cohérent avec les chaînes \tempmxb\1 et \tempmxb\2 que tu avais repérées dans .rodata.

Deciphering_Data_And_DMA — surprise : ce n'est pas l'algo de déchiffrement lui-même. Elle fait : charger l'adresse d'un registre MMIO, y positionner un bit (OR 1), appeler une sous-fonction à 0xa0e4a14c, puis effacer ce même bit (AND 0xFFFE). Classique pattern "arme le DMA → laisse une autre fonction faire le vrai travail → désarme le DMA". Le vrai déchiffrement/désembrouillage vit donc probablement dans cette fonction 0xa0e4a14c, qu'on n'avait pas encore identifiée.

Section .mxb — autre surprise : ce n'est pas une table de config ni un overlay de code métier, c'est une routine générique de copie mémoire (boucle lhu/sh puis lw/sw, compteur de répétition via sr0) — une primitive utilitaire, pas le déchiffreur.

Ça change la cible prioritaire : la vraie fonction à extraire et désassembler maintenant, c'est celle à 0xa0e4a14c. Tu veux que je l'extraie et la décode (je n'ai que son adresse, il faudrait soit son nom de symbole si lexianalyzer.py symbols --addr-min 0xa0e4a14c en trouve un, soit un dump brut par adresse) ?

essaye de chercher. Sinon, je peux le faire si c'est du python. tu me donne le code python à éxécuter et je peux le faire. Si j'ai bien compris, tu est au point ou le  fichier système de console peux être décompilé (donc possible ensuite de l'émuler ?)
```

### Annexe - décompilation de Lead.sys

```
cd /home/claude && python3 lexianalyzer.py elf Lead.sys
Sortie

{
  "path": "Lead.sys",
  "size": 1603098,
  "class": "ELF32",
  "endianness": "little",
  "e_machine_raw": 135,
  "e_machine_hex": "0x87",
  "e_machine_guess": "Sunplus/GeneralPlus S+core (Score7) — SoC SPG29x/SPG293 (confirme JG7420AV/JG7425)",
  "entry_point": "0xa0e01000",
  "sections": [
    {
      "name": "",
      "type": "SHT_NULL",
      "addr": "0x0",
      "size": 0
    },
    {
      "name": ".exception",
      "type": "SHT_PROGBITS",
      "addr": "0xa0e001fc",
      "size": 3336
    },
    {
      "name": ".hardware_init",
      "type": "SHT_PROGBITS",
      "addr": "0xa0e01000",
      "size": 184
    },
    {
      "name": ".init",
      "type": "SHT_PROGBITS",
      "addr": "0xa0e010b8",
      "size": 112
    },
    {
      "name": ".text",
      "type": "SHT_PROGBITS",
      "addr": "0xa0e01130",
      "size": 624340
    },
    {
      "name": ".body",
      "type": "SHT_PROGBITS",
      "addr": "0xa0e99810",
      "size": 6864
    },
    {
      "name": ".mxb",
      "type": "SHT_PROGBITS",
      "addr": "0xa0e9b2e0",
      "size": 1216
    },
    {
      "name": ".fini",
      "type": "SHT_PROGBITS",
      "addr": "0xa0e9b7a0",
      "size": 24
    },
    {
      "name": ".rodata",
      "type": "SHT_PROGBITS",
      "addr": "0xa0e9b7c0",
      "size": 52400
    },
    {
      "name": ".data",
      "type": "SHT_PROGBITS",
      "addr": "0xa0ea8570",
      "size": 129872
    },
    {
      "name": ".eh_frame",
      "type": "SHT_PROGBITS",
      "addr": "0xa0ec80c0",
      "size": 4
    },
    {
      "name": ".ctors",
      "type": "SHT_PROGBITS",
      "addr": "0xa0ec80c4",
      "size": 8
    },
    {
      "name": ".dtors",
      "type": "SHT_PROGBITS",
      "addr": "0xa0ec80cc",
      "size": 8
    },
    {
      "name": ".jcr",
      "type": "SHT_PROGBITS",
      "addr": "0xa0ec80d4",
      "size": 4
    },
    {
      "name": ".sdata",
      "type": "SHT_PROGBITS",
      "addr": "0xa0ec80d8",
      "size": 196
    },
    {
      "name": ".sbss",
      "type": "SHT_NOBITS",
      "addr": "0xa0ec819c",
      "size": 448
    },
    {
      "name": ".bss",
      "type": "SHT_NOBITS",
      "addr": "0xa0ec835c",
      "size": 522032
    },
    {
      "name": ".stab",
      "type": "SHT_PROGBITS",
      "addr": "0x0",
      "size": 18468
    },
    {
      "name": ".stabstr",
      "type": "SHT_STRTAB",
      "addr": "0x0",
      "size": 763
    },
    {
      "name": ".comment",
      "type": "SHT_PROGBITS",
      "addr": "0x0",
      "size": 3008
    },
    {
      "name": ".debug_aranges",
      "type": "SHT_PROGBITS",
      "addr": "0x0",
      "size": 2464
    },
    {
      "name": ".debug_pubnames",
      "type": "SHT_PROGBITS",
      "addr": "0x0",
      "size": 43864
    },
    {
      "name": ".debug_info",
      "type": "SHT_PROGBITS",
      "addr": "0x0",
      "size": 313894
    },
    {
      "name": ".debug_abbrev",
      "type": "SHT_PROGBITS",
      "addr": "0x0",
      "size": 27733
    },
    {
      "name": ".debug_line",
      "type": "SHT_PROGBITS",
      "addr": "0x0",
      "size": 58130
    },
    {
      "name": ".debug_frame",
      "type": "SHT_PROGBITS",
      "addr": "0x0",
      "size": 31248
    },
    {
      "name": ".debug_str",
      "type": "SHT_PROGBITS",
      "addr": "0x0",
      "size": 8993
    },
    {
      "name": ".debug_loc",
      "type": "SHT_PROGBITS",
      "addr": "0x0",
      "size": 59642
    },
    {
      "name": ".pdr",
      "type": "SHT_PROGBITS",
      "addr": "0x0",
      "size": 46176
    },
    {
      "name": ".shstrtab",
      "type": "SHT_STRTAB",
      "addr": "0x0",
      "size": 276
    },
    {
      "name": ".symtab",
      "type": "SHT_SYMTAB",
      "addr": "0x0",
      "size": 104608
    },
    {
      "name": ".strtab",
      "type": "SHT_STRTAB",
      "addr": "0x0",
      "size": 62938
    }
  ],
  "segments": [
    {
      "type": "PT_LOAD",
      "vaddr": "0xa0e00000",
      "filesz": 819612,
      "memsz": 1342092
    }
  ],
  "symbol_count": 6538,
  "symbols_sample": [
    "H:\\Work_0\\spg\\Lexibook_JG7420\\HK_Workspace\\Project\\AV\\body\\os_isr.s",
    "_exception_vec",
    "norm_debug_service",
    "general_vec",
    "general_service",
    "int1_vec",
    "int_service",
    "int2_vec",
    "int3_vec",
    "int4_vec",
    "int5_vec",
    "int6_vec",
    "int7_vec",
    "int8_vec",
    "int9_vec",
    "int10_vec",
    "int11_vec",
    "int12_vec",
    "int13_vec",
    "int14_vec",
    "int15_vec"
  ]
}
```
