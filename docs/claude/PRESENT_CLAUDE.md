# PRESENT_CLAUDE.md — Action en cours (NON terminée)

Ce fichier documente une tâche précise, interrompue faute de tokens, à reprendre
telle quelle dans la prochaine session. Ne pas repartir de zéro : lire ceci d'abord.

## Objectif de la tâche en cours
Construire `sd_card.img` — une image disque brute FAT32 à partir du dossier `core/`
(carte SD dumpée), pour pouvoir tester **emu293** (découverte majeure de cette session,
voir CLAUDE.md § priorités) :
```
./emu293 core/windows/Lead.sys sd_card.img
```

## Contexte matériel/logiciel de l'utilisateur
- Windows, **aucun droit administrateur possible** (ni logiciel, ni terminal admin)
- Dossier de travail : `C:\Users\maxlw\Documents\Le Grand Jeu De L'Été\`
- `core/` présent dedans, taille réelle mesurée : **2.78 Go**
- Outil utilisé : `mtools` (build Windows portable 2019, `foone/mtools_win32`),
  extrait dans `C:\Users\maxlw\Downloads\mtools\` (mformat.exe, mcopy.exe, mmd.exe, etc.)

## Ce qui a déjà été fait (ne pas refaire)
1. ✅ `sd_card.img` créé et formaté FAT32 : 4 Go (8 388 608 secteurs de 512 octets)
   ```
   C:\Users\maxlw\Downloads\mtools\mformat.exe -i sd_card.img -C -T 8388608 ::
   ```
2. ✅ Bug identifié et contourné : l'option `-s` (copie récursive de dossier) de ce
   build mtools échoue systématiquement avec `Permission denied` sur TOUS les dossiers
   testés (`Classroom`, `Fun`, `Sports`, `System`, `windows`) — pas un souci d'attributs
   Windows (`attrib` ne montre rien), pas un souci de caractères spéciaux (échoue même
   sur des dossiers simples). Cause probable : bug du binaire 2019 avec `-s` sur cet OS.
   **Ne plus jamais utiliser `-s` avec ce binaire.**
3. ✅ Copie d'un fichier UNIQUE confirmée fonctionnelle (sans `-s`) :
   ```
   mcopy.exe -i sd_card.img core\windows\Lead.sys ::/
   ```
   → a marché, fichier bien présent (vérifié avec `mdir`), puis supprimé pour repartir propre.
4. ✅ Script de contournement écrit et fourni : **`build_sd_image.ps1`**
   (déjà téléchargé par l'utilisateur, doit être dans le dossier de travail).
   Il recrée l'arborescence dossier par dossier (`mmd`) puis copie CHAQUE fichier
   individuellement (`mcopy`, jamais `-s`) — plus lent mais fiable, contourne le bug ci-dessus.

## Dernière étape en cours au moment de l'interruption
L'utilisateur devait lancer :
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
cd "C:\Users\maxlw\Documents\Le Grand Jeu De L'Été"
.\build_sd_image.ps1
```
**On ne sait pas encore si ce script a été exécuté, ni s'il a réussi.**

## Prochaine étape immédiate (reprise de session)
1. Demander à l'utilisateur s'il a lancé `build_sd_image.ps1`, et s'il a le résumé final
   affiché (nombre de fichiers copiés / erreurs listées).
2. Si pas encore lancé : le relancer avec les commandes ci-dessus.
3. Si lancé avec succès (0 erreur) : passer à l'étape suivante — compiler/récupérer
   `emu293` (https://github.com/gatecat/emu293) et tester
   `emu293 core/windows/Lead.sys sd_card.img`.
4. Si erreurs listées par le script : les examiner une par une (souvent noms de fichiers
   non-ASCII probables, cf `Classroom\Music\...\简谱表` mentionné dans CLAUDE.md, ou
   chemins trop longs — limite Windows 260 caractères) et adapter au cas par cas.

## Rappel budget tokens
Cette tâche (créer une image disque) est mécanique et ne nécessite normalement PAS
d'analyse ELF/reverse engineering — éviter de ré-ouvrir Lead.sys ou de relancer des
analyses déjà faites (voir CLAUDE.md § 2) pendant qu'on finit cette étape.
