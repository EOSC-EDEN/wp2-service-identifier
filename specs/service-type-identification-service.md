# Service Type Identification Service (STIS) Specification

**Version:** 0.1.0 (Draft)
**Date:** 2026-03-16
**Status:** Proposed specification for the EOSC EDEN architecture, open for review by EDEN technical working groups.

## Abstract

This specification defines the functional and technical requirements for a Service Type Identification Service (STIS) within the EOSC EDEN ecosystem. The STIS is responsible for determining the protocol type and capability profile of an unknown endpoint by issuing structured HTTP probes and scoring responses against a curated registry of known service profiles. By identifying endpoints as specific service types (e.g., OAI-PMH, SPARQL, OGC-WMS), this service enables automated harvesting pipelines, interoperability assessments, and service registry population tasks to proceed without prior knowledge of what protocol an endpoint speaks.

## Rationale

EOSC harvesting workflows and repository aggregators routinely encounter endpoint URLs with no reliable accompanying metadata indicating the endpoint's protocol. Manually curating service type metadata does not scale across the breadth of EOSC-participating infrastructure. This service performs blind protocol identification by probing endpoints and scoring responses against signatures of known service types, providing the prerequisite input for harvest routing, capability negotiation, and service registry enrichment. There is no existing centralized orchestrator for this task in the EOSC context.

## Introduction

In the context of federated scientific infrastructure such as EOSC, endpoints are discovered through a variety of channels—SPARQL harvests, link-following, manual submission—without guaranteed metadata describing the endpoint's protocol or capability profile. Without accurate type identification, automated systems cannot select the correct harvesting strategy, negotiate capabilities, or populate service registries with accurate service-type metadata.

The Service Type Identification Service addresses this gap. It serves two critical purposes:

1. **Harvest Routing:** It provides the protocol classification needed to route an endpoint to the correct harvesting adapter (e.g., using OAI-PMH `ListRecords` only after confirming the endpoint speaks OAI-PMH).
2. **Registry Enrichment:** It produces machine-actionable evidence to populate or validate the `service type` field in EOSC service registries and knowledge graphs, reducing manual curation burden.

This service operates in the context of EOSC EDEN WP2, specifically supporting automated service discovery and harvest pipeline orchestration. The output of this service is a prerequisite for any downstream service that must select a protocol-specific behaviour, such as a metadata harvester, a capability negotiator, or a conformance checker.

## Scope

### In scope

* **Blind protocol identification:** Identification of the service type and protocol profile of an endpoint using only its URL, without requiring the caller to supply an assumed type.
* **Multi-stage probing pipeline:** A structured sequence of probes that narrows candidates progressively:
    * Initial response scoring against all candidate profiles to form a shortlist.
    * Targeted protocol-specific probes for shortlisted candidates (e.g., appending `?verb=Identify` for OAI-PMH).
    * Parallel execution of targeted probes to minimize latency.
* **Non-HTTP scheme shortcuts:** Immediate classification of endpoints using non-HTTP schemes (e.g., `amqp://`, `mqtt://`, `xmpp://`, `ftp://`) without issuing HTTP probes.
* **Scoring and confidence:** A deterministic scoring function that assigns a numeric confidence value to each candidate profile, enabling ranking and threshold-based filtering.
* **Ambiguity detection:** Detection and reporting of cases where the top two candidate types score within a configurable gap, indicating the result may be unreliable.
* **Runner-up reporting:** Reporting of the ranked list of alternative candidate types below the top match, to support downstream disambiguation workflows.
* **Batch processing:** Processing of multiple endpoint URLs provided as a structured input (e.g., CSV file or SPARQL query result from a Fuseki triple store).
* **Structured output:** Machine-actionable output in a structured format (JSON) including identification result, confidence, ambiguity flag, provenance, and runner-up candidates.
* **Multiple interface modes:** The service MUST be operable via a command-line interface, a REST API, and a batch processing mode.
* **Deployment model:** The service specification is deployment-agnostic:
    * MUST be deployable locally (e.g., via Container/Docker) for pipelines requiring data sovereignty or offline operation.
    * MAY be deployed as a centralized/SaaS solution for lower-volume or less technical consumers.

