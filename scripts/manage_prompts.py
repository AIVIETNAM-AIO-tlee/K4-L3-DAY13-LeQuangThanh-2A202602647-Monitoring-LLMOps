from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

dotenv.load_dotenv()

from app.tracing import get_langfuse_client


def get_prompt_status() -> None:
    client = get_langfuse_client()
    try:
        p_prod = client.get_prompt("day13-chat", label="production")
        print(f"[PROMPT STATUS] 'production' label points to Version: {p_prod.version}")
        print(f"Content:\n{p_prod.prompt}")
    except Exception as e:
        print(f"Error getting production prompt: {e}")

    try:
        p_base = client.get_prompt("day13-chat", label="baseline")
        print(f"\n[PROMPT STATUS] 'baseline' label points to Version: {p_base.version}")
    except Exception as e:
        print(f"Error getting baseline prompt: {e}")

    try:
        p_cand = client.get_prompt("day13-chat", label="candidate")
        print(f"\n[PROMPT STATUS] 'candidate' label points to Version: {p_cand.version}")
    except Exception as e:
        print(f"Error getting candidate prompt: {e}")


def promote_v2() -> None:
    client = get_langfuse_client()
    res = client.update_prompt(name="day13-chat", version=2, new_labels=["candidate", "production"])
    client.clear_prompt_cache()
    try:
        import httpx
        httpx.post("http://127.0.0.1:8000/prompts/clear-cache", timeout=2.0)
    except Exception:
        pass
    print(f"Successfully promoted Version 2 to 'production'! Labels: {getattr(res, 'labels', None)}")


def rollback_v1() -> None:
    client = get_langfuse_client()
    res = client.update_prompt(name="day13-chat", version=1, new_labels=["baseline", "production"])
    client.clear_prompt_cache()
    try:
        import httpx
        httpx.post("http://127.0.0.1:8000/prompts/clear-cache", timeout=2.0)
    except Exception:
        pass
    print(f"Successfully rolled back 'production' to Version 1! Labels: {getattr(res, 'labels', None)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Langfuse Prompts (Day 13)")
    parser.add_argument("action", choices=["status", "promote", "rollback"], help="Action to perform")
    args = parser.parse_args()

    if args.action == "status":
        get_prompt_status()
    elif args.action == "promote":
        promote_v2()
    elif args.action == "rollback":
        rollback_v1()


if __name__ == "__main__":
    main()
