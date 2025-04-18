DROP TABLE IF EXISTS story_stats;
DROP TABLE IF EXISTS story_reactions;
DROP TABLE IF EXISTS user_ip_history;
DROP TABLE IF EXISTS feeds;
DROP TABLE IF EXISTS friendships;
DROP TABLE IF EXISTS stories;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS publishers;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS common_passwords;
DROP TABLE IF EXISTS register_tokens;
DROP TABLE IF EXISTS site_statistics;
DROP TABLE IF EXISTS stocks;
DROP TABLE IF EXISTS currencies;
DROP TABLE IF EXISTS crypto;
DROP TABLE IF EXISTS global_salts;


CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    public_id BINARY(16) NOT NULL UNIQUE, -- UUIDv4 Binary, for public display
    
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
    avatar_url VARCHAR(80) DEFAULT 'https://infomundi.net/static/img/avatar.webp',
    profile_banner_url VARCHAR(80),
    profile_wallpaper_url VARCHAR(80),
    level INT DEFAULT 0,
    level_progress INT DEFAULT 0,

    -- Account Registration
    is_enabled TINYINT(1) DEFAULT 0,
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
    last_activity DATETIME,

    -- Totp 
    totp_secret VARCHAR(120), -- Stored in encrypted format (AES/GCM)
    totp_recovery VARCHAR(150), -- Stored in encrypted format (Argon2id)
    mail_twofactor INT,
    mail_twofactor_timestamp DATETIME
);


CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(15) UNIQUE NOT NULL
);


CREATE TABLE tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tag VARCHAR(30) UNIQUE NOT NULL
);


CREATE TABLE publishers (
    id INT AUTO_INCREMENT PRIMARY KEY,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    name VARCHAR(200) NOT NULL,
    url VARCHAR(200) NOT NULL,
    
    favicon_url VARCHAR(100),

    category_id INT NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);


CREATE TABLE stories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    title VARCHAR(150) NOT NULL,
    description VARCHAR(500) NOT NULL DEFAULT 'No description has been provided.',
    gpt_summary JSON,
    
    url VARCHAR(512) NOT NULL,
    
    /* The url_hash here is a MD5 hash of the URL. This prevents duplicate stories being inserted into the database, while
    maintaining performance and optimal disk usage. */
    url_hash BINARY(16) UNIQUE NOT NULL,
    
    pub_date DATETIME NOT NULL,
    image_url VARCHAR(100),
    has_image TINYINT(1) DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    category_id INT NOT NULL,
    publisher_id INT NOT NULL,

    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (publisher_id) REFERENCES publishers(id)
);


CREATE TABLE story_reactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    story_id INT NOT NULL,
    user_id INT NOT NULL,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    action VARCHAR(10),  -- 'like' or 'dislike'
    
    FOREIGN KEY (story_id) REFERENCES stories(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
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
    story_id INT NOT NULL,
    user_id INT,
    parent_id INT,
    content TEXT NOT NULL,
    is_edited TINYINT(1) DEFAULT 0,
    is_deleted TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE
);


CREATE TABLE comment_reactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    comment_id INT NOT NULL,
    user_id INT NOT NULL,
    action VARCHAR(10) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_comment_reaction UNIQUE (comment_id, user_id)
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

