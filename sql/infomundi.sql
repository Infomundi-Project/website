DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS bookmarks;
DROP TABLE IF EXISTS comment_stats;
DROP TABLE IF EXISTS comment_reactions;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS story_stats;
DROP TABLE IF EXISTS story_reactions;
DROP TABLE IF EXISTS friendships;
DROP TABLE IF EXISTS user_story_views;
DROP TABLE IF EXISTS stories;
DROP TABLE IF EXISTS user_blocks;
DROP TABLE IF EXISTS user_reports;
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS publishers;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS common_passwords;
DROP TABLE IF EXISTS register_tokens;
DROP TABLE IF EXISTS site_statistics;
DROP TABLE IF EXISTS stocks;
DROP TABLE IF EXISTS currencies;
DROP TABLE IF EXISTS crypto;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    public_id BINARY(16) NOT NULL UNIQUE, -- UUIDv4 Binary, for public display in certain occasions
    
    username VARCHAR(25) UNIQUE NOT NULL,
    
    /* The email is encrypted with AES/GCM. Realistically, we only require the email address during registration so we have SOME kind of protection against spam accounts, as the user needs to verify their email to be able to activate the account. 

    In order to prevent user login via username, the user can only log in via email. An attacker, to target an individual user in the platform, would have to know the user's email address first, not just their public username. 

    The email has to be stored in the database because:

    1. Allows user login
    2. Prevents, in some way, creation of spam accounts */
    email_fingerprint BINARY(32) UNIQUE NOT NULL,
    email_encrypted BINARY(120) NOT NULL,
    
    role VARCHAR(15) DEFAULT 'user',
    password VARCHAR(150) NOT NULL, -- Stored in encrypted format (Argon2id)
    session_version INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    
    -- Profile
    display_name VARCHAR(40),
    profile_description VARCHAR(1500),
    
    -- Below fields can all be calculated later in the application because paths to user-uploaded images are made of the user's public ID
    has_avatar TINYINT(1) DEFAULT 0,
    has_banner TINYINT(1) DEFAULT 0,
    has_wallpaper TINYINT(1) DEFAULT 0,
    
    -- Contact info
    website_url VARCHAR(120),
    public_email VARCHAR(120),
    
    -- External links
    twitter_url VARCHAR(80),
    instagram_url VARCHAR(80),
    linkedin_url VARCHAR(80),
    
    -- Level
    level INT DEFAULT 0,
    level_progress INT DEFAULT 0,
    
    -- Preferences
    profile_visibility TINYINT(1) DEFAULT 0,  -- 0 = public // 1 = login-only // 2 = friends-only // 3 = private
    notification_type TINYINT(1) DEFAULT 0,  -- 0 = all // 1 = important-only // 2 = none

    -- Account Registration
    is_enabled TINYINT(1) DEFAULT 0,
    is_thirdparty_auth TINYINT(1) DEFAULT 0,
    register_token BINARY(16),
    register_token_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Account Recovery
    in_recovery TINYINT(1) DEFAULT 0,
    recovery_token BINARY(16),
    recovery_token_timestamp DATETIME,

    -- Account Deletion
    delete_token BINARY(16),
    delete_token_timestamp DATETIME,

    -- Activity
    is_online TINYINT(1) DEFAULT 0,
    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Totp 
    is_totp_enabled TINYINT(1) DEFAULT 0,
    totp_secret BINARY(120  ), -- Stored in encrypted format (AES/GCM)

    totp_recovery VARCHAR(150), -- Stored in encrypted format (Argon2id)

    is_mail_twofactor_enabled TINYINT(1) DEFAULT 0,
    mail_twofactor_code INT,
    mail_twofactor_timestamp DATETIME,

    -- Messaging public key
    public_key_jwk JSON,

    -- Country info
    country_id MEDIUMINT UNSIGNED,
    state_id MEDIUMINT UNSIGNED,
    city_id MEDIUMINT UNSIGNED,

    FOREIGN KEY (country_id) REFERENCES countries(id),
    FOREIGN KEY (state_id) REFERENCES states(id),
    FOREIGN KEY (city_id) REFERENCES cities(id)
) WITH (DATA_COMPRESSION = ROW);


CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(15) UNIQUE NOT NULL
);


CREATE TABLE publishers (
    id INT AUTO_INCREMENT PRIMARY KEY,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    name VARCHAR(150) NOT NULL,
    feed_url VARCHAR(200),
    site_url VARCHAR(200),
    
    favicon_url VARCHAR(100),

    category_id INT NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);


CREATE TABLE stories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    title VARCHAR(250) NOT NULL,
    description VARCHAR(500) NOT NULL DEFAULT 'No description was provided.',
    gpt_summary JSON,
    lang VARCHAR(2) NOT NULL DEFAULT 'en',
    author VARCHAR(150),
    
    url VARCHAR(512) NOT NULL,
    
    /* The url_hash here is a MD5 hash of the URL. This prevents duplicate stories being inserted into the database, while
    maintaining performance and optimal disk usage. */
    url_hash BINARY(16) UNIQUE NOT NULL,
    
    pub_date DATETIME NOT NULL,
    has_image TINYINT(1) DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    category_id INT NOT NULL,
    publisher_id INT NOT NULL,
    country_id MEDIUMINT UNSIGNED,

    FOREIGN KEY (country_id) REFERENCES countries(id),
    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (publisher_id) REFERENCES publishers(id)
) WITH (DATA_COMPRESSION = ROW);


CREATE TABLE tags (
  id INT AUTO_INCREMENT PRIMARY KEY,
  story_id INT NOT NULL,
  tag VARCHAR(30) NOT NULL,
  UNIQUE KEY uq_story_tag (story_id,tag),
  KEY idx_tags_story (story_id),
  CONSTRAINT fk_tags_story
    FOREIGN KEY (story_id)
    REFERENCES stories (id)
    ON DELETE CASCADE
) WITH (DATA_COMPRESSION = ROW);


CREATE TABLE story_reactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    story_id INT NOT NULL,
    user_id INT NOT NULL,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    action VARCHAR(7) NOT NULL,  -- 'like', 'dislike', 'report'
    
    FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_reaction (story_id, user_id, action)
);


CREATE TABLE story_stats (
    story_id INT PRIMARY KEY,

    dislikes INT DEFAULT 0,
    views INT DEFAULT 0,
    likes INT DEFAULT 0,

    FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE CASCADE
);


CREATE TABLE friendships (
    id INT AUTO_INCREMENT PRIMARY KEY,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(10) NOT NULL DEFAULT 'pending',
    accepted_at TIMESTAMP,
    
    user_id INT NOT NULL,
    friend_id INT NOT NULL,
    CONSTRAINT unique_friendship UNIQUE (user_id, friend_id),
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_friend FOREIGN KEY (friend_id) REFERENCES users(id) ON DELETE CASCADE
);


CREATE TABLE site_statistics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    last_updated_message VARCHAR(15) NOT NULL,
    total_countries_supported INT NOT NULL,
    total_news INT NOT NULL,
    total_feeds INT NOT NULL,
    total_users INT NOT NULL,
    total_comments INT NOT NULL,
    total_clicks INT NOT NULL
);


CREATE TABLE comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    page_hash BINARY(16) NOT NULL, -- Unique page identifier (MD5)
    user_id INT,
    story_id INT,
    parent_id INT,
    content VARCHAR(1000) NOT NULL,
    url VARCHAR(100),
    is_flagged TINYINT(1) DEFAULT 0,
    is_edited TINYINT(1) DEFAULT 0,
    is_deleted TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE SET NULL,
    FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE
) WITH (DATA_COMPRESSION = ROW);


CREATE TABLE comment_reactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    comment_id INT NOT NULL,
    user_id INT NOT NULL,
    action VARCHAR(7) NOT NULL,  -- 'like', 'dislike', 'report'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_comment_reaction UNIQUE (comment_id, user_id)
);


CREATE TABLE comment_stats (
    comment_id INTEGER PRIMARY KEY REFERENCES comments(id) ON DELETE CASCADE,
    likes    INTEGER NOT NULL DEFAULT 0,
    dislikes INTEGER NOT NULL DEFAULT 0
);


CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- which user will receive this notification
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,
    
    type VARCHAR(20) NOT NULL, -- "default", "new_comment", "comment_reply", "comment_reaction", "friend_request", "friend_accepted", "friend_status", "mentions", "security", "profile_edit"
    
    comment_id INT,
    FOREIGN KEY (comment_id)
        REFERENCES comments(id) ON DELETE CASCADE,
    
    friendship_id INT,
    FOREIGN KEY (friendship_id)
        REFERENCES friendships(id) ON DELETE CASCADE,
    
    message VARCHAR(100) NOT NULL,
    url VARCHAR(512),

    is_read TINYINT(1) NOT NULL DEFAULT 0,
    read_at DATETIME,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_notifications_pending_friend (
        user_id,
        type,
        friendship_id,
        is_read
    )
) WITH (DATA_COMPRESSION = ROW);

-- Index to speed up querying unread notifications per user
CREATE INDEX idx_notifications_user_unread
    ON notifications(user_id, is_read);


CREATE TABLE bookmarks (
  id INT NOT NULL AUTO_INCREMENT,
  user_id INT NOT NULL,
  story_id INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_user_story_bookmark (user_id, story_id),
  CONSTRAINT fk_bookmarks_user
    FOREIGN KEY (user_id)
    REFERENCES users(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_bookmarks_story
    FOREIGN KEY (story_id)
    REFERENCES stories(id)
    ON DELETE CASCADE
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


CREATE TABLE user_reports (
  id INT NOT NULL AUTO_INCREMENT,
  reporter_id INT NOT NULL,
  reported_id INT NOT NULL,
  reason VARCHAR(500) DEFAULT NULL,
  -- add a category column with predefined set
  category ENUM(
    'spam',
    'harassment',
    'hate_speech',
    'inappropriate',
    'other'
  ) NOT NULL DEFAULT 'other',
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_at DATETIME DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_user_report (reporter_id, reported_id, category),
  KEY idx_user_reports_reporter (reporter_id),
  KEY idx_user_reports_reported (reported_id),
  CONSTRAINT fk_user_reports_reporter
    FOREIGN KEY (reporter_id) REFERENCES users (id)
    ON DELETE CASCADE,
  CONSTRAINT fk_user_reports_reported
    FOREIGN KEY (reported_id) REFERENCES users (id)
    ON DELETE CASCADE
);


CREATE TABLE user_blocks (
  id INT NOT NULL AUTO_INCREMENT,
  blocker_id INT NOT NULL,
  blocked_id INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_user_block (blocker_id, blocked_id),
  KEY idx_user_blocks_blocker (blocker_id),
  KEY idx_user_blocks_blocked (blocked_id),
  CONSTRAINT fk_user_blocks_blocker
    FOREIGN KEY (blocker_id) REFERENCES users (id)
    ON DELETE CASCADE,
  CONSTRAINT fk_user_blocks_blocked
    FOREIGN KEY (blocked_id) REFERENCES users (id)
    ON DELETE CASCADE
);


CREATE TABLE user_story_views (
  id INT NOT NULL AUTO_INCREMENT,
  user_id INT NOT NULL,
  story_id INT NOT NULL,
  viewed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  
  -- Foreign key constraints for referential integrity
  CONSTRAINT fk_user_story_views_user
    FOREIGN KEY (user_id)
    REFERENCES users (id)
    ON DELETE CASCADE,
    
  CONSTRAINT fk_user_story_views_story
    FOREIGN KEY (story_id)
    REFERENCES stories (id)
    ON DELETE CASCADE
);


CREATE TABLE messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT NOT NULL,
    receiver_id INT NOT NULL,
    content_encrypted TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    read_at DATETIME,
    delivered_at DATETIME,
    parent_id INT,
    FOREIGN KEY (parent_id) REFERENCES messages(id),
    FOREIGN KEY (sender_id) REFERENCES users(id),
    FOREIGN KEY (receiver_id) REFERENCES users(id)
) WITH (DATA_COMPRESSION = ROW);