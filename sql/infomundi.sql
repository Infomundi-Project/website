DROP TABLE IF EXISTS story_stats;
DROP TABLE IF EXISTS story_reactions;
DROP TABLE IF EXISTS user_ip_history;
DROP TABLE IF EXISTS feeds;
DROP TABLE IF EXISTS friendships;
DROP TABLE IF EXISTS stories;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS publishers;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS common_passwords;
DROP TABLE IF EXISTS register_tokens;
DROP TABLE IF EXISTS site_statistics;
DROP TABLE IF EXISTS stocks;
DROP TABLE IF EXISTS currencies;
DROP TABLE IF EXISTS crypto;
DROP TABLE IF EXISTS global_salts;


CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(20) NOT NULL PRIMARY KEY,
    username VARCHAR(25) NOT NULL UNIQUE,
    email VARCHAR(128) NOT NULL UNIQUE,
    role VARCHAR(15) DEFAULT 'user',
    password VARCHAR(150) NOT NULL,
    session_version INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    
    -- Customization
    display_name VARCHAR(40),
    profile_description VARCHAR(1500),
    avatar_url VARCHAR(80),
    profile_banner_url VARCHAR(80),
    profile_wallpaper_url VARCHAR(80),
    level INT DEFAULT 0,
    level_progress INT DEFAULT 0,

    -- Recovery
    in_recovery BOOLEAN DEFAULT FALSE,
    recovery_token VARCHAR(40),
    recovery_token_timestamp DATETIME,

    -- Account deletion
    delete_token VARCHAR(40),
    delete_token_timestamp DATETIME,

    -- Activity
    is_online BOOLEAN DEFAULT FALSE,
    last_activity DATETIME,

    -- Totp
    totp_secret VARCHAR(120),
    totp_recovery VARCHAR(120),
    mail_twofactor VARCHAR(6),
    mail_twofactor_timestamp DATETIME,

    -- Encryption
    derived_key_salt VARCHAR(120),
    INDEX idx_username (username),
    INDEX idx_email (email)
);


CREATE TABLE publishers (
    publisher_id INT AUTO_INCREMENT PRIMARY KEY,
    
    name VARCHAR(100) NOT NULL,
    publisher_hash BINARY(16) NOT NULL,
    link VARCHAR(120) NOT NULL,
    favicon VARCHAR(100) NOT NULL
);


CREATE TABLE categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(20) UNIQUE NOT NULL
);


CREATE TABLE tags (
    tag_id INT AUTO_INCREMENT PRIMARY KEY,
    tag VARCHAR(30) UNIQUE NOT NULL
);


CREATE TABLE stories (
    story_id INT AUTO_INCREMENT PRIMARY KEY,
    story_hash BINARY(16) NOT NULL UNIQUE,
    
    title VARCHAR(150) NOT NULL,
    description VARCHAR(500),
    gpt_summary JSON,
    
    link VARCHAR(512) NOT NULL,
    pub_date DATETIME NOT NULL,
    media_content_url VARCHAR(100),
    has_media_content TINYINT(1) DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    category_id INT NOT NULL,
    publisher_id INT NOT NULL,

    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    FOREIGN KEY (publisher_id) REFERENCES publishers(publisher_id)
);


CREATE TABLE story_reactions (
    reaction_id INT AUTO_INCREMENT PRIMARY KEY,
    story_hash BINARY(16) NOT NULL,
    user_id VARCHAR(20),
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    action VARCHAR(10),  -- 'like' or 'dislike'
    
    FOREIGN KEY (story_hash) REFERENCES stories(story_hash),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    UNIQUE KEY unique_reaction (story_hash, user_id, action)
);


CREATE TABLE story_stats (
    story_hash BINARY(16) PRIMARY KEY,
    
    dislikes INT DEFAULT 0,
    clicks INT DEFAULT 0,
    likes INT DEFAULT 0,

    FOREIGN KEY (story_hash) REFERENCES stories(story_hash) ON DELETE CASCADE
);

CREATE TABLE feeds (
    feed_id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT NOT NULL,
    feed_hash BINARY(16),

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    site VARCHAR(120) NOT NULL,
    url VARCHAR(150) NOT NULL,
    favicon VARCHAR(150),

    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);


CREATE TABLE register_tokens (
    user_id VARCHAR(10) PRIMARY KEY,
    email VARCHAR(70) UNIQUE NOT NULL,
    username VARCHAR(30) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    token VARCHAR(40) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE friendships (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(10) NOT NULL,
    friend_id VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(10) NOT NULL DEFAULT 'pending',
    accepted_at TIMESTAMP,
    CONSTRAINT unique_friendship UNIQUE (user_id, friend_id),
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_friend FOREIGN KEY (friend_id) REFERENCES users(user_id) ON DELETE CASCADE
);


CREATE TABLE common_passwords (
    id INT AUTO_INCREMENT PRIMARY KEY,
    password VARCHAR(30) NOT NULL
);


CREATE TABLE site_statistics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    total_countries_supported INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_news VARCHAR(15) NOT NULL,
    total_feeds INT NOT NULL,
    total_users INT NOT NULL,
    total_comments INT NOT NULL,
    last_updated_message VARCHAR(15) NOT NULL,
    total_clicks BIGINT NOT NULL
);


CREATE TABLE stocks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    country_name VARCHAR(40) NOT NULL,
    data TEXT
);


CREATE TABLE currencies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    data TEXT
);


CREATE TABLE crypto (
    id INT AUTO_INCREMENT PRIMARY KEY,
    data TEXT
);


CREATE TABLE global_salts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    salt VARCHAR(64) NOT NULL
);


CREATE INDEX idx_story_hash ON stories (story_hash);
CREATE INDEX idx_publisher_hash ON publishers (publisher_hash);
CREATE INDEX idx_feed_hash ON feeds (feed_hash);
