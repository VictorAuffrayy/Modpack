# Modpack Companion

Outils interactifs, en anglais et en français, pour les gros modpacks Minecraft (ATM10, puis ATM11…).
Le principe : **toutes les données sont extraites des fichiers des mods et du modpack, jamais écrites de mémoire**.
Un script relit les fichiers, un autre génère le site. Ajouter un pack ou une mise à jour = relancer les scripts.

## Ce qui est en ligne

| Pack  | Outil                                   | État      |
|-------|-----------------------------------------|-----------|
| ATM10 | 🐝 Planificateur d'abeilles (le Rucher) | ✅ en ligne |
| ATM10 | 📜 Livre de quêtes                      | bientôt   |
| ATM10 | 🧭 Comment obtenir X ?                  | bientôt   |
| ATM11 | (tous)                                  | prévu     |

## Organisation

```
packs/<pack>/pack.json        nom, version Minecraft, sources, outils actifs
packs/atm10/bees.json         abeilles : arbre, méthodes, noms et descriptions EN/FR + leurs clés de langue
packs/atm10/bees_notes.json   les quelques notes écrites à la main (œufs, abeilles coucou…), EN/FR
i18n/en.json, i18n/fr.json    textes de l'interface
templates/                    gabarits HTML ({{clé}} échappée, {{{clé}}} brute)
static/                       CSS, JS, icône
scripts/refresh_bee_text.py   met à jour noms/descriptions depuis les fichiers de langue de Productive Bees
scripts/build_site.py         génère docs/ (aucune dépendance, aucun accès réseau)
docs/                         le site généré, servi par GitHub Pages
```

## Commandes

```bash
python3 scripts/refresh_bee_text.py atm10   # relire les textes officiels du mod (réseau)
python3 scripts/build_site.py               # régénérer docs/
python3 -m http.server 8000 -d docs         # voir le site sur http://localhost:8000
```

## Mise en ligne (GitHub Pages)

Settings → Pages → *Deploy from a branch* → branche `main`, dossier `/docs`.
Le site sera sur `https://victorauffrayy.github.io/Modpack/`. Si tu prends un nom de domaine,
relance le build avec `SITE_URL=https://ton-domaine/ python3 scripts/build_site.py`.

## D'où viennent les données

- **Abeilles ATM10** : `bees.json` vient du Rucher généré par le premier `build.py`
  (recettes de Productive Bees 1.21.1, Productive Metalworks et des scripts KubeJS d'ATM10).
  Les noms et descriptions EN/FR sont relus depuis les fichiers de langue officiels de Productive Bees.
  À faire : remettre l'extracteur (`build.py`) dans `scripts/` pour pouvoir régénérer l'arbre à chaque mise à jour du pack.
- **Quêtes** : `config/ftbquests/quests/` du dépôt [AllTheMods/ATM-10](https://github.com/AllTheMods/ATM-10).
  ⚠️ Les quêtes sont « All Rights Reserved » : demander l'accord de l'équipe ATM avant de les republier.
- **Recettes (« Comment obtenir X »)** : exporter les recettes finales depuis le jeu lancé (KubeJS modifie celles des mods),
  plutôt que de recombiner les fichiers à la main.

## Feuille de route

1. Semaine 1 : Rucher public bilingue → poster sur r/allthemods et le Discord ATM pour mesurer l'intérêt.
2. Semaines 2–3 : extracteur des quêtes ATM10 + livre de quêtes en ligne (après accord de l'équipe ATM).
3. Semaine 4 : proposer les traductions FR/DE des quêtes directement dans le dépôt ATM-10.
4. Semaines 5–6 : publicité + Ko-fi, préparer les pages ATM11.

Site de fan, sans lien avec l'équipe All the Mods, Mojang ou les auteurs des mods.
