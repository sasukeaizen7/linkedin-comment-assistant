# LinkedIn Comment Assistant

Trois projets qui s'enchaînent pour aider à interagir sur LinkedIn sans automatiser son compte : **c'est toujours l'utilisateur qui clique** pour liker ou publier.

```
hn-comments-dataset/  ──paires post → commentaire──▶  comment-model/  ──POST /suggest──▶  linkedin-like-helper/
   (Scrapy, HN API)                                    (LoRA Qwen2.5-1.5B)                 (extension Chrome)
```

| Projet | Rôle | Stack |
|---|---|---|
| [`linkedin-like-helper/`](linkedin-like-helper/) | Extension Chrome : surligne les posts des relations de 1er niveau pas encore likés, aide à liker, propose des commentaires générés par le modèle local et les insère dans le champ de commentaire. | Chrome MV3, JavaScript |
| [`hn-comments-dataset/`](hn-comments-dataset/) | Construit un dataset post → commentaire depuis Hacker News : API officielle et API Algolia, respect du robots.txt, aucun nom d'utilisateur stocké. Premier crawl : 25 898 paires. | Python, Scrapy |
| [`comment-model/`](comment-model/) | Fine-tuning LoRA de Qwen2.5-1.5B-Instruct sur ces paires (RTX 4060 Laptop, 4,2 Go de VRAM), puis un serveur local de suggestions. | PyTorch, transformers, PEFT, FastAPI |

## Pourquoi Hacker News et pas LinkedIn ?

Aucun dataset public ne contient de commentaires LinkedIn, et le `robots.txt` de LinkedIn interdit tout crawl automatisé (`User-agent: * Disallow: /`). Hacker News propose une API ouverte, et ses discussions tech, data et carrière sont assez proches des sujets LinkedIn. Les limites de ce choix (ton, langue) sont détaillées dans [`comment-model/README.md`](comment-model/README.md).

## Démarrage rapide

```bash
# 1. Dataset
cd hn-comments-dataset
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/scrapy crawl hn_history -a max_stories=3000
.venv/Scripts/python build_pairs.py

# 2. Modèle (installation détaillée dans comment-model/README.md)
cd ../comment-model
.venv/Scripts/python train.py --max-train 10000 --batch 4 --grad-accum 4
.venv/Scripts/python server.py

# 3. Extension : chrome://extensions → Mode développeur → Charger l'extension non empaquetée → linkedin-like-helper/
```

Chaque dossier a son propre README avec les détails et les résultats.
