"""
wp2-service-identifier — CLI entry point.

Usage:
    python identify_service.py --url "https://example.com/oai"
    python identify_service.py --url "https://example.com/oai" --min-confidence 4.0
    python identify_service.py   # interactive mode
"""
import argparse
import dataclasses
import json
import logging
import sys

from dotenv import load_dotenv
load_dotenv()

from Identifier import ServiceIdentifier


def main():
    parser = argparse.ArgumentParser(
        description="Identify the service type of an unknown endpoint."
    )
    parser.add_argument("--url", help="Endpoint URL to identify")
    parser.add_argument("--min-confidence", type=float, default=3.0,
                        help="Minimum confidence score to report a match (default: 3.0)")
    parser.add_argument("--ambiguity-gap", type=float, default=1.0,
                        help="Score gap below which result is flagged ambiguous (default: 1.0)")
    parser.add_argument("--max-runners-up", type=int, default=3,
                        help="Maximum number of runner-up candidates to return (default: 3)")
    parser.add_argument("--threads", type=int, default=10,
                        help="Max parallel probe threads (default: 10)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show INFO log messages (e.g. FFIS queries)")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    url = args.url
    if not url:
        url = input("Enter Service URL: ").strip()
        if not url:
            print("No URL provided.", file=sys.stderr)
            sys.exit(1)

    identifier = ServiceIdentifier(
        min_confidence=args.min_confidence,
        ambiguity_gap=args.ambiguity_gap,
        max_runners_up=args.max_runners_up,
        max_threads=args.threads,
    )

    result = identifier.identify_url(url)
    print(json.dumps(dataclasses.asdict(result), indent=2))


if __name__ == "__main__":
    main()
