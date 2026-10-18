"""Local comment-suggestion API for the LinkedIn Like Helper extension.

    python server.py                                  # fine-tuned adapter
    python server.py --adapter none                   # base model, for comparison

Listens on 127.0.0.1 only: nothing is reachable from the network.
"""
import argparse
import threading
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

import generate

state: dict = {}
lock = threading.Lock()  # one generation at a time on the GPU


class SuggestRequest(BaseModel):
    post: str = Field(min_length=1, max_length=10_000)
    n: int = Field(default=3, ge=1, le=5)
    temperature: float = Field(default=0.8, ge=0.1, le=1.5)


class SuggestResponse(BaseModel):
    suggestions: list[str]
    ms: int


def create_app(base: str, adapter: str | None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app):
        state["tokenizer"], state["model"] = generate.load(base, adapter)
        state["adapter"] = adapter
        yield
        state.clear()

    app = FastAPI(title="Comment suggestions", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"ok": "model" in state, "adapter": state.get("adapter")}

    @app.post("/suggest", response_model=SuggestResponse)
    def suggest(req: SuggestRequest):  # sync: FastAPI runs it in a worker thread
        start = time.perf_counter()
        with lock:
            texts = generate.suggest(state["tokenizer"], state["model"], req.post, n=req.n,
                                     temperature=req.temperature)
        return SuggestResponse(suggestions=texts, ms=int((time.perf_counter() - start) * 1000))

    return app


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default=generate.BASE)
    p.add_argument("--adapter", default="adapters/qwen-hn-lora", help='"none" for the base model')
    p.add_argument("--port", type=int, default=8008)
    args = p.parse_args()
    adapter = None if args.adapter == "none" else args.adapter
    uvicorn.run(create_app(args.base, adapter), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
