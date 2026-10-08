-- images table

CREATE TABLE IF NOT EXISTS images (
    image_id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path TEXT UNIQUE,
    image_width INTEGER,
    image_height INTEGER,
    timestamp TEXT
);

SELECT AddGeometryColumn(
    'images',            -- Table name
    'location',          -- Column name
    4326,                -- SRID (-1 or 0 signifies flat pixel/Cartesian space)
    'POINT',             -- Geometry type
    'XY'                 -- 2D coordinates
);

SELECT CreateSpatialIndex('images', 'location');

-- trees table

CREATE TABLE IF NOT EXISTS trees (
    tree_id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER,
    confidence REAL,
    tree_touches_edge INTEGER DEFAULT 0,
    pixel_count DOUBLE,
    shape_class INTEGER,
    soft_tree_class INTEGER,
    soft_tree_prob REAL,
    tree_class TEXT,
    FOREIGN KEY (image_id) REFERENCES images (image_id) ON DELETE CASCADE 
);

SELECT AddGeometryColumn(
    'trees',             -- Table name
    'tree_poly',         -- Column name
    0,                   -- SRID (-1 or 0 signifies flat pixel/Cartesian space)
    'POLYGON',           -- Geometry type
    'XY'                 -- 2D coordinates
);

SELECT CreateSpatialIndex('trees', 'tree_poly');

-- damage table

CREATE TABLE IF NOT EXISTS damage (
    damage_id INTEGER PRIMARY KEY AUTOINCREMENT, 
    image_id INTEGER,
    tree_id INTEGER, 
    FOREIGN KEY (tree_id) REFERENCES trees(tree_id) ON DELETE CASCADE
);

    SELECT AddGeometryColumn(
    'damage',            -- Table name
    'damage_poly',       -- Column name
    0,                   -- SRID (-1 or 0 signifies flat pixel/Cartesian space)
    'POLYGON',           -- Geometry type
    'XY'                 -- 2D coordinates
);

SELECT CreateSpatialIndex('damage', 'damage_poly');
