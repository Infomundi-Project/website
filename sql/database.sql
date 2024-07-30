DROP TABLE IF EXISTS account_recovery_tokens;
DROP TABLE IF EXISTS register_tokens;

CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(10) PRIMARY KEY,
    username VARCHAR(25) NOT NULL UNIQUE,
    role VARCHAR(15) DEFAULT 'user',
    password VARCHAR(100) NOT NULL,
    email VARCHAR(70) NOT NULL UNIQUE,
    avatar_url VARCHAR(80),

    display_name VARCHAR(40) NOT NULL,
    
    profile_description VARCHAR(1500),
    profile_banner_url VARCHAR(80),
    profile_wallpaper_url VARCHAR(80),
    level INT DEFAULT 0,
    level_progress INT DEFAULT 0,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    in_recovery TINYINT(1) DEFAULT 0,
    recovery_token VARCHAR(40),
    recovery_token_timestamp TIMESTAMP
);

CREATE TABLE register_tokens (
    user_id VARCHAR(10) PRIMARY KEY,
    email VARCHAR(70) UNIQUE NOT NULL,
    username VARCHAR(30) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    token VARCHAR(40) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create friendships table
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

-- No changes needed for the users table
