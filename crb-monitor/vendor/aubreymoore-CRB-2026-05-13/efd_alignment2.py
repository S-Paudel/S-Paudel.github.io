# Referesnce: https://share.google/aimode/MlKy7RnLpEmYV4ikh

# 2026-08-12 Turned visualization into a function to prevent creating plots when importing

import numpy as np
import numpy.typing as npt 

import cv2
from cv2.typing import MatLike

import matplotlib.pyplot as plt
from pyefd import elliptic_fourier_descriptors, reconstruct_contour, calculate_dc_coefficients

from icecream import ic

def align_contours(original, reconstructed):
    """
    Finds the optimal spatial translation, scale, rotation, and phase shift
    (starting point index) to match the reconstructed contour to the original.
    """
    orig_centroid = np.mean(original, axis=0)
    recon_centroid = np.mean(reconstructed, axis=0)
    
    orig_centered = original - orig_centroid
    recon_centered = reconstructed - recon_centroid
    
    orig_scale = np.sqrt(np.sum(orig_centered**2) / len(original))
    recon_scale = np.sqrt(np.sum(recon_centered**2) / len(reconstructed))
    
    orig_scaled = orig_centered / orig_scale
    recon_scaled = recon_centered / recon_scale
    
    best_recon_transformed = None
    min_distance = float('inf')
    n_points = len(original)
    
    for shift in range(n_points):
        shifted_recon = np.roll(recon_scaled, shift, axis=0)
        
        H = orig_scaled.T @ shifted_recon
        U, S, Vt = np.linalg.svd(H)
        R = Vt.T @ U.T
        
        if np.linalg.det(R) < 0:
            Vt[-1, :] *= -1
            R = Vt.T @ U.T
            
        transformed_recon = shifted_recon @ R
        distance = np.sum((orig_scaled - transformed_recon)**2)
        
        if distance < min_distance:
            min_distance = distance
            best_recon_transformed = (transformed_recon * orig_scale) + orig_centroid
            
    return best_recon_transformed


def pipeline_pyefd_alignment(original_contour: npt.NDArray[np.float64], num_harmonics: int=5):
    """
    Extracts EFD coefficients using pyefd, reconstructs the shape,
    and returns both the raw reconstruction and the aligned reconstruction.
    """   
    
    orig_contour = np.array(original_contour, dtype=np.float64).reshape(-1, 2)
    
    # 1. Extract descriptors (keep normalize=False to retain native spatial details)
    coeffs = elliptic_fourier_descriptors(orig_contour, order=num_harmonics, normalize=False)
    
    # 2. Extract DC spatial tracking offsets
    dc_coeffs = calculate_dc_coefficients(orig_contour)
    
    # 3. Generate raw reconstruction (matching original row length for point parity)
    raw_reconstruction = reconstruct_contour(
        coeffs, 
        locus=dc_coeffs, 
        num_points=len(orig_contour)
    )
    
    # 4. Perform the Procrustes phase alignment loop
    aligned_reconstruction = align_contours(orig_contour, raw_reconstruction)
    
    return raw_reconstruction, aligned_reconstruction


def alignment_visualization():
    """  
    
    """
    # =====================================================================
    # EXAMPLE DATA GENERATION
    # =====================================================================
    # Generate a mathematical asymmetric flower shape to act as original contour
    t = np.linspace(0, 2 * np.pi, 120, endpoint=False)
    # Radial equation for an asymmetric, multi-lobed structure
    r = 100 + 40 * np.sin(3 * t) + 15 * np.cos(5 * t)
    x_orig = r * np.cos(t) + 300  # Shifted to image space (300, 400)
    y_orig = r * np.sin(t) + 400
    original_data = np.column_stack((x_orig, y_orig))

    # Execute the pipeline with a low harmonic order (5) to clearly see 
    # how EFD smoothing behaves while maintaining perfect alignment geometry.
    raw_recon, aligned_recon = pipeline_pyefd_alignment(original_data, num_harmonics=5)


    # =====================================================================
    # PYPLOT VISUALIZATION
    # =====================================================================
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Subplot 1: Raw pyefd Reconstruction vs Original
    # Shows the orientation/phase issues that happen without alignment
    axes[0].plot(original_data[:, 0], original_data[:, 1], 'g-', label='Original Contour', linewidth=2.5)
    axes[0].plot(raw_recon[:, 0], raw_recon[:, 1], 'r--', label='Raw pyefd Reconstruction', linewidth=2)
    # Highlight starting points to show index mismatch/phase drift
    axes[0].scatter(original_data[0, 0], original_data[0, 1], color='green', s=100, zorder=5, label='Original Start Pt')
    axes[0].scatter(raw_recon[0, 0], raw_recon[0, 1], color='red', s=100, zorder=5, label='Raw Recon Start Pt')
    axes[0].set_title("Before Phase/Procrustes Alignment\n(Notice rotation & shifted starting indices)", fontsize=11)
    axes[0].grid(True, linestyle=':', alpha=0.6)
    axes[0].legend(loc='upper right')
    axes[0].set_aspect('equal')

    # Subplot 2: Aligned Reconstruction vs Original
    # Shows the result of the optimized alignment algorithm
    axes[1].plot(original_data[:, 0], original_data[:, 1], 'g-', label='Original Contour', linewidth=2.5)
    axes[1].plot(aligned_recon[:, 0], aligned_recon[:, 1], 'b-', label='Aligned Reconstruction', linewidth=2)
    # Highlight starting points showing they are now perfectly mapped
    axes[1].scatter(original_data[0, 0], original_data[0, 1], color='green', s=100, zorder=5)
    axes[1].scatter(aligned_recon[0, 0], aligned_recon[0, 1], color='blue', s=100, zorder=5, label='Aligned Start Pt')
    axes[1].set_title("After Phase/Procrustes Alignment\n(Perfect spatial and rotational overlay)", fontsize=11)
    axes[1].grid(True, linestyle=':', alpha=0.6)
    axes[1].legend(loc='upper right')
    axes[1].set_aspect('equal')

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    alignment_visualization()
