import sys
sys.path.insert(1, '/home/aubrey/crbdd/src') # directory containing roadside.py
import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True" # prevents running out of GPU memory
import logging
import sqlite3
import cv2
import exif
import numpy as np
from icecream import ic
from roadside import run_sam3_semantic_predictor
from amutils import dict_from_toml, setup_logging
from tree_shape_tools import run_tree_shape_classifier_pipeline, classify_tree_shapes
from np2sqlite import array2blob, blob2array

import pandas as pd


def already_in_db(db_path: str, table_name: str, column_name: str, search_value) -> bool:
    """
    Returns True if search_value is in column_name table_name in db_path. False otherwise.
    """
    # Prevent SQL injection by verifying table and column names are alphanumeric/underscores
    if not (table_name.replace('_', '').isalnum() and column_name.replace('_', '').isalnum()):
        raise ValueError("Invalid table or column name format.")
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if the table is completely empty
        cursor.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
        if cursor.fetchone() is None:
            return False  # Table is empty
            
        # Check if the specific value exists in the target column
        cursor.execute(f"SELECT 1 FROM {table_name} WHERE {column_name} = ? LIMIT 1", (search_value,))
        search_value_found = cursor.fetchone() is not None
        return search_value_found  # True id search vaue was found; False otherwise
   
    finally:
        cursor.close()
        conn.close()


# def already_in_db(conn, image_path):
#     cursor = conn.cursor()
#     cursor.execute(f"SELECT 1 FROM trees WHERE image_path = '{image_path}'")
#     return cursor.fetchone()[0]

######################################

def add_image_to_db(conn, image_path, results_cpu):
    """Add image metadata and EXIF location data to the database."""
    image_height = results_cpu[0].orig_shape[0]
    image_width = results_cpu[0].orig_shape[1]
    image_cursor = conn.execute(
        "INSERT INTO images (image_path, image_width, image_height) VALUES (?, ?, ?)", 
        (image_path, image_width, image_height)
    )
    image_id = image_cursor.lastrowid
    conn.commit()
    
    with open(image_path, 'rb') as f:
        imgx = exif.Image(f)
        if imgx.has_exif:
            # timestamp
            timestamp = imgx.datetime
                
            # latitude
            d, m, s = imgx.gps_latitude
            latitude = d + m/60 + s/3600   
            if imgx.gps_latitude_ref == 'S':
                latitude = -latitude              

            # longitude
            d, m, s = imgx.gps_longitude
            longitude = d + m/60 + s/3600   
            if imgx.gps_longitude_ref == 'W':
                longitude = -longitude
            longitude

            wkt = f'POINT ({longitude} {latitude})'
            
            conn.execute(
                "UPDATE images SET timestamp = ?, location = GeomFromText(?, 4326) WHERE image_path = ?",
                (timestamp, wkt, image_path)
            )
            conn.commit()
            
############################################3            

def add_trees_to_db(conn, image_path, results_cpu):
    """Add tree detection results to the database."""
        
    # Get the image_id for the current image_path
    cursor = conn.execute(f"SELECT image_id FROM images WHERE image_path = '{image_path}'")
    image_id = cursor.fetchone()[0]
    ic(image_id)
            
    # add records to trees table
    ################
    boxes = results_cpu[0].boxes
    conf_list = boxes.conf.cpu().numpy().tolist()
    class_list = boxes.cls.cpu().numpy().tolist()
    # tree_contour_list = cpu_results[0].masks.xy

    try:
        mask_tensor = results_cpu[0].masks.data
    except AttributeError:
        log.error("The results object does not have the expected 'masks' attribute. Ensure that the model is configured to output masks.")
        return

    # Convert PyTorch Tensor to NumPy array
    binary_masks = (mask_tensor.cpu().numpy() * 255).astype(np.uint8)

    for i, binary_mask in enumerate(binary_masks):
        
        # Find clean, isolated contours
        # RETR_EXTERNAL ignores internal holes and fragment hierarchies completely
        # CHAIN_APPROX_SIMPLE implements lossless compression by removing coordinates on straight lines
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        tree_contour = max(contours, key=cv2.contourArea)
        if len(tree_contour) == 0:
            continue
        
        # convert tree_contour to int32 numpy array
        tree_contour = tree_contour.astype(np.int32)
        tree_contour = np.squeeze(tree_contour)

        # Check if the last coordinate matches the first
        # tree_contour[0] is first point [x, y], tree_contour[-1] is last point [x, y]
        if not np.array_equal(tree_contour[0], tree_contour[-1]):
            # Append the first point to the end to close the loop
            tree_contour = np.vstack([tree_contour, tree_contour[0]])  
                                        
        # convert tree_contour from np.int32 to WKT   
        coord_str = ', '.join([f'{coord[0]} {coord[1]}' for coord in tree_contour])
        wkt = f"POLYGON (({coord_str}))"
        
        # 4. Insert into the database
        
        # class_id = class_list[i]
        confidence = conf_list[i]
        conn.execute(
            "INSERT INTO trees (image_id, confidence, tree_poly) VALUES (?, ?, GeomFromText(?, 0))", 
            (image_id, confidence, wkt)
        )
        conn.commit()