### Out of scope

* **Service validation:** Verifying that an identified endpoint fully conforms to its claimed protocol specification (e.g., that an OAI-PMH endpoint correctly implements all required verbs) is a separate service that relies on identification.
* **Metadata harvesting:** Extracting records from an identified endpoint is out of scope; this service produces only the classification needed to route a subsequent harvesting operation.
* **Capability negotiation:** Determining the full capability set of an endpoint (e.g., which OGC operations are supported) is the responsibility of a downstream service.
* **Service registry management:** Persisting identification results into a registry or knowledge graph is not the responsibility of the STIS; the service produces structured output that a registry population tool may consume.
* **Authentication brokering:** The service does not manage credentials or authentication tokens for accessing protected endpoints. It operates on publicly accessible or pre-authorized endpoints.
* **Content quality assessment:** The quality, completeness, or semantic correctness of the content returned by an identified endpoint is not assessed by this service.
* **Recursive content crawling:** The service probes a single root endpoint per identification request. It does not follow links or recursively enumerate sub-paths.

## Core Preservation Processes

The STIS operates on external service endpoints — outside the TDA (Trustworthy Digital Archive) boundary — and generates the service-type evidence that downstream CPPs require to operate correctly. Without protocol identification, harvest routing, discovery catalogue population, and metadata management cannot proceed reliably. The STIS is therefore a prerequisite for the WP2 harvesting pipeline that feeds these CPP-governed processes.

### CPP Relationship Summary

The table below maps the STIS's relationships to specific CPPs. The Scope column uses two values: **WP1 framework** denotes a relationship defined within the formal EOSC EDEN CPP framework; **WP2 pipeline** denotes a relationship that holds in the EOSC EDEN harvesting pipeline deployment context.

| Relationship | CPP | OAIS Area | Scope | Rationale |
|---|---|---|---|---|
| Prerequisite for | CPP-029 Ingest | Ingest | WP2 pipeline | In the EOSC EDEN harvesting pipeline, ingest must select the correct protocol adapter (OAI-PMH, SPARQL, OGC, etc.) before a SIP can be submitted; the STIS provides the protocol classification needed for that routing decision. |
| Produces input for | CPP-024 Enabling Discovery | Data Management | WP2 pipeline | The STIS output — service type, confidence, and provenance — constitutes the machine-actionable metadata record needed to populate a service endpoint catalogue or registry of the kind that CPP-024-compliant discovery processes can query. |
| Produces input for | CPP-016 Metadata Ingest and Management | Data Management | WP1 framework + WP2 pipeline | The identification result (service type, confidence, ambiguity flag, resolved URL, HTTP status, content-type) maps directly to *Technical metadata* and *Provenance metadata* as defined in CPP-016; this metadata about the service endpoint must itself be ingested and managed. |
| Conceptual analogue | CPP-008 File Format Identification | Administration | WP1 framework (analogue, not dependency) | The STIS performs for service endpoints what CPP-008 performs for files: both identify the "type" of an artifact using signatures and scoring, producing Technical and Provenance metadata that unlocks downstream preservation actions. The STIS is not a TDA-internal process, but the structural parallel is intentional and directly informs the STIS's scoring model and evidence design. |

### Inputs and Outputs

**Input:** An endpoint URL — the service-level equivalent of a *File* in CPP-008 — optionally accompanied by configuration parameters (confidence threshold, ambiguity gap, desired number of runner-up candidates).

**Output:** A structured identification result serving as *Technical metadata* and *Provenance metadata* about the service endpoint. The result MUST include:

* **Technical metadata (Classification):**
    * Identified service type (e.g., `OAI-PMH`, `SPARQL`, `OGC-WMS`)
    * Confidence score (numeric)
    * Ambiguity flag (boolean)
* **Provenance metadata:**
    * The URL as resolved (after any redirects)
    * The probed URL used for the winning candidate (including any appended query parameters)
    * HTTP status code of the winning probe response
    * Content-Type of the winning probe response
    * Any error or informational note (e.g., connection timeout, HTML documentation page detected)
* **Runner-up candidates:** A ranked list of alternative matches, each with service type, score, and matched evidence (MIME type match, body signatures matched)

