"""
wp2-service-identifier — FastAPI web service.

Run with:
    uvicorn main:app --reload --port 8001
    python main.py
"""
import dataclasses
import logging

from fastapi import FastAPI, Query

from Identifier import ServiceIdentifier

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="WP2 Service Identifier",
    description="Identify the service type of an unknown EOSC EDEN endpoint.",
    version="1.0.0",
)


@app.get("/identify")
def identify(
    url: str = Query(..., description="Endpoint URL to identify"),
    min_confidence: float = Query(3.0, description="Minimum confidence to report a match"),
    ambiguity_gap: float = Query(1.0, description="Score gap below which result is flagged ambiguous"),
    max_runners_up: int = Query(3, description="Max runner-up candidates to return"),
) -> dict:
    identifier = ServiceIdentifier(
        min_confidence=min_confidence,
        ambiguity_gap=ambiguity_gap,
        max_runners_up=max_runners_up,
    )
    result = identifier.identify_url(url)
    return dataclasses.asdict(result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
