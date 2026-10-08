import cv2
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
from icecream import ic

def extract_invariant_features(contour):
    """ Extracts log-transformed Hu Moments from an OpenCV contour. """
    moments = cv2.moments(contour)
    hu_moments = cv2.HuMoments(moments).flatten()
    
    log_hu = []
    for m in hu_moments:
        if m != 0:
            log_hu.append(-1.0 * np.sign(m) * np.log10(np.abs(m)))
        else:
            log_hu.append(0.0)
            
    return np.array(log_hu)

def generate_mock_shapes():
    """
    Generates synthetic contours and packages them into a dictionary format
    with a unique tracking identifier (0, 1, 2, ...).
    """
    shapes_dataset = []
    contour_id = 0
    np.random.seed(42)
    
    square = np.array([[-20,-20], [20,-20], [20,20], [-20,20]], dtype=np.int32)
    triangle = np.array([[0,-25], [22,15], [-22,15]], dtype=np.int32)
    
    for _ in range(20):
        scale = np.random.uniform(0.5, 2.5)
        angle = np.random.uniform(0, 2 * np.pi)
        tx, ty = np.random.randint(100, 400, size=2)
        rot_mat = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        
        for base_shape in [square, triangle]:
            transformed = (base_shape * scale) @ rot_mat.T + [tx, ty]
            contour = transformed.astype(np.int32).reshape(-1, 1, 2)
            
            # Package with tracking identifier
            shapes_dataset.append({
                'id': contour_id,
                'contour': contour
            })
            contour_id += 1
            
        # Circle approximation
        cx, cy = np.random.randint(100, 400, size=2)
        r = int(20 * scale)
        blank = np.zeros((500, 500), dtype=np.uint8)
        cv2.circle(blank, (cx, cy), r, 255, -1)
        cnts, _ = cv2.findContours(blank, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            shapes_dataset.append({
                'id': contour_id,
                'contour': cnts[0]
            })
            contour_id += 1
            
    return shapes_dataset

# --- Main Pipeline ---

# 1. Load data structured with IDs
# Replace this with your own loop processing real images to build the dataset array!
shapes_dataset = generate_mock_shapes()
ic(shapes_dataset[0])  # Example of the data structure with 'id' and 'contour'

# 2. Extract features using the contour key
features = np.array([extract_invariant_features(item['contour']) for item in shapes_dataset])

# 3. Standardize features
scaler = StandardScaler()
scaled_features = scaler.fit_transform(features)

# 4. Run Unsupervised Clustering
dbscan = DBSCAN(eps=0.5, min_samples=3)
cluster_labels = dbscan.fit_predict(scaled_features)

# Attach results back to the master dictionary pipeline
for idx, label in enumerate(cluster_labels):
    shapes_dataset[idx]['cluster'] = label

unique_labels = set(cluster_labels)
n_clusters = len(unique_labels) - (1 if -1 in cluster_labels else 0)
print(f"Clustering complete. Found {n_clusters} core shape groups.")

# 5. Visual Inspection showing the tracking ID
plt.figure(figsize=(14, 2.5 * len(unique_labels)))

for row_idx, label in enumerate(sorted(unique_labels)):
    # Filter dataset objects belonging to the current cluster
    cluster_items = [item for item in shapes_dataset if item['cluster'] == label]
    title_text = f"Group {label}" if label != -1 else "Noise Group"
    
    # Display the first 5 shapes of this cluster group
    for col_idx, item in enumerate(cluster_items[:5]):
        plt.subplot(len(unique_labels), 5, row_idx * 5 + col_idx + 1)
        
        canvas = np.zeros((100, 100), dtype=np.uint8)
        cnt = item['contour'].copy()
        
        # Center the contour for clear visualization thumbnail
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            cnt = cnt - [cx, cy] + [50, 50]
            
        cv2.drawContours(canvas, [cnt], -1, 255, 2)
        plt.imshow(canvas, cmap='gray')
        plt.axis('off')
        
        # Title each thumbnail with its permanent tracking identifier
        plt.title(f"ID: {item['id']}", fontsize=9, color='blue')
        
        if col_idx == 0:
            # Group row flag labels
            plt.text(-25, 50, title_text, fontsize=11, weight='bold', 
                     ha='right', va='center', rotation=0)

plt.tight_layout()
plt.show()