# LinkedIn Like Helper

Extension Chrome qui repère, dans ton fil LinkedIn, les posts de tes **relations de 1er niveau** que tu n'as pas encore likés.

- Chaque post concerné est entouré en bleu, avec un badge **👍 Liker / Ignorer**.
- Un panneau en bas à gauche affiche le nombre de posts à liker et propose deux boutons :
  - **Suivant ↓** fait défiler jusqu'au prochain post à liker. S'il n'y en a plus à l'écran, il descend pour charger la suite du fil.
  - **Liker les visibles** like les posts surlignés actuellement à l'écran, avec 0,8 s entre chaque.
- Les posts sponsorisés, ceux des 2e/3e niveaux et ceux que tu as déjà likés sont ignorés.
- Chaque post d'une relation a aussi un bouton **💬 Suggérer**. Il envoie le texte du post à ton **modèle local** (`../comment-model/`, serveur sur `127.0.0.1:8008`) et affiche 3 commentaires proposés, que tu peux modifier. **Insérer** ouvre le champ de commentaire du post et y écrit le texte. Tu relis, puis tu cliques toi-même sur Publier. Si le champ est introuvable, le texte est copié dans le presse-papiers.
- L'extension ne like **jamais toute seule**. Chaque like part d'un clic de ta part, ce qui limite le risque vis-à-vis des règles de LinkedIn sur l'automatisation.

## Installation

1. Ouvre `chrome://extensions`.
2. Active le **Mode développeur** (en haut à droite).
3. Clique sur **Charger l'extension non empaquetée** et choisis le dossier `linkedin-like-helper/`.
4. Va sur https://www.linkedin.com/feed/ (ou recharge la page si elle était déjà ouverte).

## Suggestions de commentaires

Démarre le serveur avant d'ouvrir LinkedIn :

```bash
cd ../comment-model
.venv/Scripts/python server.py
```

Les requêtes passent par le service worker (`background.js`), parce que la page LinkedIn n'a pas le droit d'appeler `localhost` directement. Si le serveur n'est pas lancé, le panneau de suggestions affiche « Serveur local injoignable ».

## Si rien n'est détecté

LinkedIn change souvent son HTML. Les sélecteurs sont regroupés en haut de `content.js` :

| Constante | Ce qu'elle cible |
|---|---|
| `POST_SEL` | le conteneur d'un post du fil |
| `ACTOR_SEL` | le bloc auteur (nom, « • 1er », titre) |
| `LIKE_SEL` / `LIKE_FALLBACK_SEL` | le bouton J'aime du post (avec `aria-pressed`) |
| `FIRST_DEGREE` | le texte du niveau de relation (`1st`, `1er`, `1re`) |
| `TEXT_SEL` | le bloc de texte du post (envoyé au modèle) |
| `EDITOR_SEL` | le champ de commentaire (où « Insérer » écrit) |

Pour les ajuster : clic droit sur un post → **Inspecter**, repère les nouvelles classes, mets les constantes à jour, puis clique sur ↻ dans `chrome://extensions`.
