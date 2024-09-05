-- Create composite index to speed up filtering by category_id, created_at, and pub_date
CREATE INDEX idx_category_created_pubdate ON stories(category_id, created_at DESC, pub_date DESC);

-- Drop individual indexes now covered by the composite index
DROP INDEX idx_created_at ON stories;
DROP INDEX idx_pub_date ON stories;

-- Keep or remove other indexes based on your query patterns
-- DROP INDEX idx_clicks ON stories; -- (Optional: Drop if not frequently used)
-- DROP INDEX idx_title ON stories; -- (Optional: Drop if not frequently used)

-- Keep the index on media_content_url for filtering
CREATE INDEX idx_media_content_url ON stories(media_content_url);

-- Analyze the table to update statistics for the query planner
ANALYZE TABLE stories;

-- Optimize the table to reduce fragmentation and improve I/O performance
OPTIMIZE TABLE stories;
