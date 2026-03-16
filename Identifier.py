"""
wp2-service-identifier — core identification engine.
"""
from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, urljoin

import requests

logger = logging.getLogger(__name__)


@dataclass
class CandidateMatch:
    service_type: str
    score: float
    matched_mime: bool
    matched_body_signatures: list[str]


@dataclass
class IdentificationResult:
    url: str
    identified_type: Optional[str] = None
    confidence: Optional[float] = None
    ambiguous: bool = False
    runners_up: list[CandidateMatch] = field(default_factory=list)
    final_url: Optional[str] = None
    had_redirect: bool = False
    probed_url: Optional[str] = None   # URL used for the winning targeted probe
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    error: Optional[str] = None
    note: Optional[str] = None


_PROFILES_PATH = os.path.join(os.path.dirname(__file__), "service_profiles.json")

# Configurable thresholds
DEFAULT_MIN_CONFIDENCE = 3.0
DEFAULT_AMBIGUITY_GAP = 1.0
DEFAULT_MAX_RUNNERS_UP = 3
DEFAULT_LOW_THRESHOLD = 1.0   # minimum score to shortlist for targeted probes
DEFAULT_MAX_THREADS = 10
DEFAULT_REQUEST_TIMEOUT = 15  # seconds per HTTP request


class ServiceIdentifier:

    # Schemes that can be identified purely from the URL scheme
    _SCHEME_SHORTCUTS = {
        "amqp": "AMQP",
        "mqtt": "MQTT",
        "xmpp": "XMPP",
    }
    # Schemes we can actually probe
    _SUPPORTED_SCHEMES = {"http", "https", "ftp"}

    def __init__(
        self,
        profiles_path: str = _PROFILES_PATH,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        ambiguity_gap: float = DEFAULT_AMBIGUITY_GAP,
        max_runners_up: int = DEFAULT_MAX_RUNNERS_UP,
        low_threshold: float = DEFAULT_LOW_THRESHOLD,
        max_threads: int = DEFAULT_MAX_THREADS,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ):
        self.min_confidence = min_confidence
        self.ambiguity_gap = ambiguity_gap
        self.max_runners_up = max_runners_up
        self.low_threshold = low_threshold
        self.max_threads = max_threads
        self.request_timeout = request_timeout

        with open(profiles_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        self.profiles: dict = raw["service_profiles"]
        self.global_config: dict = raw.get("global", {})
        self._api_doc_keywords: list[str] = self.global_config.get("api_doc_keywords", [])
        self._decommissioned_keywords: list[str] = self.global_config.get("decommissioned_keywords", [])

        # Cache spec URL index once — used for body scanning in _score_response
        self._spec_url_index: dict[str, str] = self._build_spec_url_index()

        # Reuse a single session for connection pooling across all probes
        self._session = requests.Session()

    def _build_spec_url_index(self) -> dict[str, str]:
        """Build a mapping from spec URL → profile key. Called once in __init__.
        Full implementation added in Task 6."""
        index = {}
        for key, profile in self.profiles.items():
            for entry in profile.get("spec_urls", []):
                url = entry.get("url", "").rstrip("/")
                if url:
                    index[url] = key
        return index

    def identify_url(self, url: str) -> IdentificationResult:
        raise NotImplementedError("Pipeline not yet implemented")
