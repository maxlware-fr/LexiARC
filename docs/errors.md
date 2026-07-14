# Errors — Erreurs connues

## Compilation d'emu293 (MSYS2)

### `error: target not found: mingw-w64-x86_64-wxWidgets`
Le paquet a été renommé/scindé dans les dépôts MSYS2. Utilisez :
```bash
pacman -S mingw-w64-x86_64-wxwidgets3.2-msw git make
```

### `Operation too slow` / téléchargement `pacman` qui échoue
Miroir MSYS2 surchargé, pas une vraie erreur de dépendances. Relancez la même commande (le cache garde ce qui a déjà réussi), au besoin après :
```bash
pacman -Syy
```

### `static_assert(sizeof(off_t) == 8)` dans `stor/sdcard.cpp`
`off_t` est en 32 bits par défaut sous MinGW-w64. Ajoutez `-D_FILE_OFFSET_BITS=64` aux flags de compilation (patch du `Makefile`) :
```bash
sed -i 's/-std=c++11/-std=c++11 -D_FILE_OFFSET_BITS=64/' Makefile
```

### `cannot find -lv4l2` / `cannot find -lv4lconvert`
Ces libs Video4Linux sont **Linux uniquement** (support webcam). Sous Windows, retirez-les de la ligne de link :
```bash
sed -i 's/ -lv4l2 -lv4lconvert//' Makefile
```

### `undefined reference to WinMain` (après link réussi des `.o`)
**Cause réelle** : SDL2 redéfinit `main` en `SDL_main` via une macro (`#define main SDL_main` dans `SDL2/SDL.h`) et attend que `SDL2main` fournisse le vrai point d'entrée Windows. Il ne faut **pas** essayer de forcer un sous-système console/`-mconsole`/`-Wl,--subsystem` — ça ne résout pas la vraie cause. Le correctif est d'ajouter `-lmingw32 -lSDL2main` **avant** `-lSDL2` dans la ligne de link :
```bash
sed -i 's/-lSDL2 -lz/-lmingw32 -lSDL2main -lSDL2 -lz/' Makefile
```

## Lancement d'emu293

### `Failed to open SD image file ...` avec un chemin qui contient des caractères bizarres (`├ët├®` au lieu de `Été`)
Bug d'encodage Windows/MSYS2 : un chemin accentué passé en UTF-8 est mal interprété en codepage ANSI par le CRT Windows lors de l'appel `fopen()`. **Solution** : utilisez un chemin sans accents ni espaces pour `Lead.sys`, l'image SD, et l'ensemble du dossier du projet si vous passez par LexiARC (qui pointe vers ces mêmes fichiers).

### `failed to open audio device: WASAPI can't initialize audio client`
Pilote audio par défaut du système dans un état incompatible. Forcez un autre pilote SDL2 :
```bash
SDL_AUDIODRIVER=directsound ./emu293.exe ...
```
ou, si `directsound` échoue aussi :
```bash
SDL_AUDIODRIVER=winmm ./emu293.exe ...
```
Pour rendre le choix permanent :
```bash
echo 'export SDL_AUDIODRIVER=directsound' >> ~/.bashrc
```

### `terminate called without an active exception` juste après un message d'erreur
Symptôme générique d'un `exit(1)` appelé après un échec d'initialisation (SD, ELF, audio...) pendant qu'un thread SDL est encore actif. Regardez toujours le message **juste avant** cette ligne — c'est lui qui indique la vraie cause (voir entrées ci-dessus).

## `mtools` (mdir/mcopy/mformat)

### `Drive 'C:' not supported` / `Cannot initialize 'A:'`
Oubli du flag `-i` avant le chemin de l'image :
```bash
./mdir.exe -i "chemin/vers/image.img" ::/
```

### Un jeu/dossier n'apparaît pas dans le menu de la console après reconstruction d'une image SD
Vérifiez si votre script de génération d'image a bien préservé les **espaces** dans les noms de fichiers/dossiers (ex. `Game Player`, `9 Ball`). Un remplacement de caractères "non sûrs" qui exclurait l'espace produira des noms du type `Game_u0020Player`, introuvables par le firmware. Voir [Software](software.md).

## Émulation en cours d'exécution

### Animations saccadées

Ne pas activer `SDL_RENDERER_PRESENTVSYNC` sur le renderer SDL sans restructuration préalable : dans l'architecture actuelle d'emu293, `PPUTick()`/`PPUFlip()` s'exécutent sur le **même thread** que l'interpréteur CPU et l'audio (voir [Emulate](emulate.md)). Activer le vsync, ou ajouter un `SDL_Delay` de limitation de fréquence dans cette même boucle, bloque **tout** le système émulé (audio y compris) pendant l'attente — testé, et confirmé comme régression : le patch a dû être annulé.

### Son totalement absent

Investigation en cours. Pistes déjà écartées ou confirmées :
- Le pilote audio SDL (WASAPI/directsound/winmm) n'est **pas** la cause si le silence persiste avec tous les pilotes testés.
- Le mixage (`spu_mix_channels`) fonctionne correctement sur le papier et dépend des registres `spu_regs[]`.
- Certains jeux activent bien le canal PCM logiciel (`softch_en = 1` observé par intermittence), donc l'absence de son n'est pas systématiquement due à un canal jamais activé.
- Reste à confirmer si `spu_softch_compctrl` (diviseur de fréquence du canal PCM) est réellement configuré par le jeu à un moment donné, ou reste à 0 en permanence (ce qui empêcherait toute avance réelle du pointeur de lecture PCM). Un diagnostic ciblé (impression périodique de `base`/`ptr`/échantillons lus) est en cours d'exploitation — voir les issues du dépôt pour la suite.
