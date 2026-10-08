import sqlite3

db_path = 'test.db'

# 1. Connect to a database (or use :memory:)
conn = sqlite3.connect(db_path)

# 2. Enable loading extensions
conn.enable_load_extension(True)

# 3. Load the SpatiaLite extension
# The name may vary by OS (e.g., "mod_spatialite" or "libspatialite")
conn.load_extension("mod_spatialite")

# 4. Initialize spatial metadata (required for new databases)
conn.execute("SELECT InitSpatialMetaData();")

conn.close()
