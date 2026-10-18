"""Side-by-side comments from the base model and the fine-tuned adapter.

    python compare.py --n-posts 6 --out samples.md

Uses validation posts (never seen in training) plus a few hand-written
LinkedIn-style posts, including one in French.
"""
import argparse
import gc
import random

import torch

import generate
from data import load_pairs

EXTRA_POSTS = [
    "After 6 months of self-study I just passed the Databricks Data Engineer Associate exam! "
    "Biggest lesson: build real pipelines, don't just watch videos.",
    "We moved our nightly batch jobs from Airflow to event-driven pipelines with Kafka. "
    "Latency went from 24h to 5 minutes, but debugging got much harder.",
    "Je viens de terminer mon premier projet de data engineering : un pipeline qui récupère les "
    "données Vélib' toutes les 5 minutes, les stocke dans Postgres et alimente un dashboard Streamlit.",
]


def run(adapter, posts, seed):
    tokenizer, model = generate.load(adapter=adapter)
    outputs = []
    for post in posts:
        torch.manual_seed(seed)
        outputs.append(generate.suggest(tokenizer, model, post, n=1, temperature=0.7)[0])
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return outputs


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--adapter", default="adapters/qwen-hn-lora")
    p.add_argument("--n-posts", type=int, default=6)
    p.add_argument("--out", default="samples.md")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    random.seed(args.seed)
    val = load_pairs("val")
    picked = random.sample(val, args.n_posts)
    posts = [r["post"] for r in picked] + EXTRA_POSTS
    real = [r["comment"] for r in picked] + [None] * len(EXTRA_POSTS)

    base = run(None, posts, args.seed)
    tuned = run(args.adapter, posts, args.seed)

    lines = ["# Base vs fine-tuned\n"]
    for i, post in enumerate(posts, 1):
        short = post if len(post) < 400 else post[:400] + " …"
        lines += [f"## {i}. Post\n", "> " + short.replace("\n", "\n> ") + "\n",
                  f"**Base Qwen2.5-1.5B** : {base[i - 1]}\n",
                  f"**Fine-tuned (LoRA)** : {tuned[i - 1]}\n"]
        if real[i - 1]:
            lines.append(f"*Vrai commentaire HN* : {real[i - 1]}\n")
    with open(args.out, "w", encoding="utf8") as f:
        f.write("\n".join(lines))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
