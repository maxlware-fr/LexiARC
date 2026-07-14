# Software — Système et formats de fichiers

## Organisation de la carte SD

La carte SD d'origine est structurée en catégories de jeux (`Fun`, `Sports`, `Classroom`, `System`, `windows`...). Le firmware principal se trouve à `windows/Lead.sys` (ELF de ~1,6 Mo), en dehors de l'arborescence des jeux.

Deux types de contenus de jeu coexistent :
- **Jeux "lourds"** : un ELF (`spg.elf`, `rom.elf`, ou variantes) accompagné de ressources `.bin` dans un sous-dossier dédié
- **Jeux "légers"** : fichiers `.wxn` autonomes, principalement dans `Fun/Game Player/` (89 fichiers observés)

> ⚠️ **Piège de nommage** : certains noms de dossiers/fichiers contiennent des espaces (`Game Player`, `9 Ball`, etc.). Si vous reconstruisez une image SD avec un outil personnalisé, assurez-vous que l'espace est bien préservé dans le nom — un remplacement automatique de caractères "sûrs" qui exclurait l'espace produira une arborescence que le firmware ne retrouvera pas (symptôme observé : le menu de jeu affiche "Pls download..." car il ne trouve pas ses fichiers).

## Formats de fichiers identifiés

| Extension | Statut | Détail |
|---|---|---|
| `.elf` (jeux autonomes) | ✅ Compris | ELF32 Score7 standard, souvent non strippé avec DWARF complet (symboles + fichiers source d'origine visibles) |
| `.wxn` avec header `4E 45 53 1A` | ✅ Résolu | ROMs **NES brutes** (header iNES standard), jouées par un émulateur NES embarqué dans `Lead.sys` (`load_nes`, `Entry_Single_Nes`) |
| `.wxn` avec header `6D 66 63 00` ("mfc") | 🔶 Partiellement compris | Conteneur **chiffré/désembrouillé** contenant très probablement un ELF Score7 compact, traité à la volée par le pipeline ci-dessous |
| `.drm` | ✅ Résolu | Header `"SP_ToneMaker"` — format audio Sunplus, partiellement documenté par le projet communautaire [SPG2xx-sound-engines](https://github.com/BLiNXthetimesweeperGOD/SPG2xx-sound-engines) |
| `.km`, `.jp` | 🔶 Hypothèse | Probablement liés à une application piano/notation musicale (présence de tables "jianpu"/notation numérique chinoise dans `Classroom/Music/`) |
| `.mxb0` | 🔶 Hypothèse | Entropie quasi nulle — possible sortie décompressée d'un `.wxn` correspondant, jamais confirmée dynamiquement |

## Pipeline de chargement des `.wxn`

Reconstruit par analyse statique de `Lead.sys` (désassemblage Score7 + chaînes trouvées en `.rodata`) :

```
public_Init_mxb / public_Open_mxb   (trampolines C, mxb_public.c)
        │
        ▼
Deciphering_Data_And_DMA            (arme un bit MMIO, appelle BLN_DMA, désarme le bit)
        │
        ▼
BLN_DMA                             (séquence de contrôle DMA matérielle : programme
                                      src/dst/longueur, lance le transfert, poll le
                                      statut jusqu'à fin, accuse réception)
        │
        ▼
set_mxb_disk                        (monte un "disque" virtuel temporaire —
                                      switch à 3 branches selon un paramètre,
                                      construit un chemin \tempmxb\1 ou \tempmxb\2)
        │
        ▼
Entry_Single_Elf  /  Entry_Single_Nes   (dispatch selon le type de contenu)
        │
        ▼
load_elf  /  load_nes
```

**Point important** : contrairement à l'hypothèse initiale d'un simple XOR/LFSR logiciel, l'analyse a montré que `Deciphering_Data_And_DMA` ne fait qu'armer/désarmer un bit de registre MMIO autour d'un appel à `BLN_DMA`, qui est lui-même une séquence de contrôle DMA matérielle standard (programmation source/dest/longueur, lancement, attente de fin par polling). Le "déchiffrement" est donc probablement une **fonctionnalité intégrée au contrôleur DMA matériel** (descrambling à la volée, courant sur ce type de SoC pour la protection de contenu), pas un algorithme logiciel isolé qu'on pourrait extraire et réimplémenter facilement.

Preuve textuelle à l'appui : les chaînes `\tempmxb\`, `\tempmxb\1`, `\tempmxb\2` sont présentes en dur dans `.rodata` de `Lead.sys` — la console extrait physiquement le contenu déchiffré vers un dossier temporaire avant exécution.

## Section `.mxb` (ELF `Lead.sys`)

Contrairement à l'hypothèse initiale ("table de configuration" ou "overlay de code métier"), cette section (1216 octets) s'est révélée être une **routine générique de copie mémoire** (boucle `lhu`/`sh` puis `lw`/`sw`, avec un compteur de répétition utilisant un registre spécial `sr0`) — une primitive utilitaire, pas un composant du pipeline de déchiffrement lui-même.

## Ce qui reste à faire

- Confirmer bit à bit le fonctionnement du descrambler matériel (nécessiterait de comprendre en détail le contrôleur DMA du SPG293, au-delà des registres déjà identifiés dans [Console](console.md))
- Documenter `.km`/`.jp` (priorité basse)
- Contribuer les échantillons `.drm` Lexibook au projet communautaire SPG2xx-sound-engines
