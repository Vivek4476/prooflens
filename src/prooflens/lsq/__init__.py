"""LeadSquared integration.

Phase 2 ships the LSQClient protocol + FakeLSQClient (all tests/local), writing
the three custom fields back in order (band, score, reason). Phase 3 adds
RealLSQClient, stubbing the unknowns tracked in the README with marked TODOs:
  - LSQ webhook payload shape + signature scheme
  - LSQ custom-field ids for band / score / reason
  - LSQ API auth + image-fetch endpoint (if the image arrives by reference)
"""

from .base import FieldUpdate, LSQClient
from .fake import BAD_FETCH_MARKER, FakeLSQClient

__all__ = ["LSQClient", "FieldUpdate", "FakeLSQClient", "BAD_FETCH_MARKER"]
