# Politique de sécurité

## Versions supportées

LexiARC est en phase bêta active. Seule la dernière version publiée (dernière release GitHub) reçoit des correctifs de sécurité.

| Version | Supportée |
|---|---|
| Dernière release | ✅ |
| Versions antérieures | ❌ |
| Branche `main` (développement) | ⚠️ Meilleur effort, pas de garantie |

## Signaler une vulnérabilité

Si vous découvrez une faille de sécurité dans LexiARC (pas dans emu293 ou mtools eux-mêmes, voir [Périmètre](#périmètre) ci-dessous) :

1. **N'ouvrez pas d'issue publique.** Utilisez l'onglet **Security > Report a vulnerability** du dépôt GitHub, ou contactez directement le mainteneur via les moyens indiqués sur [maxlware.com](https://maxlware.com).
2. Décrivez la faille avec autant de détail que possible : version concernée, étapes de reproduction, impact estimé.
3. Vous recevrez un accusé de réception sous quelques jours. Le délai de correction dépend de la gravité — les failles critiques (exécution de code arbitraire, écriture de fichier hors périmètre prévu) sont traitées en priorité.
4. Merci de nous laisser un délai raisonnable pour publier un correctif avant toute divulgation publique.

## Périmètre

**Couvert par cette politique** :
- Le code de LexiARC lui-même (interface, scripts d'appel à `mtools`/`emu293`, `lexianalyzer.py`, `score_disasm.py`)
- La façon dont LexiARC construit ses appels en sous-processus et manipule les chemins fournis par l'utilisateur

**Non couvert ici** (à signaler directement aux projets concernés) :
- [emu293](https://github.com/gatecat/emu293) — bugs de l'émulateur lui-même (corruption mémoire dans l'émulation CPU/DMA, etc.)
- [mtools](https://www.gnu.org/software/mtools/) (GNU) — bugs des utilitaires FAT32 tiers utilisés par LexiARC
- SDL2, wxWidgets et autres dépendances tierces

## Points d'attention spécifiques à ce projet

LexiARC manipule des données potentiellement non fiables et invoque des exécutables externes ; quelques points à garder en tête si vous l'auditez ou y contribuez :

- **Fichiers analysés** : les images de carte SD, fichiers `.wxn`/`.elf`/`.drm` traités par `lexianalyzer.py` peuvent être malformés (accidentellement ou volontairement). Le parsing doit rester défensif — un fichier corrompu ne doit produire qu'une erreur propre, jamais un comportement inattendu côté outil d'analyse.
- **Émulation de contenu non fiable** : `emu293` interprète du code machine Score7 arbitraire. Un fichier de jeu conçu de façon malveillante pourrait en théorie exploiter un bug de l'émulateur CPU. LexiARC ne fait aucune vérification de sécurité supplémentaire sur le contenu émulé au-delà de ce qu'emu293 fait lui-même — traitez tout fichier de jeu comme vous traiteriez n'importe quel exécutable non fiable.
- **Appels en sous-processus** : LexiARC invoque `mcopy`/`mdir`/`mformat`/`emu293.exe` via `subprocess`, avec des chemins fournis par l'utilisateur (sélecteur de fichier, ou saisie libre pour le chemin de destination sur l'image SD). Ces appels utilisent des listes d'arguments (pas de concaténation en chaîne shell), ce qui évite l'injection de commande classique — mais un chemin de destination saisi librement par l'utilisateur n'est pas validé au-delà de ça. Ne saisissez pas de chemin provenant d'une source non fiable dans ce champ.
- **Aucune télémétrie** : LexiARC ne fait aucun appel réseau à l'insu de l'utilisateur. Les seules ressources distantes référencées sont les liens de téléchargement explicites (releases GitHub, fichier console sur `lexiarc.maxlware.com`) et la documentation. Le code est ouvert : n'hésitez pas à vérifier vous-même l'absence d'appel réseau caché.
- **Fichiers de la console** : LexiARC ne modifie jamais les fichiers d'origine de la console (voir `README.md`, section Conformité et sécurité). Toutes les opérations d'écriture (formatage, copie de jeu) s'effectuent sur des copies (images `.img`) explicitement désignées par l'utilisateur, jamais sur un périphérique physique en accès direct.

## Bonnes pratiques recommandées aux utilisateurs

- Ne lancez pas LexiARC avec des privilèges administrateur/élevés sans raison particulière.
- Gardez `emu293.exe` et `mtools` à jour depuis leurs sources officielles respectives.
- Si vous testez des fichiers `.wxn`/`.elf` obtenus d'une source autre que votre propre carte SD, gardez en tête les points ci-dessus sur l'émulation de contenu non fiable.
