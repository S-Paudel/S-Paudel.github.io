--- get_damage_polygons_for_tree_id.sql

SELECT damage_poly, damage_id 
FROM trees, damage 
WHERE 
trees.tree_id = damage.tree_id
AND trees.tree_id = 4
AND damage_poly IS NOT NULL 
AND trees.confidence>0.4 AND tree_touches_edge=0 AND trees.pixel_count > 400