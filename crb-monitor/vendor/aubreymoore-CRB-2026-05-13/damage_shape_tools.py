# Reference: https://www.youtube.com/watch?v=CUjCqOw_oFk

# Use "pytest --xdoctest" to run doctests

# Here is an example of using xdoctest to test a single function in this module:
# xdoctest --verbose 2 damage_shape_tools.py create_db_views

# This library imports the python fire library to implement a CLI
# Reference: https://www.youtube.com/watch?v=F0V5c4-i81k&t=3s

import sqlite3
import json
import numpy as np
from icecream import ic
import cv2
import matplotlib.pyplot as plt
import os
import shutil
import joblib
# using the HDBSCAN implementation from the hdbscan package instead of sklearn because of bugs
import hdbscan
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import pandas as pd
import time
import fire
import tomllib
import sys
import xdoctest
import fire
from contextlib import contextmanager

##############################################################################################
# The first 3 functions are here to help me learn xdoctest and should be removed at some point
###############################################################################################


def parse_int(value):
    """
    Parses a string into an integer.

    Example:
        >>> try:
        ...     parse_int("not_a_number")
        ... except ValueError as ex:
        ...     print(f"Caught expected error: {ex}")
        Caught expected error: invalid literal for int() with base 10: 'not_a_number'
    """
    return int(value)

#############################################################################################

def validate_age(age):
    """
    Validates the user's age.

    >>> validate_age(-5)
    Traceback (most recent call last):
    ...
    ValueError: Age cannot be negative.
    """
    if age < 0:
        raise ValueError("Age cannot be negative.")
    return True

############################################################################################

def cause_runtime_error():
    """
    This function deliberately raises a RuntimeError.

    >>> cause_runtime_error()
    Traceback (most recent call last):
    RuntimeError: Something went wrong!
    """
    raise RuntimeError("Something went wrong!")

# if __name__ == "__main__":
#     import doctest
#     doctest.testmod()

##########################################################################################
##########################################################################################

@contextmanager
def open_db(db_path):
    conn = sqlite3.connect(db_path)
    try:
        # 1. Configure Row Factory (built-in dictionary-like rows)
        conn.row_factory = sqlite3.Row
        
        # 2. Load SpatiaLite Extension
        conn.enable_load_extension(True)
        conn.load_extension("mod_spatialite") 
        
        # Yield the fully configured connection
        yield conn
        
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# Usage example:

# db_path = 'new.db'
# with open_db() as conn:
#     cursor = conn.cursor()
    
#     # You can now use SpatiaLite functions right away
#     cursor.execute("SELECT image_id FROM images WHERE damage_flag = 0")
    
#     # Because of sqlite3.Row, you can access columns by name!
#     image_id_queue = [row['image_id'] for row in cursor.fetchall()]    
    
#     # Connection is automatically committed and closed here.
    
# ic(image_id_queue);       


def fit_contour_to_canvas(cnt, canvas_width, canvas_height, padding=20):
    # Get bounding box of the contour
    x, y, w, h = cv2.boundingRect(cnt)
    
    # Subtract padding from both sides of the canvas dimensions
    target_w = canvas_width - (padding * 2)
    target_h = canvas_height - (padding * 2)
    
    # Ensure target dimensions don't go below zero
    target_w = max(1, target_w)
    target_h = max(1, target_h)
    
    # Calculate scale factors using the padded dimensions
    scale_x = target_w / w
    scale_y = target_h / h
    scale = min(scale_x, scale_y)
    
    # Find center of the original bounding box
    center_x = x + w / 2
    center_y = y + h / 2
    
    # Center the contour at origin, scale, and shift to canvas center
    cnt_norm = cnt - np.array([center_x, center_y])
    cnt_scaled = cnt_norm * scale
    cnt_scaled = cnt_scaled + np.array([canvas_width / 2, canvas_height / 2])
    
    return cnt_scaled.astype(np.int32)


def run_train_damage_model_shape_pipeline(db_path, db_backup_dir, model_path, images_per_cluster, gallery_dir, min_prob):
    """  
    Trains an HDBSCAN model to assign model shapes to clusters.
    """
    backup_database(db_path, db_backup_dir)  
    check_damage_table(db_path) 
    train_model(db_path, model_path)    
    classify_damage_shapes(db_path, model_path)
    create_damage_cluster_gallery(db_path, images_per_cluster, gallery_dir, min_prob)


def run_damage_shape_classifier_pipeline(db_path, csv_path, model_path):
    """  
    Converts cluster index to damage_shape index.
    """ 
    ic()
    create_damage_cluster2class_table(db_path, csv_path)
    create_damage_view(db_path)
    classify_damage_shapes(db_path, model_path)
  
      
