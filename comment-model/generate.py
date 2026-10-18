"""Load the base model (+ optional LoRA adapter) and generate comments."""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from data import messages

BASE = "Qwen/Qwen2.5-1.5B-Instruct"


def load(base: str = BASE, adapter: str | None = None):
    tokenizer = AutoTokenizer.from_pretrained(base)
    tokenizer.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(base, dtype=torch.bfloat16, device_map="cuda")
    if adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter).merge_and_unload()  # merged = no LoRA overhead
    model.eval()
    return tokenizer, model


@torch.inference_mode()
def suggest(tokenizer, model, post: str, n: int = 3, temperature: float = 0.8,
            max_new_tokens: int = 120) -> list[str]:
    prompt = tokenizer.apply_chat_template(messages(post), add_generation_prompt=True, tokenize=False)
    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(model.device)
    out = model.generate(
        **inputs,
        do_sample=True,
        temperature=temperature,
        top_p=0.9,
        repetition_penalty=1.1,
        max_new_tokens=max_new_tokens,
        num_return_sequences=n,
        pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
    )
    texts = tokenizer.batch_decode(out[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)
    seen, unique = set(), []
    for t in (t.strip() for t in texts):
        if t and t not in seen:
            seen.add(t)
            unique.append(t)
    return unique