### Outcome Classification

* *Success:* Endpoint matched a known service profile above the minimum confidence threshold, unambiguously.
* *Ambiguous:* Top two candidates are within the configured ambiguity gap; result may be unreliable.
* *No match:* No candidate profile exceeded the minimum confidence threshold.
* *Error:* Endpoint was unreachable, returned an unsupported scheme, or resulted in a connection failure.

## Conformance

The keywords MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

## Normative Requirements

### Requirement Group 1 – Identification Methodology

* **{{ STIS-REQ-1-01 }}** The Service MUST identify the service type of an endpoint using only the endpoint URL, without requiring the caller to specify an assumed service type.
* **{{ STIS-REQ-1-02 }}** The Service MUST implement a multi-stage probing pipeline. At minimum, the pipeline MUST include:
    * An initial probe stage that issues a bare GET request to the URL as provided.
    * A shortlisting stage that scores the initial response against all candidate profiles and retains only those scoring above a low threshold.
    * A targeted probe stage that issues protocol-specific requests for each shortlisted candidate.
    * A ranking stage that applies a minimum confidence threshold and emits a final result.
* **{{ STIS-REQ-1-03 }}** The Service MUST execute targeted probes for shortlisted candidates in parallel to minimize total identification latency. The maximum number of concurrent probe threads SHOULD be configurable.
* **{{ STIS-REQ-1-04 }}** The Service MUST handle non-HTTP schemes (e.g., `amqp://`, `mqtt://`, `xmpp://`, `ftp://`) by returning an immediate classification result without issuing HTTP probes, where the scheme itself is sufficient for identification.
* **{{ STIS-REQ-1-05 }}** The Service MUST classify endpoints returning HTML documentation pages or decommissioned service notices (as detectable from response structure) as non-live services and return an appropriate informational result rather than a false service type match.
* **{{ STIS-REQ-1-06 }}** The Service MUST apply a configurable per-request timeout to all outbound HTTP probes. Probes that exceed the timeout MUST be treated as failed; they MUST NOT block the result and MUST score zero rather than inheriting any prior score from the shortlisting stage.
* **{{ STIS-REQ-1-07 }}** The Service SHOULD follow HTTP redirects and MUST report the final resolved URL in the output, along with a flag indicating whether a redirect occurred.

### Requirement Group 2 – Service Profile Registry

* **{{ STIS-REQ-2-01 }}** The Service MUST maintain a profile registry defining the identifiable service types and their corresponding detection signatures. Each profile MUST specify at minimum:
    * A unique service type identifier (e.g., `OAI-PMH`, `SPARQL`).
    * Probe parameters: the URL suffix or query parameters to append for targeted probing, and the HTTP method.
    * Expected MIME type(s) for the targeted probe response.
    * Body signatures: one or more substring or regular expression patterns whose presence in the response body is indicative of the service type.
* **{{ STIS-REQ-2-02 }}** The profile registry SHOULD include coverage of the following service type categories relevant to EOSC-participating infrastructure:
    * Metadata/discovery protocols (e.g., OAI-PMH, ATOM/RSS feeds, Sitemaps).
    * Geospatial/OGC services (e.g., WMS, WFS, WCS, WMTS, CSW, SOS).
    * SPARQL endpoints and IVOA-standard astronomy services (e.g., TAP, SCS, SIA, SLAP, SSA, VOSpace).
    * Scientific data access services (e.g., OpenDAP, THREDDS, ERDDAP, NetCDF).
    * General-purpose web service patterns (e.g., REST/OpenAPI, SOAP, GraphQL).
    * Message queue protocols (e.g., AMQP, MQTT).
    * File transfer protocols (e.g., FTP).
* **{{ STIS-REQ-2-03 }}** The profile registry MUST be machine-readable and validated against a schema to prevent misconfiguration. Changes to the registry MUST not require code changes to the identification engine.
* **{{ STIS-REQ-2-04 }}** The Service SHOULD support an index of known specification namespace URIs (e.g., `http://www.openarchives.org/OAI/2.0/`) that, when found in a response body, provide additional evidence for a specific profile. This index MUST be derived from the profile registry and MUST be built at service initialization, not per-request.