def create_damage_view(db_path: str):
    """ 
    Creates views named v_damage in the current db.
    v_damage contains the number of damage records associated with each damage in the v_damage view.
    
    Example:
        >>> db_path = '/home/aubrey/Desktop/crb-2026-05-13/test.db'
        >>> # check if the views exist
        >>> create_damage_view(db_path)  
        >>> conn = sqlite3.connect(db_path)
        >>> cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='view';")
        >>> view_names = [row[0] for row in cursor.fetchall()]
        >>> print(view_names)
        >>> assert len(view_names) > 0
        >>> assert 'v_damage' in view_names
        >>> assert 'v_damage' in view_names
        >>> conn.close()
    """
    # connect to db and enable spatial extensions
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            print(f"Creating views v_damage in database: {db_path}")
            conn.execute('DROP VIEW IF EXISTS v_damage;')
            conn.commit()
            
            conn.execute(''' 
                CREATE VIEW v_damage AS
                SELECT 
                    damage_id, 
                    image_id, 
                    confidence, 
                    damage_poly, 
                    pixel_count, 
                    soft_damage_class, 
                    soft_damage_prob, 
                    damage_cluster, 
                    cluster2class.damage_class
                FROM damage, cluster2class
                WHERE damage.soft_damage_class = cluster2class.damage_cluster
                ''')
            conn.commit
            
            conn.execute('DROP VIEW IF EXISTS v_damage;')
            conn.commit()
            
            conn.execute(''' 
                CREATE VIEW v_damage AS
                SELECT 
                    t.damage_id,  
                    t.damage_class,	
                    COUNT(d.damage_id) AS damage_count
                FROM v_damage t
                LEFT JOIN damage d ON t.damage_id = d.damage_id
                GROUP BY t.damage_id;
                ''')
            conn.commit()
            
    except sqlite3.Error as e:
        print(f"Transaction failed and was rolled back: {e}")
         
    conn.close()
    
# # Usage example:
# create_db_views('test.db')
       
##########################################################################################

def backup_database(db_path, db_backup_dir='db_backups'):
    os.makedirs(db_backup_dir, exist_ok=True)
    db_basename = os.path.basename(db_path)
    t = time.localtime()
    timestamp = time.strftime('%Y-%m-%d-%H%M', t)
    backup_name = db_basename.replace('.', f'-{timestamp}.')
    shutil.copy2(db_path, f'{db_backup_dir}/{backup_name}')
    
db_path = '/home/aubrey/Desktop/Efate2025/Efate2025B.db'
backup_database(db_path)

#############################################################################################

def create_damage_cluster2class_table(db_path: str, csv_path :str='damage_cluster2class.csv') -> None:
    """  
    Imports a csv file into a new database table named 'cluster_class'
    The csv file should contain 2 columns: 'damage_cluster' (integer) and 'damage_class' (string)
    If csv_path does not exist, a FileNotFound error is raised with a message instructions 
    on creation of cluster2class.csv.
    
    >>> create_cluster2class_table(db_path='/home/aubrey/Desktop/Efate2025/Efate2025B_copy.db', csv_path='missing.csv')
    ERROR: csv_path does not exist
    """
    if not os.path.exists(csv_path):
        return 'ERROR: csv_path does not exist'
    df = pd.read_csv(csv_path)
    df.to_sql(name='damage_cluster2class', con=sqlite3.connect(db_path), if_exists="replace", index=False)

###############################################################################################

