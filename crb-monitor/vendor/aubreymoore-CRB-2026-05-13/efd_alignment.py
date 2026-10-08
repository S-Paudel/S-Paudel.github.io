# Reference: https://gemini.google.com/share/f6b384e7f28b

import cv2
import numpy as np
from pyefd import elliptic_fourier_descriptors, reconstruct_contour

def reconstruct_aligned_mask(image_shape, contour, order=10):
    """
    Finds EFDs and reconstructs the mask perfectly aligned with the original locus.
    
    Parameters:
        image_shape (tuple): Shape of the original image (H, W)
        contour (ndarray): Contour array of shape (N, 2) or (N, 1, 2)
        order (int): Number of Fourier coefficients to use
        
    Returns:
        ndarray: Binary mask with the reconstructed shape in the correct position
    """
    # 1. Standardize contour shape to (N, 2)
    contour = contour.reshape(-1, 2)
    
    # 2. Calculate the true centroid (locus) of the original contour using moments.
    # This keeps the reconstructed shape strictly bound to the true defect location.
    M = cv2.moments(contour)
    if M["m00"] != 0:
        cX = M["m10"] / M["m00"]
        cY = M["m01"] / M["m00"]
    else:
        cX, cY = np.mean(contour, axis=0)

    # 3. Compute EFD coefficients (keeping unnormalized to retain spatial properties)
    coeffs = elliptic_fourier_descriptors(contour, order=order, normalize=False)
    
    # 4. Corrected function: Reconstruct contour points via the native API.
    # We pass the calculated cX, cY into the locus argument.
    reconstructed_points = reconstruct_contour(coeffs, locus=(cX, cY), num_points=200)
    
    # 5. Prevent sub-pixel "floor bias" shift by rounding before converting to integer
    reconstructed_contour = np.round(reconstructed_points).astype(np.int32)
    reconstructed_contour = reconstructed_contour.reshape(-1, 1, 2)
    
    # 6. Create the aligned mask
    mask = np.zeros(image_shape, dtype=np.uint8)
    cv2.drawContours(mask, [reconstructed_contour], -1, 255, -1)
    
    return mask

# --- Verification Example ---
if __name__ == "__main__":
    # Create a dummy mask with a mock "defect"
    img = np.zeros((200, 200), dtype=np.uint8)
    cv2.rectangle(img, (50, 60), (130, 140), 255, -1)
    
    # Extract the original defect contour
    contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    orig_contour = contours[0]
    
    # Get the perfectly aligned reconstructed mask
    aligned_mask = reconstruct_aligned_mask(img.shape, orig_contour, order=5)
    
    # Verify alignment
    print(f"Original mask pixels: {np.sum(img == 255)}")
    print(f"Reconstructed mask pixels: {np.sum(aligned_mask == 255)}")