### Requirement Group 3 – Scoring and Confidence

* **{{ STIS-REQ-3-01 }}** The Service MUST assign a numeric confidence score to each candidate profile for each probe response. The scoring function MUST be deterministic: identical inputs MUST produce identical scores.
* **{{ STIS-REQ-3-02 }}** The scoring function SHOULD reward the following evidence signals, each contributing a defined maximum number of points:
    * HTTP status code in the 2xx or 3xx range.
    * Response `Content-Type` matching the profile's expected MIME type.
    * Presence of body signatures defined in the profile (partial credit awarded proportionally to the fraction of signatures matched).
    * Presence of a known specification namespace URI in the response body.
* **{{ STIS-REQ-3-03 }}** The Service MUST apply a configurable minimum confidence threshold. Candidates scoring below this threshold MUST NOT be reported as a match; the result MUST indicate no match was found.
* **{{ STIS-REQ-3-04 }}** The Service MUST detect and report ambiguous results. A result is ambiguous when the score difference between the top-ranked and second-ranked candidates is less than or equal to a configurable ambiguity gap. Ambiguous results MUST be clearly flagged in the output and MUST NOT be treated as definitive identifications without further investigation.
* **{{ STIS-REQ-3-05 }}** Confidence scores MUST be bounded to a defined maximum value (e.g., 10.0). The score ceiling MUST be documented.
* **{{ STIS-REQ-3-06 }}** The shortlisting stage MUST apply a configurable low threshold to filter out clearly non-matching profiles before targeted probing. Only profiles meeting the low threshold SHOULD proceed to targeted probing, to avoid unnecessary network requests.

### Requirement Group 4 – Reporting and Output

* **{{ STIS-REQ-4-01 }}** The Service MUST produce machine-actionable output in a structured format (e.g., JSON). The output MUST be parseable without additional transformation by downstream automated workflows.
* **{{ STIS-REQ-4-02 }}** The output MUST include all fields described in the "Core Preservation Processes" section: identified service type, confidence score, ambiguity flag, resolved URL, redirect flag, probed URL, HTTP status code, content-type, runner-up candidates, and outcome/error information.
* **{{ STIS-REQ-4-03 }}** Runner-up candidate entries in the output MUST include, at minimum: service type identifier, score, whether the MIME type matched, and which body signatures were matched. This evidence MUST be sufficient for a human or downstream system to understand why a candidate was ranked.
* **{{ STIS-REQ-4-04 }}** The output MUST distinguish between the following outcome states: successful unambiguous match, ambiguous match, no match, and error (unreachable endpoint, unsupported scheme, connection failure). Each state MUST be representable in the structured output.
* **{{ STIS-REQ-4-05 }}** The number of runner-up candidates included in the output SHOULD be configurable by the caller.

### Requirement Group 5 – Integration and Interface

* **{{ STIS-REQ-5-01 }}** The Service MUST provide a REST API accepting a URL as input and returning the structured identification result. The API MUST support at minimum:
    * A required `url` parameter identifying the endpoint to probe.
    * Optional parameters for minimum confidence threshold, ambiguity gap, and maximum runner-up count.
* **{{ STIS-REQ-5-02 }}** The Service MUST provide a command-line interface (CLI) that accepts a URL and optional configuration parameters, and prints the identification result to standard output.
* **{{ STIS-REQ-5-03 }}** The Service MUST provide a batch processing mode capable of processing multiple endpoint URLs supplied as a structured input file (e.g., CSV). The batch mode MUST write results to an output file.
* **{{ STIS-REQ-5-04 }}** The Service SHOULD support batch input from a SPARQL query against an RDF triple store (e.g., Apache Jena Fuseki), to enable integration with EOSC knowledge graph workflows where harvested service endpoints are stored as RDF.
* **{{ STIS-REQ-5-05 }}** The Service SHALL provide a user interface (e.g., auto-generated API documentation such as Swagger/OpenAPI) so that humans can interact with the identification functionality via a browser without requiring programmatic access.
* **{{ STIS-REQ-5-06 }}** The REST API MUST expose its parameter contracts via a machine-readable OpenAPI schema to facilitate integration by downstream tools and services.

### Requirement Group 6 – Security