def create_damage_cluster_gallery(db_path:str, images_per_cluster:int, gallery_dir:str, min_prob:float=0.2):
    """
    Creates a gallery of images for each HDBSCAN cluster (soft_damage_class).    
    Images are saved in folders named "damage_cluster_gallery/cluster_nn" where n is "soft_damage_class"
    A limit of images_per_cluster images with the largest soft_damage_prob greater than 0.2 are saved
    
    db_path:            path to Spatialite database
    images_per_cluster: maximum number of images generated per cluster
    gallery_dir:        path to gallery
    min_prob:           minimum soft_damage_prob for inclusion in examples
    """
    ic()
    ic(db_path, images_per_cluster, gallery_dir, min_prob)
    
    # connect to database and enable spatialite extension
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    conn.load_extension('mod_spatialite')
    conn.row_factory = sqlite3.Row # enables access by column name
    
    # get list of damage classes
    sql = """  
    SELECT DISTINCT(soft_damage_class) 
    FROM damage
    WHERE soft_damage_class IS NOT NULL 
    ORDER BY soft_damage_class
    """
    with conn:
        cursor = conn.execute(sql)
        soft_damage_classes = [row['soft_damage_class'] for row in cursor.fetchall()]
    ic(soft_damage_classes)

    # Create and save sample images for each damage shape class 
    shutil.rmtree(gallery_dir, ignore_errors=True)  # Remove existing directory if it exists
    for soft_damage_class in soft_damage_classes:
        damage_class_dir = f"{gallery_dir}/cluster_{soft_damage_class:02}"
        os.makedirs(damage_class_dir, exist_ok=True)
        
        sql = f""" 
        SELECT image_path, damage_id, AsGeoJSON(damage_poly) AS damage_contour_json
        FROM damage
        JOIN images USING (image_id)
        WHERE soft_damage_class = {soft_damage_class} 
          AND soft_damage_prob > {min_prob}
        ORDER BY soft_damage_prob DESC
        LIMIT {images_per_cluster}
        """
        
        with conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.close()
        
        for row in rows:        
            geojson_data = json.loads(row['damage_contour_json'])
            coords = geojson_data["coordinates"][0]
            contour = np.array(coords, dtype=np.int32).reshape((-1, 1, 2))
            
            # Create a binary canvas to draw the contour
            canvas = np.zeros((1080, 1080), dtype=np.uint8)

            # Normalize contour position to center of the visualization thumbnail
            cnt = contour.copy()
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                # cx = int(M["m10"] / M["m00"])
                # cy = int(M["m01"] / M["m00"])
                # cnt = cnt - [cx, cy] + [540, 540] # shifts center to (540,540)
                
                # fit contour to canvas
                cnt = fit_contour_to_canvas(cnt, 1080, 1080)
                
                cv2.drawContours(canvas, [cnt], -1, 255, thickness=cv2.FILLED)
                cv2.flip(canvas, 0, dst=canvas)  # Flip vertically for correct orientation
                cv2.imwrite(f"{damage_class_dir}/{row['damage_id']}.png", canvas)

# db_path = '/home/aubrey/Desktop/Efate2025/Efate2025B.db'
# gallery_dir = 'damage_cluster_gallery_1'
# images_per_cluster = 35
# min_prob = '0.2'              
# create_damage_cluster_gallery(db_path, images_per_cluster, gallery_dir, min_prob)
 
 ######################################################################################### 
                             
def get_spatialite_contours(db_path, table_name, geom_column, additional_filters='', limit=100):
    """
    Fetches geometries from a SpatiaLite database and converts them into 
    a list of NumPy arrays structured for OpenCV contour functions.
    
    Parameters:
        db_path (str): Path to the SpatiaLite database file.
        table_name (str): Name of the table to query.
        geom_column (str): Name of the geometry column.
        additional_filters(str): optional filters to be added to WHERE; see example below
        limit (int): Maximum number of features to fetch (default 100).
        
    Returns:
        list of np.ndarray: A list of arrays, each with shape (N, 1, 2) and dtype int32.
        
    Example for additional_filters argument: 'AND confidence>0.5 AND damage_touches_edge=0'
    """
    contours = []
    damage_ids = []
    
    # 1. Connect and query the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    conn.enable_load_extension(True)
    conn.load_extension('mod_spatialite')
    query = f"""
        SELECT AsGeoJSON({geom_column}), damage_id 
        FROM {table_name} 
        WHERE {geom_column} IS NOT NULL 
        {additional_filters}
        LIMIT {limit};
    """
    ic(query)
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # 2. Parse the results
        for row in rows:
            if not row[0]:
                continue
            
            damage_ids.append(row[1])    
            geojson_data = json.loads(row[0])
            geom_type = geojson_data.get("type")
            
            if geom_type == "Polygon":
                # Extract exterior ring coordinates
                coords = geojson_data["coordinates"][0]
                pts = np.array(coords, dtype=np.int32).reshape((-1, 1, 2))
                contours.append(pts)
                
            elif geom_type == "MultiPolygon":
                # Unroll each sub-polygon
                for polygon in geojson_data["coordinates"]:
                    coords = polygon[0]
                    pts = np.array(coords, dtype=np.int32).reshape((-1, 1, 2))
                    contours.append(pts)
                          
    finally:
        # Ensure the connection closes even if an error occurs
        conn.close()
        
    return contours, damage_ids

################################################################################

def extract_invariant_features(contour, log_transform=False):
    """
    Returns log-transformed Hu Moments from an OpenCV contour.
    These features are invariant to translation, scale, and rotation.
    Log transform is
    """
    moments = cv2.moments(contour)
    hu_moments = cv2.HuMoments(moments).flatten()
    if log_transform:
        log_hu = [-1.0 * np.sign(m) * np.log10(np.abs(m)) if m != 0 else 0.0 for m in hu_moments]
        return np.array(log_hu)
    else:
        return hu_moments

