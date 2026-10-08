# Aubrey Moore
# 2026-05-20 11:57
# changed mask to contain 0 and 255 instead of 0 and 1

import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
import cv2
import math
import random

def get_frond_polygons(y_offset=100):
    """Generates the geometry for each frond."""
    canopy_center = (400, 250 + y_offset)
    frond_length = 280
    
    central_angle = [-90]
    right_angles = [-65, -40, -15, 10, 35] 
    left_angles = [-180 - angle for angle in right_angles]
    all_angles = central_angle + right_angles + left_angles

    frond_data = []

    for angle_deg in all_angles:
        angle_rad = math.radians(angle_deg)
        num_segments = 24
        segment_len = frond_length / num_segments
        
        cos_val = math.cos(angle_rad)
        gravity_dir = 0 if abs(cos_val) < 0.01 else (1 if cos_val >= 0 else -1)
        
        spine = []
        curr_x, curr_y = canopy_center
        gravity_accum = 0.0
        
        for i in range(num_segments + 1):
            spine.append((curr_x, curr_y))
            current_angle = angle_rad + gravity_accum
            curr_x += segment_len * math.cos(current_angle)
            curr_y += segment_len * math.sin(current_angle)
            gravity_step = 0.07 if gravity_dir != 0 else 0.005
            gravity_accum += gravity_step * gravity_dir
            
        left_edge, right_edge = [], []
        max_frond_width = 20
        
        for i in range(len(spine) - 1):
            p1, p2 = spine[i], spine[i+1]
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            mag = math.hypot(dx, dy)
            if mag > 0:
                nx, ny = -dy / mag, dx / mag
                w = max_frond_width * math.sin(math.pi * (i / num_segments))
                left_edge.append((int(p1[0] + nx * w), int(p1[1] + ny * w)))
                right_edge.append((int(p1[0] - nx * w), int(p1[1] - ny * w)))
                
        tip = (int(spine[-1][0]), int(spine[-1][1]))
        frond_data.append({
            'poly': np.array(left_edge + [tip] + right_edge[::-1], dtype=np.int32),
            'spine': spine,
            'left_edge': left_edge,
            'right_edge': right_edge
        })
    return frond_data

def get_random_notch(frond):
    """Calculates a single triangular cut for a specific frond."""
    side = random.randint(0, 1)
    edge = frond['left_edge'] if side == 0 else frond['right_edge']
    spine = frond['spine']
    
    idx = random.randint(4, len(edge) - 6)
    p1, p2 = edge[idx], edge[idx + 2]
    depth_p = (int(spine[idx+1][0]), int(spine[idx+1][1]))
    
    def extend(center, edge_pt, scale=2.0):
        return (int(center[0] + (edge_pt[0] - center[0]) * scale), 
                int(center[1] + (edge_pt[1] - center[1]) * scale))
        
    return np.array([extend(depth_p, p1), depth_p, extend(depth_p, p2)], dtype=np.int32)

def generate_palm_with_cuts(num_cuts:int) -> npt.ArrayLike:
    """
    Generates a binary mask of a palm with a specified number of v-shaped cuts.
    The cuts are made on fronds at random positions.
    When there are 2 or more cuts, the mask may be broken into several parts from cuts which sever fronds.
    Data are returned for the contour and mask with the largest area.
    
    For reproducibility, set a seed before executing this function Example: random.seed(42)
    
    Parameters:
        num_cuts: a positive integer [0 ... n] specifying the number of cuts to apply to the mask
    
    Return values:
        contour: a closed polygon surrounding the mask (use for analysis)
        mask:    a binary mask; uint8 of size (800, 800) containing 0s and 255s
        
    Usage example:
        contour, mask = generate_palm_with_cuts(10)
        plt.imshow(mask, cmap='gray');
    """
    width, height = 800, 800
    main_mask = np.zeros((height, width), dtype=np.uint8)
    y_offset = 150 # Lowered slightly more for headroom

    # 1. Draw Trunk
    trunk_pts = np.array([[385, 800], [415, 800], [408, 250 + y_offset], [392, 250 + y_offset]], dtype=np.int32)
    cv2.fillPoly(main_mask, [trunk_pts], 255)

    # 2. Prepare Fronds
    fronds = get_frond_polygons(y_offset)
    
    # Assign cuts to random fronds
    cut_assignments = [random.randint(0, len(fronds) - 1) for _ in range(num_cuts)]

    # 3. Process each frond
    for i, frond in enumerate(fronds):
        # Create a layer for this specific frond
        frond_layer = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(frond_layer, [frond['poly']], 255)
        
        # Apply any cuts assigned to this frond index
        frond_cuts = [c for c in cut_assignments if c == i]
        for _ in frond_cuts:
            notch = get_random_notch(frond)
            cv2.fillPoly(frond_layer, [notch], 0)
            
        # Merge this frond into the main mask
        main_mask = cv2.bitwise_or(main_mask, frond_layer)
        
    # 4. At this point, main_mask may have been broken into several parts from cuts which sever fronds.
    # As a final step, we find contours and return the one with the largest area.
    
    # Use cv2.CHAIN_APPROX_NONE to get all contour points (highest resolution)
    contours, _ = cv2.findContours(main_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        
    # Get the largest contour to make a new mask
    contour = max(contours, key=cv2.contourArea).reshape(-1, 2)
    
    # If the first point does not match the last point, append the first point
    if not np.array_equal(contour[0], contour[-1]):
        contour = np.vstack([contour, contour[0]])
        # print('Point added to close contour.')
        
    # Create a new mask    
    mask = cv2.fillPoly(
        img=np.zeros_like(main_mask),
        pts=[contour],
        color=255
    )
    
    return contour, mask


def test_generate_palm_with_cuts():
    # cuts = [0, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]
    cuts = [1,2,4]
    fig, axs = plt.subplots(3, 4, figsize=(12,8))
    for ax, num_cuts in zip(axs.flatten(), cuts):
        _, mask = generate_palm_with_cuts(num_cuts)
        ax.imshow(mask, cmap='gray')
        ax.set_axis_off()
        ax.set_title(f"{num_cuts} cuts")
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    random.seed(42)
    test_generate_palm_with_cuts()