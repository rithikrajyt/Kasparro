"""CLI runner for the Promotion Readiness Agent."""

import argparse
import json
import sys

from agent import run_readiness_check


def main():
    parser = argparse.ArgumentParser(description="Promotion Readiness Agent CLI")
    parser.add_argument("--question", default="Are we ready to send?")
    parser.add_argument("--rehearsal", choices=["A", "B", "C", "D", "E", "F", "G"], default="A")
    parser.add_argument("--simulate-failure", action="store_true")
    parser.add_argument("--output", default=None, help="Write JSON result to file")
    args = parser.parse_args()

    result = run_readiness_check(
        question=args.question,
        rehearsal=args.rehearsal,
        simulate_failure=args.simulate_failure,
    )

    print(f"\n{'='*60}")
    print(f"  RECOMMENDATION: {result['recommendation']}")
    print(f"{'='*60}")
    print(f"  Run ID:     {result['run_id']}")
    print(f"  Rehearsal:  {result['rehearsal']}")
    print(f"  Question:   {result['founder_question']}")
    print(f"  Checks:     {result['summary']['total_checks']} total, "
          f"{result['summary']['passed']} passed, "
          f"{result['summary']['failed']} failed, "
          f"{result['summary']['unverified']} unverified")
    print(f"{'='*60}\n")

    if result["blockers"]:
        print("BLOCKERS:")
        for b in result["blockers"]:
            print(f"  [{b['owner']}] {b['description']}")
            print(f"    Action: {b['action']}\n")

    if result["unverified_items"]:
        print("UNVERIFIED:")
        for u in result["unverified_items"]:
            print(f"  {u.get('check_id', u.get('product_id'))}: {u['reason']}")

    print(f"\nFounder approval required: {result['founder_approval_required']}")
    print(f"Send action performed: {result['send_action_performed']}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nJSON report saved to {args.output}")
    else:
        print("\nFull JSON:")
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
