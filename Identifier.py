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
