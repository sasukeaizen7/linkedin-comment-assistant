# HN Comments Dataset

Projet Scrapy qui construit un dataset **post → commentaire** à partir de Hacker News, pour faire le fine-tuning d'un modèle qui propose des commentaires (voir `../linkedin-like-helper/`).

- Les données viennent de l'**API officielle** (`hacker-news.firebaseio.com`). Son `robots.txt` autorise explicitement les fichiers `*.json`, et le spider le respecte (`ROBOTSTXT_OBEY = True`).
- Le crawl est poli : 8 requêtes en parallèle au maximum, un petit délai entre les requêtes, AutoThrottle, et un cache HTTP local pour les relances.
- Aucun nom d'utilisateur n'est stocké : on garde seulement les textes, les ids, les scores et les dates.

## Installation

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

## Utilisation

```bash
# 1. Crawler les stories et leurs commentaires
.venv/Scripts/scrapy crawl hn -a lists=best,ask,show -a limit=500 -a max_comments=10

# 2. Construire les paires d'entraînement
.venv/Scripts/python build_pairs.py --max-per-post 3 --max-chars 600

# Tests
.venv/Scripts/python -m pytest
```

### Options du spider (`-a nom=valeur`)

| Option | Défaut | Rôle |
|---|---|---|
| `lists` | `best,ask,show` | listes HN à parcourir : `top`, `best`, `new`, `ask`, `show` |
| `limit` | `100` | nombre de stories par liste (l'API en renvoie 500 au maximum) |
| `max_comments` | `10` | nombre d'enfants suivis par élément, en commençant par les mieux classés |
| `max_depth` | `1` | 1 = seulement les réponses directes au post ; 2 et plus = les réponses aux commentaires aussi |
| `min_comments` | `3` | ignore les stories qui ont moins de commentaires |

### Spider d'historique : `hn_history`

L'API officielle ne liste que les stories récentes : environ 200 `best`, 160 `show` et 25 `ask`. Pour remonter dans le temps, `hn_history` cherche les stories via l'**API Algolia de HN** (`hn.algolia.com`, gratuite, sans clé). Il les parcourt de la plus récente à la plus ancienne, avec un curseur sur la date. Chaque story coûte 2 requêtes :
1. l'API officielle, qui donne la story et l'ordre de classement des commentaires (`kids`) ;
2. Algolia, qui donne l'arbre complet des commentaires en une seule réponse (triés par id, d'où l'étape 1 pour connaître leur rang).

```bash
.venv/Scripts/scrapy crawl hn_history -a tags=ask_hn,show_hn,story -a max_stories=3000 -a min_comments=20
```

| Option | Défaut | Rôle |
|---|---|---|
| `tags` | `ask_hn,show_hn,story` | types de stories Algolia |
| `max_stories` | `1000` | nombre de stories par tag |
| `min_comments` / `min_points` | `20` / `10` | ignore les stories peu discutées |
| `max_comments` | `10` | nombre de réponses directes gardées par story, les mieux classées d'abord |
| `before` | aucun | timestamp Unix : ne prend que les stories plus anciennes, pour continuer un crawl précédent |

Algolia limite à 10 000 requêtes par heure et par IP. Le spider attend donc 0,45 s entre deux requêtes Algolia, soit environ 8 000 par heure, et il n'utilise pas le cache HTTP (les arbres de commentaires sont volumineux). Avec `max_stories=3000` sur les 3 tags, il faut compter environ 70 minutes de crawl effectif.

Premier crawl complet (18/10/2026) : 17 520 requêtes et 0 erreur (44 nouvelles tentatives réseau). Résultat : 8 824 stories et 82 548 commentaires, soit **25 898 paires** issues de 8 746 posts (24 659 pour l'entraînement, 1 239 pour la validation). Longueur médiane : 257 caractères pour un post, 287 pour un commentaire. Les données pèsent 76 Mo.

Repère : le test (2 listes × 15 stories × 5 commentaires) a fait 159 requêtes en 20 s, soit environ 8 requêtes par seconde. Un crawl complet `best,ask,show` avec `limit=500` et `max_comments=10` fait environ 15 000 requêtes, donc à peu près 30 minutes.

## Fichiers produits (`data/`, ignoré par git)

| Fichier | Contenu |
|---|---|
| `stories.jsonl` | `id, title, text, url, score, num_comments, time, source_list` |
| `comments.jsonl` | `id, story_id, parent_id, depth, rank, text, time` |
| `pairs_train.jsonl` / `pairs_val.jsonl` | `story_id, comment_id, post, comment, rank` |

- Les fichiers bruts sont **complétés** à chaque crawl, et `build_pairs.py` supprime les doublons par id. On peut donc relancer le crawl chaque jour pour accumuler des données. Pour repartir de zéro, supprime `data/`.
- Les paires ne gardent que les commentaires directs au post (`depth = 1`), de 20 à 600 caractères, et les `--max-per-post` mieux classés de chaque post.
- La séparation train/validation se fait **par post**. Tous les commentaires d'un même post sont du même côté, pour que la validation ne contienne pas de posts déjà vus à l'entraînement.

## Structure

```
hnspider/
  spiders/hn.py   spider : listes -> stories -> arbre de commentaires
  spiders/hn_history.py  spider d'historique : recherche Algolia -> stories -> commentaires
  items.py        StoryItem, CommentItem (dataclasses)
  pipelines.py    nettoyage HTML -> texte, rejet des commentaires trop courts
  text.py         html_to_text
  settings.py     politesse, cache, exports JSONL
build_pairs.py    jointure stories + commentaires -> paires train/val
tests/            tests unitaires (nettoyage, paires, split)
```
