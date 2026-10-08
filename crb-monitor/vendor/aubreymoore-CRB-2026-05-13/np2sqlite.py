import sqlite3
import io
import numpy as np
from icecream import ic
import os

def array2blob(array: np.ndarray) -> bytes:
    """ Converts a NumPy array into a byte stream suitable for storage in a SQLite BLOB field.
    This method uses NumPy's built-in save functionality to serialize the array efficiently.
    Parameters:
    -----------
    array : np.ndarray
        The NumPy array to be converted into a BLOB.
    Returns:
    --------
    bytes
        The byte stream representing the serialized array.
    """
    buffer = io.BytesIO()
    np.save(buffer, array)
    return buffer.getvalue()


def blob2array(blob: bytes) -> np.ndarray:
    """ Converts a byte stream from a SQLite BLOB field back into a NumPy array.
    Parameters:
    -----------
    blob : bytes
        The byte stream representing the serialized array.
    Returns:
    --------
    np.ndarray
        The reconstructed NumPy array.
    """
    return np.load(io.BytesIO(blob))


if __name__ == "__main__":
    ic()
    
    # Create DB with a BLOB field
    db_path = "arrays.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS storage (id INTEGER PRIMARY KEY, data BLOB)")
    conn.commit()
    
    # Create a sample 2D array
    array_to_store = np.array([[1, 2], [3, 4], [5, 6], [1, 2]], dtype=np.uint16)

    # Insert the array into the database
    blob_data = array2blob(array_to_store)
    ic(type(blob_data))
    cursor.execute("INSERT INTO storage (data) VALUES (?)", (sqlite3.Binary(blob_data),))
    conn.commit()

    # Retrieve the BLOB data
    cursor.execute("SELECT data FROM storage WHERE id = 1")
    fetched_blob = cursor.fetchone()[0]
    ic(type(fetched_blob), len(fetched_blob))  # Should be bytes and match the original blob size
    fetched_array = blob2array(fetched_blob)
    ic(type(fetched_array), fetched_array.shape, fetched_array.dtype) 
    
    # Verify that the original and loaded arrays are identical  
    ic(np.array_equal(fetched_array, array_to_store))
    
    # Close the database connection
    conn.close()
    
    ic()
