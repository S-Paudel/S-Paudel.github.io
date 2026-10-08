SELECT image_path, confidence
FROM images, trees
WHERE images.image_id=trees.image_id
  AND images.image_id = :image_id;