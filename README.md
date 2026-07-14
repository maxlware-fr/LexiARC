# LexiARC

Logiciel de reverse engineering et d'émulation pour les produits de la marque **Lexibook** (console `JG7420AV` et modèles apparentés basés sur le SoC Sunplus **SPG293** / cœur **S+core7**).

LexiARC fournit une interface graphique pour analyser le contenu d'une carte SD Lexibook d'origine, construire une image émulable, et lancer l'émulation via le moteur [emu293](https://github.com/gatecat/emu293).

---

## Présentation

Ce projet est né d'un travail de rétro-ingénierie sur le firmware `Lead.sys` de la console (architecture Score7, format `.wxn`, pipeline de chargement des jeux) documenté au fil du développement. LexiARC en est l'aboutissement pratique : un outil qui permet à quelqu'un possédant déjà une console Lexibook et sa carte SD d'origine de :

- Importer et inspecter le contenu de sa carte SD
- Construire une image de carte SD compatible
- Lancer une émulation complète via emu293
- Gérer plusieurs configurations d'émulation (profils `.larc`)

**Ce que LexiARC n'est PAS** : un outil de piratage, de distribution de jeux, ou de contournement de protections. Voir la section [Conformité et sécurité](#conformité-et-sécurité) ci-dessous.

**État actuel** : projet bêta. Certaines fonctionnalités (compilation `.elf`/`.wxn` depuis un code source) ne sont pas encore disponibles — voir [FAQ](#faq).

---

## Installation

### Rapide

1. Installez le `.exe` disponible dans les [releases de ce GitHub](https://github.com/maxlware-fr/LexiARC/releases).
2. Allez sur [lexiarc.maxlware.com/download/latest/lexiarc_file_console.zip](https://lexiarc.maxlware.com/download/latest/lexiarc_file_console.zip) et téléchargez le `.zip`.
3. Compilez le `.zip` dans **Carte SD > Compiler une carte SD**.
4. Créez une émulation.
5. Lancez.

### Développeur

1. Téléchargez les dépôts : [LexiARC](https://github.com/maxlware-fr/LexiARC), [emu293](https://github.com/gatecat/emu293) et [mtools](https://www.gnu.org/software/mtools/).
2. Téléchargez les fichiers de la console sur [lexiarc.maxlware.com/download/latest/lexiarc_file_console.zip](https://lexiarc.maxlware.com/download/latest/lexiarc_file_console.zip).
3. Installez [MSYS2](https://www.msys2.org/) (environnement **MINGW64**).
4. Installez les dépendances :
   ```bash
   pacman -S mingw-w64-x86_64-toolchain mingw-w64-x86_64-SDL2 mingw-w64-x86_64-wxwidgets3.2-msw git make
   ```
5. Compilez emu293 :
   ```bash
   cd emu293/src
   make
   ```
6. Testez en ligne de commande :
   ```bash
   ./emu293.exe chemin/vers/Lead.sys chemin/vers/sd_card.img
   ```
   > Utilisez des chemins **sans accents ni espaces** — un chemin accentué provoque un échec d'ouverture de fichier côté Windows.
7. Placez `emu293.exe` (+ ses DLL) et `mtools` dans le dossier `bin/` de LexiARC (voir arborescence attendue dans le dépôt).
8. Compilez le `.zip` de la console dans **Carte SD > Compiler une carte SD**.
9. Créez une émulation.
10. Lancez.

---

## Conformité et sécurité

- **Aucun fichier original de la console n'est modifié, ni ne sera modifié.** LexiARC travaille sur des copies (images `.img`) fournies par l'utilisateur, jamais sur la console physique elle-même.
- **L'émulation est légale dans l'Union européenne**, dès lors qu'elle ne s'accompagne pas de distribution de contenu protégé. LexiARC ne contourne aucune mesure de protection technique dans le but de distribuer des œuvres.
- **Aucun jeu n'est fourni, hébergé ou distribué par ce projet.** L'utilisateur doit posséder légalement sa propre console et sa carte SD d'origine pour en extraire le contenu.
- **Le fichier `Lead.sys` (BIOS/firmware) reste la propriété de Lexibook.** Le lien de téléchargement fourni par le mainteneur du projet est proposé à titre de commodité pour les possesseurs légitimes de la console ; assurez-vous d'être en conformité avec le droit applicable dans votre juridiction avant de l'utiliser.
- Si vous ajoutez vos propres ROMs/fichiers sur une image de carte SD via LexiARC, **vous êtes seul responsable** du respect du copyright sur ce contenu. Le mainteneur du projet décline toute responsabilité en cas de non-respect de ces droits par un utilisateur.
- Le code source est ouvert et auditable — n'hésitez pas à vérifier vous-même qu'aucune donnée n'est envoyée à un serveur tiers à l'insu de l'utilisateur.

---

## FAQ

**LexiARC va-t-il abîmer ma console ou ma carte SD d'origine ?**
Non. LexiARC ne communique jamais avec la console physique ; il travaille uniquement sur une image `.img` que vous créez vous-même à partir du contenu de votre carte SD.

**Est-ce que je peux jouer à des jeux que je n'ai pas ?**
Non. LexiARC n'héberge, ne distribue et ne fournit aucun jeu. Il émule uniquement le contenu que vous possédez déjà et importez vous-même.

**Pourquoi la compilation `.elf`/`.wxn` ne fonctionne pas ?**
Cette fonctionnalité nécessite un toolchain GCC ciblant `score-elf` (support retiré des binutils/GCC modernes depuis environ 2015) ainsi que l'algorithme de chiffrement `.wxn`, qui semble géré par le contrôleur DMA matériel de la console plutôt que par un algorithme logiciel simple. Ni l'un ni l'autre n'ont encore été reconstruits. C'est un chantier en cours.

**J'ai un problème de son (silence, ou son qui saute) dans l'émulation.**
Connu et en cours d'investigation — le sous-système audio logiciel (`softch`) de emu293 ne semble pas toujours correctement alimenté selon les jeux. Consultez les [issues GitHub](https://github.com/maxlware-fr/LexiARC/issues) pour l'état d'avancement.

**Est-ce que ça marche avec d'autres consoles Lexibook que la JG7420AV ?**
Potentiellement, pour les modèles basés sur le même SoC SPG293/cœur Score7 (par exemple la famille JG7425 déjà documentée par la communauté MAME/emu293). Non testé/garanti pour les autres familles de consoles Lexibook (ex. celles basées sur Sunplus unSP).

**Puis-je contribuer ?**
Oui — voir les issues et pull requests sur le dépôt GitHub. Les contributions sur le désassembleur Score7, la reconstruction de l'algorithme `.wxn`, et les correctifs emu293 sont particulièrement bienvenues.

---

## Licence

Ce dépôt (LexiARC) est distribué sous licence **Apache 2.0**.

Les dépendances utilisées (emu293, mtools, SDL2, wxWidgets, etc.) ont chacune leur propre licence — reportez-vous au `README.md` / fichier `LICENSE` de chaque dépendance respective avant toute redistribution.

---

## Remerciements

- [gatecat/emu293](https://github.com/gatecat/emu293) — moteur d'émulation SPG293, avec le cœur CPU Score7 initialement issu du projet [hyperscan-emulator](https://github.com/LiraNuna/hyperscan-emulator) de LiraNuna.
- Communauté [MAME](https://www.mamedev.org/) pour la documentation du pilote `spg29x_lexibook_jg7425.cpp`.
- Projet communautaire [SPG2xx-sound-engines](https://github.com/BLiNXthetimesweeperGOD/SPG2xx-sound-engines) pour la documentation du format audio `SP_ToneMaker` (`.drm`).
- `mtools` (GNU) pour la manipulation des images FAT32.