#########################################################################################

def train_model(db_path, model_path):
    """  
    Trains a HDBSCAN model to cluster damage shapes (polygons).
    Inputs are invariant Hu moments of polygons.
    Outputs are cluster indices.
    
    The trained model can be loaded and executed by this function:
    classify_damage_shapes(db_path:str, model_path:str, cluster2class:dict)
    
    Note that the cluster2class dictionary must be constructed by visual inspection of damage shape clusters.
    """
    
    
    
    ###################################################################################
    # The following block was simplified by abandoning the use of get_spatial_contours
    # for an explicitly defined query.
      
    # Get damage contours and calculate invariant features (Hu moments)
    
    # contours, damage_ids = get_spatialite_contours(
    #     db_path=db_path,
    #     table_name='damage',
    #     geom_column='damage_poly',
    #     additional_filters='AND confidence>0.4 AND tree_touches_edge=0 AND pixel_count > 400',
    #     limit=1000000   
    # )
    
    with open_db(db_path) as conn:
        cursor = conn.cursor()
        query = '''
        SELECT damage_id, AsGeoJSON(damage_poly) AS geojson_data
        FROM trees, damage
        WHERE 
            trees.tree_id = damage.tree_id
            AND tree_touches_edge = 0
            AND trees.pixel_count > 400
        LIMIT 1000 ''' # training with 1000 damage polygons
        cursor.execute(query)
        rows = cursor.fetchall()
        
    damage_ids = []
    contours = []
    for row in rows:
        if not row[0]:
                continue       
        damage_ids.append(row['damage_id'])    
        geojson_data = json.loads(row['geojson_data'])
        ic(geojson_data)
        # Extract exterior ring coordinates
        coords = geojson_data["coordinates"][0]
        pts = np.array(coords, dtype=np.int32).reshape((-1, 1, 2))
        contours.append(pts)

    ######################################################################################
    
    features = np.array([extract_invariant_features(c) for c in contours])

    # Create, run and save pipeline
    hdbscan_pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('hdbscan', hdbscan.HDBSCAN(
            min_cluster_size=15, 
            prediction_data=True
        ))
    ])
    hdbscan_pipeline.fit(features)
    joblib.dump(hdbscan_pipeline, model_path)
    
    # Usage example:
    # train_model(db_path=Efate2025B_4k.db, model_path='hdbscan_damage_pipeline.joblib')

##############################################################################################

def classify_damage_shapes(db_path:str, model_path:str):
    """  
    This function uses a trained HDBSCAN model to assign a values in the damage.damage_poly field into clusters.
    The shape is then assigned to a class using the cluster2class dictionary.
    """
    ic(db_path, model_path)
    
    # conn = sqlite3.connect(db_path)
    # conn.enable_load_extension(True)
    # conn.load_extension('mod_spatialite')
    
    # # Get damage contours and extract invariant features
    # contours, damage_ids = get_spatialite_contours(
    #     db_path=db_path,
    #     table_name='damage',
    #     geom_column='damage_poly',
    #     additional_filters='AND confidence>0.4 AND damage_touches_edge=0 AND pixel_count > 400',
    #     limit=1000000   
    # )
    # ic(type(damage_ids), ic(len(damage_ids)));
    
    # RUN SAME QUERY AS USED IN TRAINING
    with open_db(db_path) as conn:
        cursor = conn.cursor()
        query = '''
        SELECT damage_id, AsGeoJSON(damage_poly) AS geojson_data
        FROM trees, damage
        WHERE 
            trees.tree_id = damage.tree_id
            AND tree_touches_edge = 0
            AND trees.pixel_count > 400
        '''
        cursor.execute(query)
        rows = cursor.fetchall()
        
    damage_ids = []
    contours = []
    for row in rows:
        if not row[0]:
                continue       
        damage_ids.append(row['damage_id'])    
        geojson_data = json.loads(row['geojson_data'])
        ic(geojson_data)
        # Extract exterior ring coordinates
        coords = geojson_data["coordinates"][0]
        pts = np.array(coords, dtype=np.int32).reshape((-1, 1, 2))
        contours.append(pts)

    features = np.array([extract_invariant_features(c) for c in contours])
    ic(features);
    
    # 1. Load your originally saved pipeline (Scaler + HDBSCAN)
    loaded_pipeline = joblib.load(model_path)
    scaler = loaded_pipeline.named_steps['scaler']
    hdbscan_model = loaded_pipeline.named_steps['hdbscan']

    # 2. Incoming new raw data X (e.g., 3 new points)
    new_X = features
    new_X_scaled = scaler.transform(new_X)

    # 2. Generate a membership vector matrix for the new data
    # This returns a matrix of shape: (n_samples, n_clusters)
    soft_probabilities = hdbscan.membership_vector(hdbscan_model, new_X_scaled)
    ic(soft_probabilities);

    # 3. Clean up edge cases (Optional but highly recommended)
    # Outlier points or extreme noise may result in all zeros for a row
    # You can normalize them or identify them by checking the row sums
    row_sums = soft_probabilities.sum(axis=1)
    is_noise = row_sums == 0
    ic(f"Number of noise points: {np.sum(is_noise)}");
    
    # gets the index of largest value in each row: this will be the damage_class
    soft_damage_classes = np.argmax(soft_probabilities, axis=1) 
    ic(soft_damage_classes)
    
    # gets the largest value in each row: this will be the probability 
    soft_damage_probs = np.max(soft_probabilities, axis=1)
    ic(soft_damage_probs)
    
    ic(hdbscan_model.labels_)
    
    # Update database with predicted cluster labels and probabilities
    
    with open_db(db_path) as conn:
        cursor = conn.cursor()
        for damage_id in damage_ids:
            idx = damage_ids.index(damage_id)
            if idx % 1000 == 0:
                print(f"Processing damage_id: {damage_id} (index {idx})")
            shape_class = int(hdbscan_model.labels_[idx])
            soft_damage_class = int(soft_damage_classes[idx])
            soft_damage_prob = float(soft_damage_probs[idx])
            cursor.execute(f""" 
                UPDATE damage
                SET shape_class = {shape_class}, 
                    soft_damage_class = {soft_damage_class}, 
                    soft_damage_prob = {soft_damage_prob}  
                WHERE damage_id = {damage_id}
            """)
    ic("Database updated with predicted cluster labels and probabilities.") 
    
