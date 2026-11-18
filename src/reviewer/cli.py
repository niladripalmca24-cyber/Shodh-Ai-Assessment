from __future__ import annotations
import argparse
import json
import sys
from typing import Optional
from fastapi import FastAPI, HTTPException
import uvicorn

from reviewer.engine import ReviewEngine
from reviewer.model_client import FakeModelClient
from reviewer.schemas import ReviewBundle, ReviewResult

app = FastAPI(
    title="Shodh AI - Workflow Reviewer Service",
    description="Neuro-symbolic verification API for support ticket routing workflows",
    version="1.0.0",
)


@app.post("/review", response_model=ReviewResult)
def api_review(bundle: ReviewBundle, ablate_z3: bool = False) -> ReviewResult:
    try:
        engine = ReviewEngine(model_client=FakeModelClient(), ablate_z3=ablate_z3)
        return engine.review(bundle)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def main():
    parser = argparse.ArgumentParser(
        description="Shodh AI - AI-Assisted Workflow Reviewer (CLI)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # review subcommand
    review_parser = subparsers.add_parser("review", help="Review a workflow bundle JSON file")
    review_parser.add_argument("bundle_path", type=str, help="Path to bundle JSON file")
    review_parser.add_argument(
        "--ablate-z3",
        action="store_true",
        help="Ablate Z3 solver (fall back to naive syntactic matching)",
    )
    review_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional path to write output JSON result",
    )
    review_parser.add_argument(
        "--fake-mode",
        type=str,
        default="normal",
        choices=["normal", "malformed_json", "truncated_json", "invented_rule_id", "prompt_injection_attack", "timeout"],
        help="Test failure mode for FakeModelClient",
    )

    # serve subcommand
    serve_parser = subparsers.add_parser("serve", help="Start FastAPI review microservice")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    if args.command == "serve":
        uvicorn.run("reviewer.cli:app", host=args.host, port=args.port, reload=False)
        return

    if args.command == "review":
        with open(args.bundle_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        bundle = ReviewBundle.model_validate(data)
        client = FakeModelClient(mode=args.fake_mode)
        engine = ReviewEngine(model_client=client, ablate_z3=args.ablate_z3)
        result = engine.review(bundle)

        output_json = result.model_dump_json(indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json)
            print(f"Review verdict written to: {args.output}")
        else:
            print(output_json)


if __name__ == "__main__":
    main()
