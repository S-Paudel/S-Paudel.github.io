# README.md

## realworld2.ipynb
- Current workflow?

## unsupervised_contour_clustering_HDBSCAN.ipynb
- classifies trees using Hu moments

## reassign_noise_points.py
- needs to be integrated with unsupervised_contour_clustering_HDBSCAN.ipynb?
- seems to be unnecessary

## view_tree_shape_classes.ipynb
- creates a directory tree containing images of filled tree shape contours
- probably best to turn this into a function

## Technical notes

### Gemini references

- [Please write python code for a binary classifier for shapes "of interest" and "not of interest". I have already created a training set of contours for each shape class. I want my classifier to be based on cv2.matchShapes](https://gemini.google.com/share/1f8d2d3aa787)
- [Use python cv2 to get high precision contours from a binary mask](https://share.google/aimode/JFWQPUJs6pchjI70H)
- [EFD defect detection](https://share.google/aimode/s0U9B17vVAgGjX3SL)
- [Check for object and create it if it does not exist](https://gemini.google.com/share/7ef3a3c85591)
- [plot random contours](https://gemini.google.com/share/ac1b384d3367)
- [shape matching with Hu invariants an DBSCAN](https://gemini.google.com/share/0c1ff1f9b9f3)
- [building a classier using DBSCAN where only one of several classes is labelled](https://gemini.google.com/share/8cc3494eb7c2)
- [LabelSpreading with only one labelled class](https://share.google/aimode/EbRDOCV4Xy6H62pdL)
- [Handling WKT polygons stored in SpatiaLite](https://share.gemini.google/GsXlsrXlZSvi)

### YouYube references

- [Semisupervised learning](https://youtu.be/MM1OCCdE3DQ?si=ty_ZdtFFPdxKmSWZ)
