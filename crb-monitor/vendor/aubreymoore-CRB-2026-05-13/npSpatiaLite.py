# https://gemini.google.com/share/7f7283a4d82a

import sqlite3
import numpy as np
import cv2

# --- 1. Serialization (Writing to Database) ---
def insert_numpy_array(cursor, conn, geom_wkt, array):
    """
    Serializes a numpy array instantly into a BLOB using memoryview 
    and inserts it alongside its spatial geometry.
    
    Parameters:
        -----------
        cursor : sqlite3.Cursor
            The active SQLite database cursor used to execute the query.
        conn : sqlite3.Connection
            The database connection object used to commit the transaction.
        geom_wkt : str
            The spatial geometry formatted as Well-Known Text (WKT), 
            e.g., 'POINT(121.05 14.55)'.
        array : numpy.ndarray
            The NumPy array (e.g., an OpenCV image frame) to be stored. 
            Can be of any shape or dtype.
            
        Returns:
        --------
        None   
    """
    # Grab raw memory reference without copying the data in Python
    blob_data = memoryview(array)
    
    # Format shape as a simple string, e.g., "720,1280,3"
    shape_str = ",".join(map(str, array.shape))
    dtype_str = str(array.dtype)
    
    # SQL query (using SpatiaLite geometry function)
    query = """
        INSERT INTO image_data (geometry, raw_bytes, shape, dtype)
        VALUES (ST_GeomFromText(?, 4326), ?, ?, ?)
    """
    
    cursor.execute(query, (geom_wkt, blob_data, shape_str, dtype_str))
    conn.commit()

# --- 2. Deserialization (Reading from Database) ---
def fetch_numpy_array(cursor, row_id):
    """
    Retrieves the raw bytes and perfectly reconstructs the NumPy 
    array for OpenCV use without overhead.
    
    Parameters:
    -----------
    cursor : sqlite3.Cursor
        The active SQLite database cursor used to execute the selection.
    row_id : int
        The primary key ID of the row containing the target array.

    Returns:
    --------
    numpy.ndarray or None
        The reconstructed NumPy array with its original shape and dtype restored, 
        or None if no matching record is found.
    """
    query = "SELECT raw_bytes, shape, dtype FROM image_data WHERE id = ?"
    cursor.execute(query, (row_id,))
    row = cursor.fetchone()
    
    if not row:
        return None
        
    raw_bytes, shape_str, dtype_str = row
    
    # Parse metadata
    shape = tuple(map(int, shape_str.split(',')))
    
    # Reconstruct the array directly out of the memory buffer
    array = np.frombuffer(raw_bytes, dtype=dtype_str).reshape(shape)
    return array


# # --- Example Usage Workflow ---
# if __name__ == "__main__":
#     # Setup dummy SQLite/SpatiaLite connection
#     # conn = sqlite3.connect(":memory:") # Use your spatialite file path here
#     conn = sqlite3.connect("npSpatiaLite.db") # Use your spatialite file path here
#     cursor = conn.cursor()
    
#     # (Optional: Enable SpatiaLite extension if using actual spatial queries)
#     conn.enable_load_extension(True)
#     conn.load_extension("mod_spatialite")
    
#     # Initialize a mock table for this example
#     cursor.execute("""
#         CREATE TABLE image_data (id INTEGER PRIMARY KEY, geometry TEXT, raw_bytes BLOB, shape TEXT, dtype TEXT)
#     """)

#     # Create a typical OpenCV image (BGR Matrix)
#     mock_cv_frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
#     sample_point = "POINT(121.05 14.55)"

#     # Save to DB
#     insert_numpy_array(cursor, contour, table_name="image_data", geometry_col="geometry", array=contour)

#     insert_numpy_array(cursor, conn, geom_wkt='POINT(121.05 14.55)', array=contour)
#     print("Array successfully stored.")

#     # Retrieve from DB
#     retrieved_frame = fetch_numpy_array(cursor, 1)
#     print("Array successfully retrieved. Shape matches:", retrieved_frame.shape)
    
#     # Perfect match check
#     assert np.array_equal(mock_cv_frame, retrieved_frame)
    
#     # Ready for immediate CV2 operations
#     # gray = cv2.cvtColor(retrieved_frame, cv2.COLOR_BGR2GRAY)