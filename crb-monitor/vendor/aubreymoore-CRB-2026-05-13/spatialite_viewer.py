import os
import sqlite3
import webbrowser

# 1. Define your file paths and database info
DB_PATH = "Efate2025B_4k.db"
SPATIALITE_EXT_PATH = (
    "/usr/lib/x86_64-linux-gnu/mod_spatialite.so"  # Change to your SpatiaLite extension path
)
OUTPUT_HTML = "spatial_render.html"

# 2. Connect to the database and load SpatiaLite extension
conn = sqlite3.connect(DB_PATH)
conn.enable_load_extension(True)
conn.load_extension("mod_spatialite")

cursor = conn.cursor()

try:
    # 3. Fetch the SVG path AND the bounding box (for automatic browser scaling)
    # Change 'your_spatial_table' and 'id' to match your actual database
    query = """
    SELECT 
        AsSVG(tree_poly, 0, 3) AS svg_path,
        ST_MinX(tree_poly), ST_MinY(tree_poly), 
        ST_MaxX(tree_poly) - ST_MinX(tree_poly) AS width, 
        ST_MaxY(tree_poly) - ST_MinY(tree_poly) AS height
    FROM trees 
    WHERE tree_id = 11;
    """
    cursor.execute(query)
    row = cursor.fetchone()

    if row and row[0]:
        svg_path, min_x, min_y, width, height = row

        # If width or height are 0 (e.g., a Point), give it a default view padding
        if width == 0:
            width, min_x = 10, min_x - 5
        if height == 0:
            height, min_y = 10, min_y - 5

        # 4. Generate the HTML template with the dynamic viewBox and SVG path
        # Note: SVG Y-axis goes down, GIS Y-axis goes up, so we invert the transform scale
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>SpatiaLite Render</title>
</head>
<body style="margin:20px; font-family:sans-serif; background:#f0f0f0;">
    <h2>Python + SpatiaLite Rendered Vector Image</h2>
    <div style="background:white; padding:10px; display:inline-block; border-radius:8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <svg width="800" height="600" viewBox="{min_x} {min_y} {width} {height}" style="border:1px solid #ccc;">
            <g>
                <path d="{svg_path}" fill="#3498db" stroke="#2980b9" stroke-width="{width * 0.005}" />
            </g>
        </svg>
    </div>
</body>
</html>
"""

        # 5. Write to file and open automatically in your browser
        with open(OUTPUT_HTML, "w") as f:
            f.write(html_content)

        print(f"Success! Map vector generated. Opening {OUTPUT_HTML}...")
        webbrowser.open("file://" + os.path.abspath(OUTPUT_HTML))

    else:
        print("No geometry data found for the selected ID.")

except sqlite3.OperationalError as e:
    print(f"Database error: {e}")
    print("Ensure your SpatiaLite extension path is configured correctly.")

finally:
    conn.close()
