"""ProofLens — async image-authenticity scoring for proof-of-visit photos.

Modular monolith: a pure scoring engine (prooflens.engine) wrapped by a
service (api + worker + queue + db) and pluggable vision backends. It SCORES
AND FLAGS; it never blocks an upload and never stores images.
"""

__version__ = "0.1.0"
