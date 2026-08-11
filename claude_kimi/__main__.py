"""CLI entry point: python -m claude_kimi "task" --mode review"""

from __future__ import annotations

import argparse

from .exchange import Exchange


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="claude_kimi",
        description="Have Claude and Kimi exchange prompts and results to complete a task.",
    )
    parser.add_argument("task", help="The task or question for the two agents")
    parser.add_argument(
        "--mode",
        choices=["review", "collab", "debate"],
        default="review",
        help="Collaboration pattern (default: review)",
    )
    parser.add_argument(
        "--rounds", type=int, default=4, help="Max exchange rounds (default: 4)"
    )
    parser.add_argument(
        "--out", default="transcripts", help="Directory for saved transcripts"
    )
    args = parser.parse_args()

    exchange = Exchange(task=args.task, mode=args.mode, max_rounds=args.rounds)
    result = exchange.run()
    path = exchange.save(args.out)

    print("=" * 70)
    print("RESULT")
    print("=" * 70)
    print(result)
    print(f"\nTranscript saved to: {path}")


if __name__ == "__main__":
    main()
