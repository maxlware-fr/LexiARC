# LexiARC Wiki

Bienvenue sur le wiki de **LexiARC**, logiciel de reverse engineering et d'émulation pour les consoles Lexibook basées sur le SoC Sunplus **SPG293** (cœur **S+core7**), à commencer par la **JG7420AV**.

## Pages disponibles

| Page | Contenu |
|---|---|
| [Getting Started](getting-started.md) | Installation rapide et développeur, premier lancement |
| [Console](console.md) | Architecture matérielle : CPU, SoC, toolchain d'origine |
| [Software](software.md) | Formats de fichiers de la console, pipeline de chargement des jeux |
| [Emulate](emulate.md) | Fonctionnement de l'émulateur (emu293), configuration, limites connues |
| [Compilate](compliate.md) | État de la compilation de jeux maison (`.elf`/`.wxn`) |
| [Errors](errors.md) | Erreurs connues et leurs correctifs |

## Résumé du projet

LexiARC ne modifie jamais les fichiers d'origine de la console. Il travaille sur des copies (images `.img`) fournies par l'utilisateur pour permettre l'analyse et l'émulation d'un contenu que celui-ci possède déjà légitimement. Voir la section Conformité et sécurité du `README.md` du dépôt pour le détail.

## État du projet (résumé rapide)

- ✅ Architecture CPU/SoC identifiée et documentée (voir [Console](console.md))
- ✅ Formats de fichiers principaux identifiés (voir [Software](software.md))
- ✅ Émulation fonctionnelle via emu293 (menu, chargement de jeux, DMA vidéo)
- 🔶 Audio : partiellement fonctionnel, silence dans certains cas — en cours d'investigation (voir [Errors](errors.md))
- ❌ Compilation de jeux maison (`.elf`/`.wxn`) — non disponible (voir [Compilate](compliate.md))
