# WP2 Service Identifier

Blindly identifies the service type of an unknown EOSC EDEN endpoint by probing it
and scoring its responses against all known service profiles.

Companion tool to [wp2-service-validator](../service-validator).

## Usage

### CLI

```bash
python identify_service.py --url "https://example.com/oai"
```

Options:
- `--min-confidence FLOAT` — minimum score to report a match (default: 3.0)
- `--ambiguity-gap FLOAT` — score gap below which result is flagged ambiguous (default: 1.0)
- `--max-runners-up INT` — number of runner-up candidates in output (default: 3)
- `--threads INT` — max parallel probe threads (default: 10)

### Web API

```bash
uvicorn main:app --reload --port 8001
# or
python main.py
```

`GET /identify?url=<endpoint_url>`

Interactive docs: http://127.0.0.1:8001/docs

### Batch (CSV)

```bash
python batch_identifier.py --input endpoints.csv --output results.csv
```

Input CSV columns: `endpoint`, `serviceTitle` (optional), `repoTitle` (optional)

### Batch (Fuseki)

```bash
python batch_identifier.py --fuseki http://localhost:3030/service_registry_store/query
```

Environment variables for auth: `FUSEKI_USERNAME`, `FUSEKI_PASSWORD`

## How It Works

1. **PreFilter** — scheme shortcuts for AMQP/MQTT/XMPP; routes FTP via ftplib
2. **InitialProbe** — bare GET to the URL; HTML classification (doc pages, decommissioned services)
3. **ShortList** — score all candidate profiles against initial response; keep scores >= 1.0
4. **TargetedProbes** — parallel probes using each shortlisted profile's specific suffix
5. **Rank** — apply confidence thresholds; flag ambiguous results; return best match + runners-up

## Output Schema

````json
{
  "identified_type": "OAI-PMH",
  "confidence": 8.5,
  "ambiguous": false,
  "runners_up": [
    {
      "service_type": "OAI-Static",
      "score": 4.1,
      "matched_mime": true,
      "matched_body_signatures": ["<oai-pmh"]
    }
  ],
  "url": "https://example.com/oai",
  "final_url": "https://example.com/oai",
  "had_redirect": false,
  "probed_url": "https://example.com/oai?verb=Identify",
  "status_code": 200,
  "content_type": "text/xml",
  "error": null,
  "note": null
}
````

Null result (no confident match):
````json
{
  "identified_type": null,
  "confidence": 1.8,
  "note": "No profile matched with sufficient confidence (best: REST @ 1.8)"
}
````

Ambiguous result:
````json
{
  "identified_type": "SPARQL",
  "confidence": 6.2,
  "ambiguous": true,
  "note": "Top candidates are within 1.0 score points — manual review recommended"
}
````

## Installation

```bash
pip install -r requirements.txt
```

## Updating Service Profiles

`service_profiles.json` is a local copy from the service-validator. To update:

```bash
cp ../service-validator/service_profiles.json service_profiles.json
```

## Running Tests

```bash
pytest tests/ -v
```
