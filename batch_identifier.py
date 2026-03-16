"""
wp2-service-identifier — Batch processor.

Usage:
    python batch_identifier.py                    # queries Fuseki (default)
    python batch_identifier.py --fuseki http://...
    python batch_identifier.py --input data.csv
    python batch_identifier.py --input data.csv --output results.csv
"""
import argparse
import csv
import dataclasses
import logging
import os

from Identifier import ServiceIdentifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = "identification_results.csv"
_EXTRA_FIELDS = ["identified_type", "confidence", "ambiguous", "runners_up", "note", "error"]


def run_csv_batch(input_path: str, output_path: str, identifier: ServiceIdentifier = None):
    """Process a CSV file of endpoints, writing identification results to output_path."""
    if identifier is None:
        identifier = ServiceIdentifier()

    with open(input_path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(2048)
        f.seek(0)
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        reader = csv.DictReader(f, delimiter=delimiter)
        rows = list(reader)

    if not rows:
        logger.warning("No rows found in %s", input_path)
        return

    input_fields = list(rows[0].keys())
    output_fields = input_fields + [f for f in _EXTRA_FIELDS if f not in input_fields]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields)
        writer.writeheader()

        for i, row in enumerate(rows):
            url = row.get("endpoint", "").strip()
            if not url:
                logger.warning("Row %d: no endpoint URL, skipping", i + 1)
                continue

            logger.info("Identifying %s (%d/%d)", url, i + 1, len(rows))
            result = identifier.identify_url(url)
            d = dataclasses.asdict(result)

            runners_up = d.get("runners_up", [])
            out_row = dict(row)
            out_row["identified_type"] = d.get("identified_type") or ""
            out_row["confidence"] = d.get("confidence") if d.get("confidence") is not None else ""
            out_row["ambiguous"] = d.get("ambiguous", False)
            out_row["runners_up"] = "; ".join(
                f"{r['service_type']}({r['score']})" for r in runners_up
            )
            out_row["note"] = d.get("note") or ""
            out_row["error"] = d.get("error") or ""
            writer.writerow(out_row)

    logger.info("Results written to %s", output_path)


def run_fuseki_batch(fuseki_url: str, output_path: str, identifier: ServiceIdentifier = None):
    """Query Fuseki for harvested endpoints and identify each one."""
    from fuseki_loader import FusekiLoader

    if identifier is None:
        identifier = ServiceIdentifier()

    username = os.environ.get("FUSEKI_USERNAME")
    password = os.environ.get("FUSEKI_PASSWORD")

    loader = FusekiLoader(fuseki_url, username=username, password=password)
    records = loader.load_services()

    if not records:
        logger.warning("No records returned from Fuseki")
        return

    output_fields = ["endpoint_url", "service_title", "repo_title"] + _EXTRA_FIELDS

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields)
        writer.writeheader()

        for i, record in enumerate(records):
            url = record.get("endpoint_url", "").strip()
            if not url:
                continue

            logger.info("Identifying %s (%d/%d)", url, i + 1, len(records))
            result = identifier.identify_url(url)
            d = dataclasses.asdict(result)

            runners_up = d.get("runners_up", [])
            writer.writerow({
                "endpoint_url": url,
                "service_title": record.get("service_title", ""),
                "repo_title": record.get("repo_title", ""),
                "identified_type": d.get("identified_type") or "",
                "confidence": d.get("confidence") if d.get("confidence") is not None else "",
                "ambiguous": d.get("ambiguous", False),
                "runners_up": "; ".join(f"{r['service_type']}({r['score']})" for r in runners_up),
                "note": d.get("note") or "",
                "error": d.get("error") or "",
            })

    logger.info("Results written to %s", output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Batch identify service types for EOSC EDEN endpoints."
    )
    parser.add_argument("--input", help="Path to input CSV file (alternative to Fuseki)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help=f"Output CSV path (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--fuseki",
                        default="http://localhost:3030/service_registry_store/query",
                        help="Fuseki SPARQL endpoint URL")
    args = parser.parse_args()

    if args.input:
        run_csv_batch(args.input, args.output)
    else:
        run_fuseki_batch(args.fuseki, args.output)


if __name__ == "__main__":
    main()
