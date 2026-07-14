# Emulate — Le moteur d'émulation

LexiARC s'appuie sur [emu293](https://github.com/gatecat/emu293) (licence propre au dépôt, à vérifier avant toute redistribution), un émulateur pour consoles basées sur le SoC Sunplus **SPG293**. Son cœur CPU Score7 est initialement issu du projet [hyperscan-emulator](https://github.com/LiraNuna/hyperscan-emulator).

## Lancement en ligne de commande

```bash
./emu293.exe [-cam /dev/videoN] [-scale {1,2,3,4}] [-zone3d] [-nor] [-spudebug] chemin/vers/Lead.sys chemin/vers/sd_card.img
```

- `-scale N` : facteur d'agrandissement de la fenêtre (1 à 4)
- `-spudebug` : active un enregistrement de debug audio (fonctionnel sous Linux uniquement dans le code actuel, voir [Errors](errors.md))
- `-nor` : démarre depuis une image NOR flash plutôt qu'un ELF

Via LexiARC, ces options sont gérées par l'interface (Créer une émulation / Importer une émulation) plutôt qu'en ligne de commande directe.

## Architecture interne (ce qu'il faut savoir avant de patcher)

**Tout tourne sur un seul et même thread** : `scoreCPU.step()` (interpréteur CPU), `SPUUpdate()` (audio), `PPUTick()` (vidéo) et `TimerTick()` sont enchaînés dans la boucle principale (`emu293.cpp`) via un simple compteur d'instructions (`icount % N`). Il n'y a **pas** de séparation CPU/audio/vidéo sur des threads indépendants pour la logique de timing — un seul thread de rendu séparé existe pour la préparation du framebuffer, mais le `SDL_RenderPresent` final reste appelé depuis ce même thread principal.

**Conséquence pratique** : tout blocage ajouté n'importe où dans cette boucle (ex. un `SDL_Delay` pour lisser l'affichage) ralentit **également** l'audio et l'avancement du CPU émulé, pas seulement le rendu. C'est une régression qu'on a rencontrée concrètement en essayant d'ajouter un limiteur de fréquence dans `PPUTick()` — le patch a été annulé pour cette raison (voir [Errors](errors.md)).

**Vitesse non limitée par design** : toutes les lignes `SDL_Delay` du code source sont commentées (`// SDL_Delay(1);`), y compris dans la boucle principale — c'est un choix des auteurs d'emu293, pas un oubli. L'émulateur tourne aussi vite que la machine hôte le permet, sans se caler sur un vrai rythme d'horloge de la console physique.

## Manette IR virtuelle

La console utilise une manette **infrarouge** à boutons discrets (pas d'analogique). emu293 la simule via `io/ir_gamepad.cpp`, avec :
- Mapping clavier par défaut (flèches, Z/X/C, etc. — voir le code pour le détail complet par joueur)
- Mapping souris ajouté dans le cadre de ce projet : clic gauche = Sélectionner (A), clic droit = Annuler/retour (B), molette haut/bas = navigation D-pad (impulsion haut/bas)

## Audio (SPU)

Le SPU émulé combine deux chemins :
- 24 canaux "synthé" classiques (volume, pan, échantillon courant par canal)
- Un canal **PCM logiciel** (`softch`), piloté par un pointeur de lecture avancé à un rythme dérivé du registre `spu_softch_compctrl`

**Statut connu** : certains jeux activent le canal `softch` (`softch_en = 1`) sans qu'un son audible n'en résulte de façon fiable. Investigation en cours — voir [Errors](errors.md) pour l'état d'avancement et les hypothèses explorées (registre de fréquence jamais configuré, boucle d'attente d'interruption ne se débloquant pas, etc.).

## Limites connues

- Pas de limitation de vitesse fiable sans risquer de casser l'audio (voir architecture ci-dessus)
- Certains registres MMIO ne sont pas encore modélisés (`BUFCTL` notamment, voir logs `write error: address ... out of range`) — sans conséquence bloquante observée à ce jour, mais signale une couverture matérielle incomplète
- Le debug audio (`-spudebug`) n'écrit son fichier `.wav` que sous Linux dans le code actuel