# db_path = '/home/aubrey/Desktop/Efate2025/Efate2025B.db'
# model_path = 'hdbscan_pipeline_1.joblib'
# classify_damage_shapes(db_path, model_path)
     
##################################################################################

def check_damage_table(db_path):
    """ 
    Ensures required fields exist in damage table.
    Populates pixel_count field.
    
    model is saved as hdbscan_pipeline_1.joblib
    """    
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    conn.load_extension('mod_spatialite')
    
    # get field names from damage table
    with conn:
        cursor = conn.execute("PRAGMA table_info(damage)")
        field_names = [row[1] for row in cursor.fetchall()]
        ic(field_names)
    
    # ensure fields exist
    with conn:
        if 'pixel_count' not in field_names:     conn.execute('ALTER TABLE damage ADD COLUMN pixel_count DOUBLE')
        if 'shape_class' not in field_names:     conn.execute('ALTER TABLE damage ADD COLUMN shape_class INTEGER')
        if 'soft_damage_class' not in field_names: conn.execute('ALTER TABLE damage ADD COLUMN soft_damage_class INTEGER')
        if 'soft_damage_prob' not in field_names:  conn.execute('ALTER TABLE damage ADD COLUMN soft_damage_prob REAL')
        if 'confidence' not in field_names:  conn.execute('ALTER TABLE damage ADD COLUMN confidence REAL')
        if 'damage_class' not in field_names:      conn.execute('ALTER TABLE damage ADD COLUMN damage_class TEXT')
           
    # populate pixel_count field (= area of damage_poly in pixels)
    with conn:
        conn.execute('UPDATE damage SET pixel_count = ST_Area(damage_poly)')
    conn.close()
    
    ############################################
    
def main(): 
    
    # If '--test' is passed in the terminal arguments, run doctest instead of CLI
    if "--test" in sys.argv:
        sys.argv.remove("--test")  # Clean up arguments for doctest
        xdoctest.doctest_module(__file__)
        print("xdoctest completed.")
    else:
        os.environ["PAGER"] = "cat" # disables output in full page format
        fire.Fire({
            'backup_database': backup_database,   
            'check_damage_table': check_damage_table, 
            'train_model': train_model, 
            'classify_damage_shapes': classify_damage_shapes,
            'create_damage_cluster_gallery': create_damage_cluster_gallery,
            'run_train_damage_shape_model_pipeline': run_train_damage_model_shape_pipeline,
            'run_damage_shape_classifier_pipeline': run_damage_shape_classifier_pipeline,
            # 'create_db_views': create_db_views,
        })

    ################################################
        
if __name__ == '__main__':
    main()
