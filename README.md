# LexiARC
Logiciel de reverse engineering pour les produits de la marque Lexibook.

## Installation
### Rapide
1. Installez le .exe disponible dans les [releases de ce github](https://github.com/maxlware-fr/LexiARC/releases).
2. Aller sur le site internet [lexiarc.maxlware.com/download/latest/lexiarc_file_console.zip](https://lexiarc.maxlware.com/download/latest/lexiarc_file_console.zip) et télécharger le .zip
3. Compiler le .zip dans Carte SD > Compiler une carte SD
4. Créez une émulation
5. Lancer.

### Développeur
1. Téléchargez les gits : [LexiARC](https://github.com/maxlware-fr/LexiARC), [emu293](https://github.com/gatecat/emu293) et mtools.
2. Téléchargez les fichiers de la console sur [lexiarc.maxlware.com/download/latest/lexiarc_file_console.zip](https://lexiarc.maxlware.com/download/latest/lexiarc_file_console.zip).
3. Téléchargez [MSYS2 MINGW64](https://www.msys2.org/).
4. Installez les dépendances
5. Build emu293 avec "make"
6. Ensuite faite la commande : *./emu293.exe chemin/vers/Lead.sys chemin/vers/sd_card.img*
7. Compiler le .zip dans Carte SD > Compiler une carte SD
8. Créez une émulation
9. Lancer.

## License
Le git est sous license Apache. Les dépendances ont leurs propre license, allez dans les README.md de celle-ci.

## Conformité et sécurité
**AUCUN** fichier de la console n'a été modifié et ne sera pas modifié. Dans l'UE, l'émulation est autorisé. Aucun jeu n'est copié. Des ROMs de l'utilisateur peuvent être mise mais je décline TOUTES responsabilités en cas de non respect du copyright.
