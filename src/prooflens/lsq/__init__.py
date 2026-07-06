"""LeadSquared integration.

Phase 2 builds the LSQClient protocol + FakeLSQClient (all tests/local) that
writes the three custom fields back in order (band, score, reason). Phase 3 adds
RealLSQClient, stubbing the unknowns tracked in the README with marked TODOs:
  - LSQ webhook payload shape + signature scheme
  - LSQ custom-field ids for band / score / reason
  - LSQ API auth + image-fetch endpoint (if the image arrives by reference)
"""
