# Console — Architecture matérielle

Informations techniques sur la console Lexibook **JG7420AV**, reconstruites par analyse statique du firmware (`Lead.sys`) et des ELF de jeux présents sur la carte SD d'origine.

## Identification

| Élément | Valeur | Source |
|---|---|---|
| CPU | Sunplus/GeneralPlus **S+core7** (Score7), RISC 32 bits | `e_machine = 0x87` (`EM_SCORE`) dans les en-têtes ELF |
| SoC | **SPG293** (famille SPG29x) | Chemins DWARF (`SPG293_Change_Clk.c`, `SPG293_NANDDriver_1.2.0.2`) |
| SDK constructeur | `SPGLib29x` | Symboles et chemins de build |
| Toolchain d'origine | GCC + binutils, cible `score-elf` | Support présent dans binutils/gcc entre ~2009 et ~2015, retiré depuis |
| Équipe de développement | Basée à Hong Kong | Chemins de build (`H:\Work_0\spg\Lexibook_JG7420\HK_Workspace\...`) |
| Origine du design | SDK dérivé d'un toolchain antérieur **SUBOR** (fabricant chinois de consoles), relicencié à Lexibook | Traces dans les chemins de build |

## Consoles apparentées

La **Lexibook JG7425** (221-en-1) utilise la même famille de SoC et est déjà documentée par la communauté :
- Pilote MAME : `spg29x_lexibook_jg7425.cpp`
- Émulateur dédié : [emu293](https://github.com/gatecat/emu293), qui prend en charge le JG7425 nativement (voir [Emulate](emulate.md))

Ces ressources ont servi de base de comparaison utile pour la JG7420AV.

## Jeu d'instructions Score7

Le CPU Score7 utilise un encodage **mixte 16/32 bits** (et un mode "PCE" combinant deux instructions 16 bits en parallèle dans un même mot de 32 bits). L'algorithme de découpage, confirmé par croisement avec le vrai désassembleur GNU binutils (`opcodes/score7-dis.c`) et validé empiriquement (toutes les cibles de branchement retombent sur des débuts d'instructions décodées) :

- Lire un mot de 32 bits (little-endian) à l'adresse courante : `b0 | b1<<8 | b2<<16 | b3<<24`
- Si bit 15 (bas) **et** bit 31 (haut) sont à 1 → instruction **32 bits** : dépouiller la parité (`ridparity = (given & 0x7FFF) | ((given & 0x7FFF0000) >> 1)`) avant de matcher la table d'opcodes
- Si bit 15 (bas) est à 0 → instruction **16 bits** simple
- Si bit 15 (bas) = 1 et bit 31 (haut) = 0 → **PCE** : deux instructions 16 bits indépendantes empaquetées dans le même mot de 32 bits

Un mini-désassembleur Python (`score_disasm.py` + table d'opcodes `score_opcodes.py`, transcrite depuis le source binutils officiel) a été construit sur cette base pour analyser des fonctions ciblées du firmware sans dépendre d'un toolchain complet.

## Registres MMIO connus

Découverts par désassemblage des fonctions de gestion DMA (`BLN_DMA`, `Deciphering_Data_And_DMA`, section `.mxb`) :

- Bloc de contrôle DMA à une base fixe (observée autour de `0x880d____`), avec des offsets pour :
  - source, destination, longueur du transfert
  - registre de configuration/mode (valeur observée `0x505`)
  - registre de statut avec bit de "busy" (bit `0x100`), interrogé en polling par le firmware pour détecter la fin de transfert
- Contrôleur `BUFCTL` (rencontré dans les logs emu293 sous forme d'écritures hors plage — implémentation incomplète côté émulateur, voir [Errors](errors.md))
- Contrôleur `BLNDMA` distinct du DMA générique, dédié au blit vidéo (observé lors du chargement du menu : `src1`, `src2`, `dest`, dimensions `w`/`h`)

## Ce qui reste à documenter

- Le détail exact du "descrambling" matériel des fichiers `.wxn` chiffrés (voir [Software](software.md)) — probablement une fonctionnalité du contrôleur DMA lui-même plutôt qu'un algorithme logiciel, mais non confirmé au bit près.
- La carte mémoire complète (au-delà des blocs DMA/BUFCTL/BLNDMA déjà identifiés).
- Le sous-système vidéo/PPU et audio/SPU matériel dans le détail (l'implémentation actuelle vient d'emu293, voir [Emulate](emulate.md), pas d'une analyse indépendante du vrai hardware Lexibook).
