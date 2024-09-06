DROP TABLE IF EXISTS story_reactions;
DROP TABLE IF EXISTS stories;
DROP TABLE IF EXISTS category_tags;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS publishers;
DROP TABLE IF EXISTS tags;

CREATE TABLE publishers (
    publisher_id VARCHAR(40) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    link VARCHAR(512) NOT NULL,
    favicon VARCHAR(100) NOT NULL
);

CREATE TABLE categories (
    category_id VARCHAR(15) PRIMARY KEY
);

CREATE TABLE tags (
    tag_id INT AUTO_INCREMENT PRIMARY KEY,
    tag VARCHAR(30) UNIQUE NOT NULL
);

CREATE TABLE category_tags (
    category_id VARCHAR(15),
    tag_id INT,
    PRIMARY KEY (category_id, tag_id),
    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    FOREIGN KEY (tag_id) REFERENCES tags(tag_id)
);

CREATE TABLE stories (
    story_id VARCHAR(40) PRIMARY KEY,
    title VARCHAR(120) NOT NULL,
    description VARCHAR(500),
    gpt_summary TEXT,
    clicks INT DEFAULT 0,
    link VARCHAR(512) NOT NULL,
    pub_date VARCHAR(30) NOT NULL,
    category_id VARCHAR(20) NOT NULL,
    publisher_id VARCHAR(40) NOT NULL,
    media_content_url VARCHAR(100),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    FOREIGN KEY (publisher_id) REFERENCES publishers(publisher_id),
    INDEX idx_created_at (created_at),
    INDEX idx_pub_date (pub_date),
    INDEX idx_clicks (clicks),
    INDEX idx_title (title)
);

CREATE TABLE story_reactions (
    reaction_id INT AUTO_INCREMENT PRIMARY KEY,
    story_id VARCHAR(40),
    user_id VARCHAR(10),
    action VARCHAR(10),  -- 'like' or 'dislike'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (story_id) REFERENCES stories(story_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    UNIQUE KEY unique_reaction (story_id, user_id, action)
);