* **{{ STIS-REQ-6-01 }}** The Service MUST enforce a configurable timeout on all outbound HTTP probes. Probes that exceed the timeout MUST be terminated and treated as failures.
* **{{ STIS-REQ-6-02 }}** The Service MUST validate and sanitize all caller-supplied URL inputs before issuing any outbound probe requests, to prevent Server-Side Request Forgery (SSRF) and path traversal attacks.
* **{{ STIS-REQ-6-03 }}** The Service SHOULD implement authentication and authorization on the REST API.
* **{{ STIS-REQ-6-04 }}** Transfer of data to and from the REST API SHOULD be encrypted in transit (e.g., HTTPS / TLS 1.2 or higher).
* **{{ STIS-REQ-6-05 }}** The Service MUST implement protections against resource exhaustion, including limits on response body size consumed during scoring (to prevent memory exhaustion from maliciously large responses) and limits on concurrent outbound probes.
* **{{ STIS-REQ-6-06 }}** The Service MUST NOT follow redirects to private network address ranges (e.g., `10.0.0.0/8`, `169.254.0.0/16`, `127.0.0.0/8`) when deployed in a shared/SaaS environment, to prevent SSRF via redirect chains.

### Requirement Group 7 – Deployment

* **{{ STIS-REQ-7-01 }}** The Service MUST be deployable locally (e.g., via Container/Docker) for pipelines requiring data sovereignty, offline operation, or integration with local network resources.
* **{{ STIS-REQ-7-02 }}** The Service MAY be deployed as a centralized/SaaS solution for lower-volume or less technical consumers.
* **{{ STIS-REQ-7-03 }}** The Service MUST be operable in environments with restricted or no external internet connectivity. In such environments, probe results relying only on locally accessible endpoints MUST be supported.

## Non-normative Guidance

### Pipeline Implementation Considerations

* **Probe connection reuse:** It is strongly recommended to use a shared HTTP session (e.g., `requests.Session`) across all probes within a single identification request. This enables TCP connection pooling and reduces overhead for targeted probes against the same host.
* **Shortlist threshold tuning:** The low threshold for shortlisting (applied before targeted probing) should be set conservatively (e.g., ≥ 1.0 out of 10.0). Setting it too high will prematurely eliminate candidates that need a targeted probe to score well; setting it too low will cause unnecessary probes against non-matching profiles.
* **Targeted probe timeout behaviour:** If a targeted probe times out, the candidate MUST score 0.0 rather than inheriting its shortlist score. This prevents unreachable but plausible-looking candidates from being reported as matches.
* **Parallel probe thread count:** A default of 10 concurrent threads is reasonable for most deployments. In high-throughput batch environments, this should be tunable per batch run.

### Scoring Design Considerations

* **Evidence signal weights:** The recommended scoring weights (each contributing to a maximum of 10.0 points) are:
    * HTTP 2xx/3xx status: 3 points.
    * MIME type match: 2 points.
    * Body signature matches (partial credit): 3 points (proportional to fraction matched).
    * Spec namespace URI found in body: 2 points.
* **Body signature design:** Profile body signatures should be chosen to be highly discriminating. Signatures that appear in responses of many different service types (e.g., generic XML declarations) should be avoided or assigned low weight. Prefer strings or patterns that are normatively part of the service protocol (e.g., XML namespace URIs, protocol-specific element names).
* **Score ceiling:** Clamping scores to 10.0 ensures that an accumulation of partial credits from multiple signals cannot falsely elevate a weak candidate above a true match.

### Profile Registry Management

* **Registry as single source of truth:** The profile registry (e.g., `service_profiles.json`) should be the single configuration artefact that defines what service types are recognizable and how they are detected. The identification engine should be generic over the registry; adding a new service type should require only a new profile entry, not code changes.
* **Schema validation:** The registry file should be validated against a JSON Schema on service startup to catch misconfigured profiles early. Invalid profiles should cause a startup failure, not silent misidentification at runtime.
* **Spec URI index:** Mapping known specification namespace URIs to profile keys (built once at startup from the registry) avoids repeated scanning of the registry on every scoring call and provides O(1) lookup for URI-based evidence.

### Handling Ambiguous and No-Match Results

