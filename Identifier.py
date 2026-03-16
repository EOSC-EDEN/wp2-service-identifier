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
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()

        # Stage 1 — scheme shortcuts (no HTTP probing needed)
        if scheme in self._SCHEME_SHORTCUTS:
            stype = self._SCHEME_SHORTCUTS[scheme]
            return IdentificationResult(url=url, identified_type=stype, confidence=10.0)

        if scheme == "ftp":
            return self._identify_ftp(url)

        if scheme not in self._SUPPORTED_SCHEMES:
            return IdentificationResult(url=url, error="unsupported_scheme",
                                        note=f"Scheme '{scheme}' cannot be probed")

        candidates = self._prefilter_by_url_pattern(url)

        # Stage 2 — initial probe
        initial_response = self._probe(url, suffix=None)
        if initial_response is None:
            return IdentificationResult(url=url, error="unreachable",
                                        note="Could not connect to endpoint")

        # Stages 3-5 not yet implemented
        raise NotImplementedError("Stages 3-5 not yet implemented")

    def _prefilter_by_url_pattern(self, url: str) -> list[str]:
        """Return list of profile keys to probe. Returns all supported profiles.

        This is the extension point for future URL-pattern-based narrowing.
        Profiles marked 'unsupported' (AMQP stub, MQTT stub, etc.) are excluded.
        """
        return [
            key for key, profile in self.profiles.items()
            if not profile.get("special", {}).get("unsupported", False)
        ]

    def _probe(self, url: str, suffix: Optional[str], method: str = "GET") -> Optional[requests.Response]:
        """Fire a single HTTP request using the shared session. Returns Response or None on error."""
        target = url + suffix if suffix else url
        try:
            if method.upper() == "POST":
                resp = self._session.post(target, timeout=self.request_timeout, allow_redirects=True)
            else:
                resp = self._session.get(target, timeout=self.request_timeout, allow_redirects=True)
            return resp
        except requests.exceptions.RequestException as e:
            logger.warning("Probe failed for %s: %s", target, e)
            return None
        except Exception as e:
            logger.warning("Unexpected error probing %s: %s", target, e)
            return None

    def _score_response(
        self, response: requests.Response, profile_key: str
    ) -> tuple[float, bool, list[str]]:
        """Score a response against a single profile.

        Returns (score, matched_mime, matched_signature_patterns).
        Score formula (max 10 pts):
          3 pts — HTTP status 2xx/3xx
          2 pts — Content-Type matches profile's expected MIME
          3 pts — Body signatures matched (partial credit: hits/total × 3)
          2 pts — Spec URL found in body resolves to this profile
        """
        profile = self.profiles.get(profile_key, {})
        if not profile:
            return 0.0, False, []

        score = 0.0
        matched_sigs: list[str] = []

        # 3 pts — HTTP status 2xx/3xx
        if 200 <= response.status_code < 400:
            score += 3.0

        # 2 pts — MIME type match
        probe_cfg = profile.get("probe", {})
        expected_mime_raw: str = probe_cfg.get("accept", "")
        response_ct: str = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        expected_mimes = [m.strip().lower() for m in expected_mime_raw.split(",") if m.strip()]
        matched_mime = bool(expected_mimes and response_ct in expected_mimes)
        if matched_mime:
            score += 2.0

        # 3 pts — body signatures (partial credit)
        body_text = response.text[:50000] if response.text else ""
        body_lower = body_text.lower()
        validation_cfg = profile.get("validation", {})
        body_sigs = validation_cfg.get("body_signatures", [])
        if body_sigs:
            hits = 0
            for sig in body_sigs:
                pattern = sig.get("pattern", "")
                mode = sig.get("mode", "substring")
                if mode == "regex":
                    if re.search(pattern, body_text, re.IGNORECASE):
                        hits += 1
                        matched_sigs.append(pattern)
                else:
                    if pattern.lower() in body_lower:
                        hits += 1
                        matched_sigs.append(pattern)
            score += (hits / len(body_sigs)) * 3.0

        # 2 pts — spec URL in body resolves to this profile
        for spec_url, resolved_key in self._spec_url_index.items():
            if spec_url.lower() in body_lower:
                if resolved_key == profile_key:
                    score += 2.0
                    break

        return round(min(score, 10.0), 2), matched_mime, matched_sigs

    def _score_against_candidates(
        self, response: requests.Response, candidates: list[str]
    ) -> list[tuple[str, float, bool, list[str]]]:
        """Score initial response against all candidate profiles.

        Returns list of (profile_key, score, matched_mime, matched_sigs) sorted descending,
        filtered to scores >= low_threshold.
        """
        results = []
        for key in candidates:
            score, matched_mime, matched_sigs = self._score_response(response, key)
            if score >= self.low_threshold:
                results.append((key, score, matched_mime, matched_sigs))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _identify_ftp(self, url: str) -> IdentificationResult:
        """Identify FTP endpoints using ftplib anonymous login."""
        import ftplib
        parsed = urlparse(url)
        try:
            ftp = ftplib.FTP(timeout=self.request_timeout)
            ftp.connect(parsed.hostname, parsed.port or 21)
            ftp.login()
            ftp.quit()
            return IdentificationResult(url=url, identified_type="FTP", confidence=10.0,
                                        status_code=226)
        except ftplib.all_errors as e:
            return IdentificationResult(url=url, identified_type=None,
                                        error="ftp_error", note=str(e))
