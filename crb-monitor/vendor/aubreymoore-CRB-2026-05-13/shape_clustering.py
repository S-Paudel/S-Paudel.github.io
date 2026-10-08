import cv2
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

class ShapeClustering:
    def __init__(self, method=cv2.CONTOURS_MATCH_I1):
        """
        Initializes the unsupervised shape clustering tool.
        """
        self.method = method
        self.distance_matrix = None
        self.optimal_labels = None
        self.n_clusters_opt = None

    def _compute_distance_matrix(self, contours):
        """
        Computes a square pairwise distance matrix using cv2.matchShapes.
        """
        n = len(contours)
        # Create an empty NxN matrix
        dist_matrix = np.zeros((n, n))
        
        # Fill the matrix symmetrically
        for i in range(n):
            for j in range(i, n):
                if i == j:
                    dist_matrix[i][j] = 0.0
                else:
                    # Match score where 0 is identical
                    score = cv2.matchShapes(contours[i], contours[j], self.method, 0.0)
                    dist_matrix[i][j] = score
                    dist_matrix[j][i] = score # Symmetric matrix
                    
        return dist_matrix

    def fit_predict(self, contours, min_clusters=2, max_clusters=10):
        """
        Builds a distance matrix, optimizes cluster count via Silhouette Score,
        and returns the cluster IDs for every shape.
        """
        n_samples = len(contours)
        if n_samples < 3:
            raise ValueError("You need at least 3 contours to run optimized clustering.")
            
        # Constrain max_clusters to prevent crashing if dataset is small
        max_clusters = min(max_clusters, n_samples - 1)
        
        # Step 1: Generate custom shape distance matrix
        print("Calculating pairwise shape distances...")
        self.distance_matrix = self._compute_distance_matrix(contours)
        
        best_score = -1
        best_labels = None
        best_k = min_clusters
        
        # Step 2: Search for the ideal number of clusters (K)
        print("Optimizing cluster count...")
        for k in range(min_clusters, max_clusters + 1):
            # We use 'precomputed' affinity because we supply the distance matrix directly
            clusterer = AgglomerativeClustering(
                n_clusters=k, 
                metric='precomputed', 
                linkage='average'
            )
            labels = clusterer.fit_predict(self.distance_matrix)
            
            # Evaluate how well-separated the shape groups are
            # Metric handles the precomputed distance layout cleanly
            score = silhouette_score(self.distance_matrix, labels, metric='precomputed')
            print(f" - Testing {k} clusters | Silhouette Score: {score:.4f}")
            
            if score > best_score:
                best_score = score
                best_labels = labels
                best_k = k
                
        self.optimal_labels = best_labels
        self.n_clusters_opt = best_k
        
        print(f"\nOptimization Complete! Ideal cluster count: {self.n_clusters_opt}")
        return self.optimal_labels