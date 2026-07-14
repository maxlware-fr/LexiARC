# Getting Started

## Prérequis

- Windows (procédure testée sous Windows via MSYS2 ; non testé sur Linux/macOS à ce stade)
- Avoir accès légalement à sa propre console Lexibook et sa carte SD d'origine
- Python 3 (pour les outils d'analyse, chemin développeur uniquement)

## Installation rapide (utilisateur)

1. Téléchargez le `.exe` depuis les [releases GitHub de LexiARC](https://github.com/maxlware-fr/LexiARC/releases) et installez-le.
2. Téléchargez le fichier console depuis [lexiarc.maxlware.com/download/latest/lexiarc_file_console.zip](https://lexiarc.maxlware.com/download/latest/lexiarc_file_console.zip).
3. Dans LexiARC : **Carte SD > Compiler une carte SD**, sélectionnez le `.zip` téléchargé.
4. **File > Émulation > Créer une émulation**, renseignez le nom, le type de CPU (Score7 par défaut), la RAM, et le chemin de l'image SD générée à l'étape 3.
5. Cliquez sur **Lancer l'émulation**.

Si l'émulation ne se lance pas ou se ferme immédiatement, consultez [Errors](errors.md) — la plupart des cas connus (chemins avec accents/espaces, pilote audio) y sont couverts.

## Installation développeur

Cette voie est nécessaire si vous voulez modifier le moteur d'émulation, contribuer au projet, ou compiler vous-même depuis les sources.

### 1. Récupérer les dépôts

```bash
git clone https://github.com/maxlware-fr/LexiARC.git
git clone https://github.com/gatecat/emu293.git
```

`mtools` s'installe via MSYS2 (voir étape 3) plutôt que depuis un dépôt séparé.

### 2. Récupérer les fichiers de la console

Téléchargez et décompressez [lexiarc_file_console.zip](https://lexiarc.maxlware.com/download/latest/lexiarc_file_console.zip) — il contient notamment `Lead.sys` (BIOS), nécessaire au boot de l'émulateur.

### 3. Installer MSYS2 et les dépendances

Installez [MSYS2](https://www.msys2.org/), puis ouvrez un terminal **MSYS2 MINGW64** (pas le terminal MSYS de base) :

```bash
pacman -Syu
pacman -S mingw-w64-x86_64-toolchain mingw-w64-x86_64-SDL2 mingw-w64-x86_64-wxwidgets3.2-msw git make
```

> Si `pacman` échoue sur un miroir lent (`Operation too slow`), relancez simplement la même commande — le cache garde ce qui a déjà réussi. Un `pacman -Syy` avant de réessayer aide aussi à changer de miroir.

### 4. Compiler emu293

```bash
cd emu293/src
make
```

Voir [Errors](errors.md) pour les erreurs de compilation courantes (nom de paquet wxWidgets, `_FILE_OFFSET_BITS`, libs Linux-only, `SDL_main`/`WinMain`).

### 5. Premier test en ligne de commande

```bash
./emu293.exe chemin/vers/Lead.sys chemin/vers/sd_card.img
```

> **Important** : utilisez des chemins **sans accents ni espaces**. Un chemin accentué provoque un échec d'ouverture de fichier silencieux côté Windows (voir [Errors](errors.md)).

Si le son ne fonctionne pas ou que le programme plante à l'ouverture du périphérique audio :
```bash
SDL_AUDIODRIVER=directsound ./emu293.exe chemin/vers/Lead.sys chemin/vers/sd_card.img
```

### 6. Intégrer à LexiARC

Placez dans le dossier `bin/` du projet LexiARC :
```
bin/
  emu293.exe + toutes ses DLL (utilisez `ldd emu293.exe` pour les identifier)
  mtools/
    mcopy.exe, mdir.exe, mformat.exe, mmd.exe
```
Et `Lead.sys` dans `core/windows/Lead.sys` à la racine du projet.

### 7. Lancer via l'interface

Suivez ensuite les étapes 3 à 5 de l'installation rapide ci-dessus, mais via votre build local.

## Prochaines lectures

- [Console](console.md) pour comprendre l'architecture matérielle émulée
- [Software](software.md) pour comprendre les formats de fichiers manipulés
- [Emulate](emulate.md) pour les options avancées de l'émulateur
