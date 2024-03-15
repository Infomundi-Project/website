DROP TABLE IF EXISTS comment_reactions;
DROP TABLE IF EXISTS comments;

/*
CREATE TABLE users (
    user_id VARCHAR(10) PRIMARY KEY,
    username VARCHAR(30) NOT NULL UNIQUE,
    role VARCHAR(15) DEFAULT 'user',
    password VARCHAR(150) NOT NULL,
    email VARCHAR(50) NOT NULL UNIQUE,
    avatar_url VARCHAR(80),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
*/

CREATE TABLE comments (
    comment_id VARCHAR(10) PRIMARY KEY,
    user_id VARCHAR(10),
    news_id VARCHAR(35),
    parent_comment_id VARCHAR(10) DEFAULT NULL,  -- NULL for top-level comments, refers to comment_id for replies
    text TEXT NOT NULL,
    likes INT DEFAULT 0,
    is_root_comment TINYINT(1) NOT NULL,
    dislikes INT DEFAULT 0,
    reports INT DEFAULT 0,
    timestamp VARCHAR(30),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (parent_comment_id) REFERENCES comments(comment_id) ON DELETE CASCADE  -- Ensures replies are deleted if the parent comment is deleted
);

CREATE TABLE comment_reactions (
    reaction_id VARCHAR(12) PRIMARY KEY,
    comment_id VARCHAR(10),
    user_id VARCHAR(10),
    type ENUM('like', 'dislike', 'report'),
    FOREIGN KEY (comment_id) REFERENCES comments(comment_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    UNIQUE KEY unique_reaction (comment_id, user_id, type)  -- Ensures a user can only like or dislike a comment once
);

