# Comment Model

Fine-tuning LoRA de **Qwen2.5-1.5B-Instruct** sur les paires post → commentaire de `../hn-comments-dataset/`, puis serveur local qui propose des commentaires à l'extension `../linkedin-like-helper/`.

Tout tourne en local, gratuitement, sur une RTX 4060 Laptop (8 Go de VRAM).

## Installation

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/Scripts/python.exe torch --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv/Scripts/python.exe transformers peft accelerate fastapi uvicorn pytest
```

Au premier lancement, le modèle de base (environ 3 Go) est téléchargé dans `~/.cache/huggingface`.

## Entraînement

```bash
.venv/Scripts/python train.py --max-train 10000 --batch 4 --grad-accum 4   # ~1 h sur RTX 4060 Laptop
```

- **Données** (`data.py`) : on garde les commentaires de 40 à 600 caractères, sans citations (`>`), sans listes de liens et sans `[flagged]`/`[dead]`. Les posts sont tronqués à 1 500 caractères.
- **Format** : un message système, qui demande un commentaire court et concret de style LinkedIn dans la langue du post, puis le post, puis le commentaire. La perte n'est calculée que sur le commentaire (le prompt est masqué à `-100`). Le modèle apprend aussi à s'arrêter, grâce au jeton `<|im_end|>` ajouté en fin de commentaire.
- **LoRA** : `r=16`, `alpha=32`, sur toutes les couches linéaires, soit 18,5 M de paramètres entraînables (1,2 % du modèle). On utilise bf16 et le gradient checkpointing.
- **VRAM** : avec la perte standard de transformers, les logits sont calculés sur les 151 000 mots du vocabulaire pour **chaque** jeton, prompt compris, et convertis en fp32. Avec un batch de 4, la mémoire dépassait les 8 Go : débordement dans la RAM partagée (0,43 exemple/s), puis OOM. `CompletionOnlyTrainer` n'applique `lm_head` qu'aux positions du commentaire. Résultat : un pic de **4,0 Go** à batch 4, environ 3 exemples/s, et une évaluation 10× plus rapide. Monter au-delà de batch 4 n'accélère plus rien, car le GPU est alors limité par le calcul.
- **Reprise** : `--resume` repart du dernier checkpoint de `--out`.

L'adaptateur est enregistré dans `adapters/qwen-hn-lora/` (ignoré par git).

## Serveur de suggestions

```bash
.venv/Scripts/python server.py                  # modèle fine-tuné
.venv/Scripts/python server.py --adapter none   # modèle de base, pour comparer
```

- Il écoute sur `127.0.0.1:8008` uniquement, donc il n'est pas accessible depuis le réseau.
- `POST /suggest` reçoit `{"post": "...", "n": 3, "temperature": 0.8}` et renvoie `{"suggestions": [...], "ms": 1234}`.
- `GET /health` indique si le modèle est chargé et quel adaptateur est utilisé.
- L'adaptateur LoRA est fusionné dans le modèle au chargement, donc il ne ralentit pas la génération.

## Résultats

Run du 18/10/2026 : 10 000 paires, 1 epoch (625 étapes de 16 exemples), environ 55 min de calcul sur la RTX 4060 Laptop, pic mémoire de 4,24 Go, adaptateur de 71 Mo.

| Étape | 0 | 156 | 312 | 468 | 625 |
|---|---|---|---|---|---|
| `eval_loss` (200 posts de validation) | 3,29 | 3,083 | 3,070 | 3,063 | **3,058** |

La perte baisse surtout au début, puis se stabilise. C'est attendu : le modèle apprend vite le *style* des commentaires, mais leur *contenu* reste difficile à prédire.

Exemples côte à côte dans [`samples.md`](samples.md) (`python compare.py`) :

- **Ce que le fine-tuning apporte** : les commentaires ressemblent à ceux d'un humain. Le modèle donne un avis tranché ou une expérience, au lieu des « Great achievement! Can you elaborate…? » génériques du modèle de base.
- **Ce qu'il dégrade** :
  - Il **invente des expériences personnelles** (« I did an internship at Databricks »), qui seraient publiées sous ton nom.
  - Il reprend le ton parfois **cynique ou hors sujet** de Hacker News.
  - Il répond **en anglais à un post en français**, alors que le modèle de base répond correctement en français.
- **Conclusion** : utilise-le comme source d'idées à **réécrire**, jamais tel quel. Pour aller plus loin, il faudrait filtrer les commentaires négatifs ou à la première personne dans `data.py`, ajouter des paires en français et dans le ton LinkedIn (par exemple celles collectées par l'extension), et comparer avec `--adapter none`.

## Limites

- Les données viennent de Hacker News. Le modèle écrit donc surtout en **anglais**, avec un ton tech assez direct. Le message système demande de répondre dans la langue du post, mais pour des posts en français, le modèle de base répond souvent mieux.
- Les suggestions doivent toujours être relues avant publication. L'extension ne publie jamais rien toute seule.