* **Ambiguous results:** When the top two candidates score within the ambiguity gap, the result should be flagged as ambiguous and both candidates reported with their evidence. The recommended default gap is 1.0 out of 10.0. Downstream systems should treat ambiguous results as requiring human review or additional disambiguation probes rather than as definitive classifications.
* **No-match results:** If no candidate exceeds the minimum confidence threshold (recommended default: 3.0 out of 10.0), the service should return a `null` identification result with the full runner-up list (if any candidates scored above the low threshold). This supports debugging and manual classification.
* **HTML documentation page detection:** Many inactive or decommissioned endpoints return HTML documentation pages at their root URL. The initial probe stage should detect this condition (e.g., by checking `Content-Type: text/html` combined with the absence of any service-indicative signatures) and return an informational note rather than scoring against service profiles.

### Batch Processing Considerations

* **CSV mode:** Batch input via CSV should accept a column containing endpoint URLs and write one output row per URL. The output schema should mirror the single-URL result, serialised to CSV-compatible fields. Empty or malformed URL entries should be skipped with a logged warning, not cause batch failure.
* **Fuseki/SPARQL mode:** When batch input is sourced from a SPARQL query against a Fuseki triple store, the query result should be mapped to a list of endpoint URLs before processing. The SPARQL query interface should be configurable to support different graph structures across deployments.
* **Idempotency:** Batch processing should be idempotent: re-running the same batch against the same endpoints should produce the same output, modulo any endpoint state changes.

### SSRF Mitigation in Shared Deployments

* When deployed as a shared/SaaS service, the STIS issues outbound HTTP requests on behalf of callers. This creates SSRF risk if callers can supply arbitrary URLs targeting internal infrastructure. Implementations should:
    * Resolve the hostname of the supplied URL before issuing any probe and reject private/loopback address ranges.
    * Validate that redirect targets do not resolve to private ranges.
    * Consider a URL allowlist or denylist appropriate to the deployment context.

### Example Output Structures

**Successful unambiguous identification:**
```json
{
  "url": "https://example.org/oai",
  "identified_type": "OAI-PMH",
  "confidence": 8.5,
  "ambiguous": false,
  "runners_up": [
    {
      "service_type": "ATOM",
      "score": 2.1,
      "matched_mime": false,
      "matched_body_signatures": []
    }
  ],
  "final_url": "https://example.org/oai",
  "had_redirect": false,
  "probed_url": "https://example.org/oai?verb=Identify",
  "status_code": 200,
  "content_type": "text/xml;charset=UTF-8",
  "error": null,
  "note": null
}
```

**Ambiguous result:**
```json
{
  "url": "https://example.org/data",
  "identified_type": "SPARQL",
  "confidence": 5.0,
  "ambiguous": true,
  "runners_up": [
    {
      "service_type": "REST",
      "score": 4.5,
      "matched_mime": true,
      "matched_body_signatures": ["application/sparql-results+json"]
    }
  ],
  "final_url": "https://example.org/data",
  "had_redirect": false,
  "probed_url": "https://example.org/data?query=SELECT+%2A+WHERE+%7B%7D+LIMIT+1",
  "status_code": 200,
  "content_type": "application/json",
  "error": null,
  "note": "Ambiguous: top two candidates within 0.5 of each other"
}
```

**No match:**
```json
{
  "url": "https://example.org/unknown",
  "identified_type": null,
  "confidence": null,
  "ambiguous": false,
  "runners_up": [],
  "final_url": "https://example.org/unknown",
  "had_redirect": false,
  "probed_url": "https://example.org/unknown",
  "status_code": 200,
  "content_type": "text/html",
  "error": null,
  "note": "No candidate exceeded minimum confidence threshold of 3.0"
}
```

**Error (unreachable endpoint):**
```json
{
  "url": "https://dead.example.org/oai",
  "identified_type": null,
  "confidence": null,
  "ambiguous": false,
  "runners_up": [],
  "final_url": null,
  "had_redirect": false,
  "probed_url": null,
  "status_code": null,
  "content_type": null,
  "error": "ConnectionError: Failed to establish connection",
  "note": null
}
```

## Traceability to EOSC EDEN Interoperability Requirements

