-- tree_class_lookup.sql
UPDATE trees
SET tree_class = (
  SELECT tree_class 
  FROM cluster2class
  WHERE trees.soft_tree_class = cluster2class.soft_tree_class
)