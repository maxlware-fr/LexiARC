# Compilate — Compiler son propre jeu

## État actuel : non disponible

LexiARC affiche volontairement un message clair plutôt que de simuler une compilation qui ne produit rien d'utilisable. Il manque deux briques essentielles :

### 1. Un toolchain fonctionnel ciblant `score-elf`

Le CPU Score7 était supporté par GCC + binutils via la cible `score-elf`, mais ce support a été **retiré des versions modernes** (présent entre ~2009 et ~2015 environ). Pour compiler un jeu depuis du code source, il faudrait :
- Reconstruire une toolchain GCC/binutils à partir d'un ancien tag/mirroir qui supporte encore `score-elf`
- Ou écrire un backend LLVM/GCC moderne pour Score7 (chantier conséquent)

Des mirroirs GitHub contenant encore le code source historique de ce support existent (ex. `bminor/binutils-gdb` à un ancien commit, `gnutools/binutils-gdb`) — voir les issues du dépôt pour l'état d'avancement des tentatives de reconstruction.

### 2. L'algorithme de chiffrement `.wxn`

Voir [Software](software.md) pour le détail : le chiffrement des `.wxn` de type "mfc" semble être une fonctionnalité du **contrôleur DMA matériel** de la console plutôt qu'un algorithme logiciel isolé. Sans le reproduire fidèlement (ou sans trouver un moyen de faire signer/chiffrer un fichier par la console elle-même dans un mode de développement), il n'est pas possible de produire un `.wxn` "mfc" valide que la console (ou son émulateur) accepterait de déchiffrer correctement.

## Ce qui est possible aujourd'hui

- Compiler un ELF Score7 **sans** passer par le chiffrement `.wxn`, si vous disposez déjà d'un moyen de compiler pour cette cible par vos propres moyens (toolchain personnel, etc.) — un ELF standard peut être ajouté directement sur l'image SD via **Implémentation > Créer une implémentation** dans LexiARC, dans un sous-dossier de jeu "lourd" au même format que les jeux d'origine.
- Analyser le firmware et les jeux existants avec `lexianalyzer.py` et `score_disasm.py` (fournis avec le dépôt), pour continuer la rétro-ingénierie de l'ISA Score7, du format `.wxn`, ou du hardware DMA.

## Comment contribuer à faire avancer ce chantier

Deux directions concrètes et indépendantes :
1. **Toolchain `score-elf`** : aide bienvenue pour reconstruire/maintenir un binutils/GCC fonctionnel ciblant Score7 (voir issues du dépôt LexiARC).
2. **Descrambling matériel** : aide bienvenue pour cartographier plus précisément le contrôleur DMA du SPG293 (registres, comportement exact du bit de contrôle observé dans `Deciphering_Data_And_DMA`/`BLN_DMA`), idéalement en croisant avec la documentation MAME du SoC si elle existe pour un modèle proche.

Consultez [Console](console.md) et [Software](software.md) pour l'état actuel de la documentation technique avant de vous lancer, afin d'éviter de refaire un travail déjà couvert.