######
# MAIN
######

# setup logger

log = setup_logging(log_filename='august.log')
log.setLevel(logging.DEBUG)
log.info('###########################################################################')

# sys.exit()

# Route icecream output through your logger's debug method
ic.configureOutput(outputFunction=log.debug)

log.info('reading config.toml')
config = dict_from_toml('config.toml')
log.debug(ic.format(config))

log.info('reading configsql.toml')
configsql = dict_from_toml('configsql.toml')

# sys.exit()

db_path = config['database']['db_path']
log.info(f'initializing database {db_path}')
# ic(config['database']['delete_db'])
if config['database']['delete_db']:
    log.info(f'recreating {db_path}')
    if os.path.exists(db_path):
        os.remove(db_path)
        
##########
    
conn = sqlite3.connect(db_path)   
conn.enable_load_extension(True)
conn.load_extension('mod_spatialite')
conn.execute("SELECT InitSpatialMetaData(1);")

log.info('creating cluster2class table')
df = pd.read_csv(config['trees']['csv_path'])
df.to_sql("cluster2class", conn, if_exists="replace", index=False)

log.info('creating damage_cluster2class table')
df = pd.read_csv(config['damage']['csv_path'])
df.to_sql("damage_cluster2class", conn, if_exists="replace", index=False)

log.info('running default_schema.sql')
conn.executescript(configsql['default_schema_sql'])
conn.commit()

# sys.exit()     
##########

# conn.executescript(configsql['create_v_tree_poly_view_sql'])
# conn.commit()

conn.executescript(configsql['create_v_camera_movement_sql'])
conn.commit()




# log.info('creating cluster2class table')
# df = pd.read_csv(config['trees']['csv_path'])
# df.to_sql("cluster2class", conn, if_exists="replace", index=False)

# # Check db tables
# cursor = conn.cursor()
# cursor.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%';")
# db_tables = cursor.fetchall()
# ic(db_tables)

log.info('detecting coconut palms in images')

log.info('### STEP 1: GET INPUT IMAGE LIST')
image_paths = config['images']['image_paths']
text_prompts = ["coconut palm tree"]

log.info('### STEP 2: RUN SAM3 SEMANTIC PREDICTOR ON IMAGES AND ADD RESULTS TO DATABASE')
for image_path in image_paths:
    if already_in_db(db_path, 'images', 'image_path', image_path):
        log.info(f'{image_path} already in database; continuing')
        continue
    if not os.path.exists(image_path):
        log.info(f'{image_path} not found; continuing')
        continue
    results_cpu = run_sam3_semantic_predictor(image_path, text_prompts)
    add_image_to_db(conn, image_path, results_cpu)
    add_trees_to_db(conn, image_path, results_cpu)
    
    ## Postprocessing steps for current image
    
    # get image_id
    cursor = conn.cursor()
    cursor.execute(f'SELECT image_id from images where image_path = "{image_path}"')
    image_id = cursor.fetchone()[0]
    ic(image_id)
    
    # flip ys in tree contours so they overlay images
    conn.execute(f'UPDATE trees SET tree_poly = ATM_Transform(tree_poly, ATM_CreateScale(1, -1)) WHERE image_id = {image_id}')
    
    template = configsql['tree_edge_proximity_sql']
    sql = template.format(image_id=image_id)
    conn.executescript(sql)

# sys.exit()     
##########

# log.info('### STEP 3: RUN POSTPROCESSING SQL')
# conn.executescript(configsql['postprocessing_sql'])
# conn.commit()

# sys.exit()
##########

log.info('### STEP 4: CLASSIFY TREE SHAPES')

# classify tree shapes using this filter:     additional_filters='AND confidence>0.4 AND tree_touches_edge=0 AND pixel_count > 400'
classify_tree_shapes(db_path, model_path=config['trees']['model_path'])

# log.info('running tree shape classifier pipeline')
# run_tree_shape_classifier_pipeline(db_path, csv_path=config['trees']['csv_path'])

# log.info('update trees.tree_class based on clustering results')
with open('tree_class_lookup.sql', 'r') as file:
    sql_script = file.read()
conn.executescript(sql_script)
conn.commit() 

log.info('### STEP 5: Calculate damage shapes')




log.info('### STEP 6: Classify damage shapes')


sys.exit()
####################################################################

# log.info('populate damage.damage_poly')

# conn.execute(configsql['create_v_tree_poly_view_sql'])





# tree_id = tree_cursor.lastrowid 
# ic(tree_id)
# defect_contours = calc_defect_contours(image_height, image_width, tree_contour, config['order'], config['minpixels'])  
# for defect_contour in defect_contours: 
#     defect_contour = np.squeeze(defect_contour)         
#     # convert defect_contour from np.int32 to WKT 
#     coord_str = ', '.join([f'{coord[0]} {coord[1]}' for coord in defect_contour])
#     wkt = f"POLYGON (({coord_str}))"
#     conn.execute(
#         'INSERT INTO damage (image_id, tree_id, damage_poly) VALUES (?, ?, GeomFromText(?, 0))', 
#         (image_id, tree_id, wkt)    
#     ) 

conn.commit() 
conn.close()

########################################################################
  
log.info('FINISHED')

