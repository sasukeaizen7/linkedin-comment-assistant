"""LoRA fine-tuning of a small instruct model on post -> comment pairs.

    python train.py                      # full run (~25k pairs, 1 epoch)
    python train.py --max-train 200 --max-steps 20 --out adapters/smoke   # smoke test

Only the comment tokens are trained on (the prompt is masked with -100).
"""
import argparse
import random

import torch
import torch.nn.functional as F
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)

from data import load_pairs, messages

BASE = "Qwen/Qwen2.5-1.5B-Instruct"


class CompletionOnlyTrainer(Trainer):
    """Applies lm_head only where there is a label to predict.

    Full-vocabulary logits (151k x every token, upcast to fp32 for the loss) are
    the biggest memory cost on an 8 GB GPU, and the prompt's logits are never
    trained on. Slicing the hidden states first cuts that cost ~3x.
    """

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.pop("labels")
        causal_lm = model.get_base_model()
        hidden = causal_lm.model(input_ids=inputs["input_ids"],
                                 attention_mask=inputs["attention_mask"]).last_hidden_state
        targets = labels[:, 1:]  # position t predicts token t+1
        mask = targets != -100
        logits = causal_lm.lm_head(hidden[:, :-1][mask]).float()
        loss = F.cross_entropy(logits, targets[mask], reduction="sum")
        # During training, num_items_in_batch counts label tokens over all
        # accumulation steps, so the Trainer doesn't divide again.
        loss = loss / (num_items_in_batch if num_items_in_batch is not None else mask.sum())
        return (loss, {"loss": loss}) if return_outputs else loss


def tokenize(tokenizer, row: dict, max_comment_tokens: int) -> dict:
    prompt = tokenizer.apply_chat_template(messages(row["post"]), add_generation_prompt=True, tokenize=False)
    prompt_ids = tokenizer(prompt, add_special_tokens=False).input_ids
    comment_ids = tokenizer(row["comment"], add_special_tokens=False).input_ids[:max_comment_tokens]
    comment_ids.append(tokenizer.convert_tokens_to_ids("<|im_end|>"))  # teach it to stop
    return {
        "input_ids": prompt_ids + comment_ids,
        "attention_mask": [1] * (len(prompt_ids) + len(comment_ids)),
        "labels": [-100] * len(prompt_ids) + comment_ids,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default=BASE)
    p.add_argument("--out", default="adapters/qwen-hn-lora")
    p.add_argument("--max-train", type=int, default=None)
    p.add_argument("--max-val", type=int, default=300)
    p.add_argument("--epochs", type=float, default=1.0)
    p.add_argument("--max-steps", type=int, default=-1)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--batch", type=int, default=4)
    p.add_argument("--grad-accum", type=int, default=4)
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--max-comment-tokens", type=int, default=200)
    p.add_argument("--resume", action="store_true", help="continue from the last checkpoint in --out")
    args = p.parse_args()

    random.seed(0)
    tokenizer = AutoTokenizer.from_pretrained(args.base)
    train_rows = load_pairs("train")
    random.shuffle(train_rows)
    train_rows = train_rows[: args.max_train]
    val_rows = load_pairs("val", limit=args.max_val)
    train_ds = [tokenize(tokenizer, r, args.max_comment_tokens) for r in train_rows]
    val_ds = [tokenize(tokenizer, r, args.max_comment_tokens) for r in val_rows]
    lengths = sorted(len(x["input_ids"]) for x in train_ds)
    print(f"train {len(train_ds)}  val {len(val_ds)}  tokens/example median {lengths[len(lengths) // 2]} max {lengths[-1]}")

    model = AutoModelForCausalLM.from_pretrained(args.base, dtype=torch.bfloat16, attn_implementation="sdpa")
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()  # needed for gradient checkpointing with a frozen base
    model = get_peft_model(model, LoraConfig(
        r=args.lora_r,
        lora_alpha=2 * args.lora_r,
        lora_dropout=0.05,
        target_modules="all-linear",
        task_type="CAUSAL_LM",
    ))
    model.print_trainable_parameters()

    steps_per_epoch = len(train_ds) // (args.batch * args.grad_accum)
    total_steps = args.max_steps if args.max_steps > 0 else int(steps_per_epoch * args.epochs)
    trainer = CompletionOnlyTrainer(
        model=model,
        args=TrainingArguments(
            output_dir=f"{args.out}/checkpoints",
            per_device_train_batch_size=args.batch,
            per_device_eval_batch_size=args.batch,
            gradient_accumulation_steps=args.grad_accum,
            num_train_epochs=args.epochs,
            max_steps=args.max_steps,
            learning_rate=args.lr,
            lr_scheduler_type="cosine",
            warmup_steps=max(1, total_steps // 30),
            bf16=True,
            logging_steps=10,
            eval_strategy="steps",
            eval_steps=max(10, total_steps // 8),
            save_strategy="steps",
            save_steps=max(10, total_steps // 8),
            save_total_limit=2,
            dataloader_num_workers=0,  # Windows: worker processes re-import everything
            label_names=["labels"],  # not inferable through the PEFT wrapper
            prediction_loss_only=True,
            report_to="none",
        ),
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=DataCollatorForSeq2Seq(tokenizer, label_pad_token_id=-100, padding=True),
    )
    trainer.train(resume_from_checkpoint=args.resume or None)
    print(f"peak GPU memory: {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB")
    print("final eval:", trainer.evaluate())
    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)
    print(f"adapter saved to {args.out}")


if __name__ == "__main__":
    main()
