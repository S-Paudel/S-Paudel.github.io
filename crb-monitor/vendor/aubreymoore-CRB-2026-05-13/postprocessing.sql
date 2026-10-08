-- flip ys in tree contours so they overlay images

UPDATE trees 
SET tree_poly = ATM_Transform(tree_poly, ATM_CreateScale(1, -1));

-- flip ys in damage contours so they overlay images
-- NO DATA IN DAMAGE TABLE !!!

UPDATE damage 
SET damage_poly = ATM_Transform(damage_poly, ATM_CreateScale(1, -1));

/**********************************************************************************
Calculates proximity of each tree polygon to the left, right an top edge the image.
Proximity is expressed as a proportion of image width or image height.

trees.tree_touches_edge is set to 1 if proximity is less that a specified threshold
or 0 otherwise.

It is assumed tree.poly is scaled with x ranging from 0 to page_width with 0 at the
left of the image and y ranging from 0 to -page_height with 0 at the top of the 
image.
*/

CREATE TEMP TABLE temp_touches AS 
SELECT 
  trees.image_id, 
  tree_id,
  MbrMinX(tree_poly)/image_width AS left_proximity,
  1 - MbrMaxX(tree_poly)/image_width AS right_proximity,
  - MbrMaxY(tree_poly)/image_height AS top_proximity
FROM trees, images
WHERE trees.image_id=images.image_id;

UPDATE trees
SET tree_touches_edge = left_proximity<0.01 OR right_proximity<0.01 OR top_proximity<0.01
FROM temp_touches
WHERE trees.tree_id = temp_touches.tree_id;
