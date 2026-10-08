# Aubrey Moore

# 2026-05-20 11:30
# changed binary masks to contain 0 and 255 instead of 0 and 1
# "diff_mask = cv2.bitwise_and(recon_mask, cv2.bitwise_not(original_mask))" instead of "diff_mask = reconstructed_mask & ~original_mask"
# changed default ksize to (3,3)


from sim_palm import generate_palm_with_cuts
from icecream import ic
from pyefd import elliptic_fourier_descriptors, reconstruct_contour
import numpy as np
import cv2
import matplotlib.pyplot as plt
from dataclasses import dataclass
import random

@dataclass
class EFDvcuts:
    order: int
    ksize: any
    coeffs: any
    original_mask: np.array
    reconstructed_mask: np.array
    diff_mask: np.array
    clean_mask: np.array
    vcut_contours: np.array
    vcut_centroids: np.array
    vcut_xs: np.array
    vcut_ys: np.array 
    n_vcuts_detected: int


def efd_find_cuts(original_contour, original_mask, order=40, ksize=(3,3), iterations=1):
    """ 
    This function was created to detect and locate defects in binary masks 
    of coconut palms, such as v-shaped cuts caused by coconut rhinoceros beetles.
    
    Synthetic contours and masks for testing may be provided by the generate_palms_with_cuts function. 
    
    Elliptic Fourier descriptors are calculated and used to reconstruct a "smoothed version" of the original mask.
    
    Cuts are apparent in the difference between the smoothed mask and the original mask.
    
    In the final step, noise is removed using a morphological operation called opening". 
    
    Required arguments:
        original_contour    binary mask of a coconut palm; nparray of shape (N, 2) containing the pixel coordinates of the contour; dtype=int32
        original_mask       a binary mask (filled original_contour); nparray of shape (H, W) containing 0s and 255s (or 0s and 1s); dtype=uint8
        
    Arguments with defaults:
        order               an EFD parameter which determines the size of the descriptor 
        ksize               a tuple defining the size of the kernel used by the morphological operation
        iterations          number of times the morphological operation is applied to a mask
        return_plot_data    a binary flag which determines if plot_data are calculated and returned
        
    Return values:
        A dataclass containing the following attributes:
        order               the order of the EFDs used to reconstruct the contour
        ksize               the size of the kernel used by the morphological operation
        coeffs              the EFD coefficients used to reconstruct the contour
        original_mask       the original binary mask of the palm
        reconstructed_mask  the reconstructed binary mask of the palm
        diff_mask           the difference between the reconstructed and original masks
        clean_mask          the filtered difference mask, which should contain only the v-cuts      
        vcut_contours       a tuple containing contours (each contour is a numpy array of points; dtype=int32)
        vcut_centroids      a numpy array containing the centroids of the detected v-cuts
        vcut_xs             a numpy array containing the x-coordinates of the detected v-cut centroids
        vcut_ys             a numpy array containing the y-coordinates of the detected v-cut centroids
        n_vcuts_detected    the number of v-cuts detected in the original mask
    """
    # calc EFDs
    coeffs = elliptic_fourier_descriptors(original_contour, order, normalize=False)

    # reconstruct contour
    reconstructed_contour = reconstruct_contour(coeffs, num_points=original_contour.shape[0])

    # Calculate the centroid of the original to shift the reconstruction back
    # EFD reconstruction is often centered at (0,0) or uses the DC component (coeffs[0])
    centroid = np.mean(original_contour, axis=0)
    reconstructed_contour += centroid
    reconstructed_contour = reconstructed_contour.astype(np.int32)
    reconstructed_mask = cv2.fillPoly(np.zeros_like(original_mask), pts=[reconstructed_contour], color=255)

    # Calculate the difference mask
    # Pixels missing in original, present in reconstruction
    diff_mask = cv2.bitwise_and(reconstructed_mask, cv2.bitwise_not(original_mask))

    # Create clean_mask
    # Define kernel (size depends on how thick the "thin" features are)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, ksize=ksize)
    # Apply Opening
    clean_mask = cv2.morphologyEx(diff_mask, cv2.MORPH_OPEN, kernel, iterations=iterations)
    
    # get vcut contours
    vcut_contours, _ = cv2.findContours(image=clean_mask, mode=cv2.RETR_EXTERNAL, method=cv2.CHAIN_APPROX_NONE)
    ic.enable()
    
    n_vcuts_detected = len(vcut_contours)
    
    # THIS IS NOT AN ACCURATE WAY TO GET CENTROIDS - SHOULD PROBABLY USE MOMENTS OR SOMETHING SIMILAR
    if n_vcuts_detected > 0:
        data = []
        for vcut_contour in vcut_contours:
            vcut_centroid = np.mean(vcut_contour, 0).flatten()
            data.append(vcut_centroid)
        vcut_centroids = np.array(data)
        vcut_xs = vcut_centroids[:, 0]
        vcut_ys = vcut_centroids[:, 1]
    else:
        vcut_centroids = None
        vcut_xs = None
        vcut_ys = None
    return EFDvcuts(order, ksize, coeffs, original_mask, reconstructed_mask, diff_mask, clean_mask, vcut_contours, vcut_centroids, vcut_xs, vcut_ys, n_vcuts_detected)


def plot_efd_results(efd_results):
    fig, axs = plt.subplots(1, 5, figsize=(20, 5), sharex=True, sharey=True)

    axs[0].imshow(efd_results.original_mask)
    axs[0].set_title('original mask')

    axs[1].imshow(efd_results.reconstructed_mask)
    axs[1].set_title(f'EFD mask {efd_results.order} {efd_results.ksize}')

    axs[2].imshow(efd_results.diff_mask)
    axs[2].set_title('diff mask')

    axs[3].imshow(efd_results.clean_mask)
    axs[3].set_title('filtered diff mask')

    axs[4].imshow(efd_results.original_mask)
    if efd_results.n_vcuts_detected > 0:
        axs[4].plot(efd_results.vcut_xs, efd_results.vcut_ys, 'or')
    axs[4].set_title('detected v-cuts')

    fig.tight_layout()
    
    return fig, axs
    
    
if __name__ == "__main__":
    random.seed(42)
    original_contour, original_mask = generate_palm_with_cuts(1)
    ic(original_contour)
    ic(original_mask)
    
    results = efd_find_cuts(original_contour=original_contour, original_mask=original_mask)
    ic(results.n_vcuts_detected)
    ic(np.max(results.original_mask))
    ic(np.max(results.reconstructed_mask))
    ic(np.max(results.diff_mask))
    ic(np.max(results.clean_mask))
    # ic(results)
    
    my_fig, my_axs = plot_efd_results(results)
    plt.show()
