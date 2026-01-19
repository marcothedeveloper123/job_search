"""Web research extractors for token-efficient data extraction."""

from scripts.research.base import BaseExtractor
from scripts.research.crunchbase import CrunchbaseExtractor
from scripts.research.g2 import G2Extractor
from scripts.research.glassdoor import GlassdoorExtractor
from scripts.research.linkedin import LinkedInExtractor

EXTRACTORS = {
    "glassdoor": GlassdoorExtractor,
    "crunchbase": CrunchbaseExtractor,
    "g2": G2Extractor,
    "linkedin": LinkedInExtractor,
}

__all__ = [
    "BaseExtractor",
    "GlassdoorExtractor",
    "CrunchbaseExtractor",
    "G2Extractor",
    "LinkedInExtractor",
    "EXTRACTORS",
]
