import numpy as np
from sklearn.semi_supervised import LabelSpreading

# 1. Define your real target data (Class 0)
X_target = np.array([
    [0.1, 0.2],
    [0.2, 0.1],
    [0.15, 0.2]
])

# 2. Automatically generate synthetic background points (Class 1)
# Create a wider bounding box around your target data
min_bounds = X_target.min(axis=0) - 5.0
max_bounds = X_target.max(axis=0) + 5.0

# Generate random points inside this bounding box
np.random.seed(42)
random_points = np.random.uniform(low=min_bounds, high=max_bounds, size=(20, 2))

# Filter out random points that accidentally fell inside your real target cluster
distances = np.linalg.norm(random_points[:, None, :] - X_target[None, :, :], axis=-1)
min_distances_to_target = distances.min(axis=1)
X_synthetic = random_points[min_distances_to_target > 2.0]  # Safe distance threshold

# 3. Define the unlabeled test points you actually want to evaluate
X_unlabeled = np.array([
    [0.12, 0.18], # Close to target cluster
    [4.5, 4.8]    # Far away from target cluster
])

# 4. Combine datasets and assign labels
# Class 0 = Target, Class 1 = Synthetic Outliers, -1 = Unlabeled
X = np.vstack([X_target, X_synthetic, X_unlabeled])
y = np.array([0] * len(X_target) + [1] * len(X_synthetic) + [-1] * len(X_unlabeled))

# 5. Fit the model
model = LabelSpreading(kernel='rbf', gamma=0.5)
model.fit(X, y)

# 6. Extract the final predictions for just your unlabeled points
unlabeled_predictions = model.transduction_[-len(X_unlabeled):]
unlabeled_probabilities = model.label_distributions_[-len(X_unlabeled):]

print("Unlabeled Probabilities [Class 0, Class 1]:\n", unlabeled_probabilities)
print("\nAssigned Labels (-1 converted to either 0 or 1):\n", unlabeled_predictions)