This section maps STIS requirements to upstream requirements identified in EOSC EDEN T2.1, derived from the EOSC Interoperability Framework and discipline-specific user stories.

### INTEROPERABILITY-TECHNICAL-REQ-063 (Mandatory)
*TDAs must provide a uniform and machine-readable way to declare their interfaces and capabilities, enabling automated discovery by external systems and registries.*
The STIS is the tool that enables automated, evidence-based classification of TDA interfaces and capabilities without requiring manual declaration by the TDA operator.
Addressed by: STIS-REQ-1-01 (blind identification without prior declaration), STIS-REQ-4-01 (machine-actionable structured output), STIS-REQ-4-02 (full provenance for registry population)

### INTEROPERABILITY-TECHNICAL-REQ-065 (Mandatory)
*TDAs must demonstrate compliance with open interoperability protocols (e.g., OAI-PMH, CSW, SPARQL, REST) by supporting a minimum set of standard operations.*
The STIS identifies whether an endpoint speaks a given open interoperability protocol, which is the prerequisite step for any protocol compliance assessment.
Addressed by: STIS-REQ-2-02 (coverage of OAI-PMH, OGC, SPARQL, REST, and other open protocols), STIS-REQ-1-02 (targeted protocol-specific probing), STIS-REQ-3-04 (ambiguity detection for inconclusive protocol evidence)

### INTEROPERABILITY-TECHNICAL-REQ-064 (Mandatory)
*TDAs should use widely adopted mechanisms (e.g., standardised link relations and well-known resources) to make services easily discoverable.*
The STIS complements this requirement from the consumer side: it allows automated systems to discover what protocol a TDA endpoint speaks even when standardised discovery mechanisms are absent or incomplete.
Addressed by: STIS-REQ-1-01 (blind protocol identification), STIS-REQ-2-01 (profile registry of widely-adopted protocols), STIS-REQ-5-04 (SPARQL/Fuseki batch input for knowledge-graph-based discovery pipelines)

### INTEROPERABILITY-TECHNICAL-REQ-057 (Mandatory)
*TDAs must provide clear, persistent, and accessible documentation describing their services and protocols, both in human-readable and machine-readable forms.*
The STIS produces the machine-readable service type evidence that can be used to populate or validate the protocol documentation associated with a TDA in EOSC registries and knowledge graphs.
Addressed by: STIS-REQ-4-01 (machine-actionable JSON output), STIS-REQ-4-02 (provenance fields enabling reproducible documentation), STIS-REQ-5-06 (machine-readable OpenAPI schema for the service itself)

### DISCIPLINE-SPECIFIC-REQ-024 (Mandatory)
*As a researcher that produce and consume research data, I require machine readable / API access to dataset, for efficient data management.*
Identifying the service type of an endpoint is a prerequisite for selecting the correct API access pattern (e.g., OAI-PMH `ListRecords`, SPARQL `SELECT`, OGC `GetCapabilities`).
Addressed by: STIS-REQ-1-01 (service type identification enabling correct API selection), STIS-REQ-5-01 (REST API for programmatic access), STIS-REQ-5-02 (CLI for scripted workflows)

## References

1. EOSC Interoperability Framework: Guidelines for semantic and technical interoperability in the European Open Science Cloud.
2. IETF RFC 2119: Key words for use in RFCs to Indicate Requirement Levels. <https://www.rfc-editor.org/rfc/rfc2119>
3. EOSC EDEN M1.1 – Report on Identification of Core Preservation Processes. Zenodo. <https://doi.org/10.5281/zenodo.16992452>
4. OAI-PMH Protocol Specification: Open Archives Initiative Protocol for Metadata Harvesting, v2.0. <https://www.openarchives.org/OAI/openarchivesprotocol.html>
5. OGC Web Services Standards: Open Geospatial Consortium. <https://www.ogc.org/standards/>
6. SPARQL 1.1 Protocol: W3C Recommendation. <https://www.w3.org/TR/sparql11-protocol/>
7. IVOA Standards: International Virtual Observatory Alliance. <https://www.ivoa.net/documents/>
8. FastAPI Framework: <https://fastapi.tiangolo.com/>
