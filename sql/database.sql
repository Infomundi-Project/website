DROP TABLE IF EXISTS account_recovery_tokens;
DROP TABLE IF EXISTS register_tokens;

CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(20) NOT NULL PRIMARY KEY,
    username VARCHAR(25) NOT NULL UNIQUE,
    email VARCHAR(70) NOT NULL UNIQUE,
    role VARCHAR(15) DEFAULT 'user',
    password VARCHAR(100) NOT NULL,
    session_version INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    display_name VARCHAR(40),
    avatar_url VARCHAR(80),
    profile_description VARCHAR(1500),
    profile_banner_url VARCHAR(80),
    profile_wallpaper_url VARCHAR(80),
    level INT DEFAULT 0,
    level_progress INT DEFAULT 0,
    in_recovery BOOLEAN DEFAULT FALSE,
    recovery_token VARCHAR(40),
    recovery_token_timestamp DATETIME,
    delete_token VARCHAR(40),
    delete_token_timestamp DATETIME,
    is_online BOOLEAN DEFAULT FALSE,
    last_activity DATETIME,
    totp_secret VARCHAR(120),
    totp_recovery VARCHAR(120),
    derived_key_salt VARCHAR(120)
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
    CONSTRAINT unique_friendship UNIQUE (user_id, friend_id),
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_friend FOREIGN KEY (friend_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE common_passwords (
    id INT AUTO_INCREMENT PRIMARY KEY,
    password VARCHAR(30) NOT NULL
);
