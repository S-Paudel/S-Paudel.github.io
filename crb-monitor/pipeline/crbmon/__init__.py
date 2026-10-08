"""CRB Damage Monitor pipeline.

Finds public palm photos (iNaturalist, GBIF, Mapillary, Flickr, pasted links),
pre-filters them cheaply, and runs Aubrey Moore's SAM3 + elliptic-Fourier
V-cut detector on the survivors. Only links and analysis results are stored.
"""

__version__ = "1.0.0"
