from __future__ import annotations

import argparse
import os
from collections.abc import Iterable
from pathlib import Path

from logging_config import configure_logging
from sourcing import new_debug_candidates_path, source_topic

DEFAULT_ENV_PATH = Path(__file__).with_name(".env")
DEFAULT_STAGE = "all"
STAGES = ("source", "analyze", "memo", "all")


def load_env_file(env_path: Path = DEFAULT_ENV_PATH) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI-Augmented Investment Pipeline")
    parser.add_argument("--topic", required=True, help="Investment theme to analyze")
    parser.add_argument(
        "--stage",
        choices=STAGES,
        default=DEFAULT_STAGE,
        help="Pipeline stage to run",
    )
    return parser


def summarize_environment(keys: Iterable[str]) -> dict[str, str | None]:
    return {key: os.environ.get(key) for key in keys}


def main() -> None:
    load_env_file()
    args = build_parser().parse_args()
    log_path = configure_logging(args.stage)

    summary = summarize_environment(("OPENAI_API_KEY", "PRODUCT_HUNT_TOKEN"))
    print(f"topic={args.topic}")
    print(f"stage={args.stage}")
    print(f"log_path={log_path}")
    print(f"env_loaded={{{', '.join(f'{key}: {'set' if value else 'missing'}' for key, value in summary.items())}}}")

    if args.stage in {"source", "all"}:
        output_path = new_debug_candidates_path()
        posts = source_topic(args.topic, output_path=output_path)
        print(f"source_posts={len(posts)}")
        print(f"source_output={output_path}")

    if args.stage in {"analyze", "memo", "all"}:
        print("remaining_stages=not_implemented")


if __name__ == "__main__":
    main()