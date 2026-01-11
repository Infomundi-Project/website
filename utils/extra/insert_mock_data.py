"""
Mock Data Generator for Development Database

This script populates the development database with realistic mock data
for testing all features of the application.

Usage:
    docker compose exec infomundi-app python -m utils.extra.insert_mock_data

Prerequisites:
    - Run insert_feeds_to_database.py first to seed categories and publishers
    - Only runs in development/testing environments

Data generated:
    - 15 users with known credentials
    - 100 stories across existing categories
    - ~300 tags (3 per story)
    - ~150 comments (mix of top-level and replies)
    - ~200 story reactions
    - ~100 comment reactions
    - ~30 friendships
    - ~50 notifications
    - ~40 bookmarks
    - ~30 messages
    - ~100 story views
"""

import argparse
import os
import sys
import random
from datetime import datetime, timedelta

# Environment check - only run in development/testing
flask_env = os.getenv("FLASK_ENV", "production")
if flask_env not in ("development", "testing"):
    print(f"ERROR: This script only runs in development/testing environments.")
    print(f"Current FLASK_ENV: {flask_env}")
    print("Set FLASK_ENV=development to run this script.")
    sys.exit(1)

from sqlalchemy.exc import IntegrityError

from app import app
from website_scripts.extensions import db
from website_scripts import models, security_util, hashing_util


def parse_args():
    parser = argparse.ArgumentParser(description="Generate mock data for development")
    parser.add_argument(  
     "--country", "-c",
     help="Limit data to a specific country code (e.g., 'br', 'us', 'uk')"
    )
    parser.add_argument(  
     "--category", "-cat",
     help="Limit data to a specific category name (e.g., 'br_general', 'us_technology')" 
    )
    return parser.parse_args()

# ============================================================================
# Mock Data Constants
# ============================================================================

MOCK_USERS = [
    {"username": "testuser1", "email": "test1@example.com", "password": "password123"},
    {"username": "testuser2", "email": "test2@example.com", "password": "password123"},
    {"username": "testuser3", "email": "test3@example.com", "password": "password123"},
    {"username": "testuser4", "email": "test4@example.com", "password": "password123"},
    {"username": "testuser5", "email": "test5@example.com", "password": "password123"},
    {"username": "johndoe", "email": "john.doe@example.com", "password": "password123"},
    {"username": "janedoe", "email": "jane.doe@example.com", "password": "password123"},
    {"username": "alice_dev", "email": "alice@example.com", "password": "password123"},
    {"username": "bob_tester", "email": "bob@example.com", "password": "password123"},
    {"username": "charlie99", "email": "charlie@example.com", "password": "password123"},
    {"username": "diana_news", "email": "diana@example.com", "password": "password123"},
    {"username": "evan_reader", "email": "evan@example.com", "password": "password123"},
    {"username": "fiona_tech", "email": "fiona@example.com", "password": "password123"},
    {"username": "george_uk", "email": "george@example.com", "password": "password123"},
    {"username": "admin_test", "email": "admin@example.com", "password": "adminpass123", "role": "admin"},
]

MOCK_STORY_TITLES = [
    "Breaking: Major Technology Company Announces Revolutionary AI Platform",
    "Scientists Discover New Species in Amazon Rainforest Expedition",
    "Global Markets React to Central Bank Interest Rate Decision",
    "Climate Summit Reaches Historic Agreement on Carbon Emissions",
    "Sports: Underdog Team Clinches Championship in Dramatic Finale",
    "Health Experts Warn About Rising Cases of Seasonal Illness",
    "Entertainment: Award-Winning Director Announces New Film Project",
    "Political Leaders Meet for International Security Conference",
    "Tech Startup Raises Record Funding for Clean Energy Solution",
    "Education Report Shows Significant Changes in Student Performance",
    "Local Community Celebrates Grand Opening of New Cultural Center",
    "Transportation Authority Unveils Plans for Infrastructure Upgrade",
    "Financial Analysts Predict Economic Trends for Coming Quarter",
    "Research Team Makes Breakthrough in Medical Treatment Development",
    "Environmental Group Launches Campaign to Protect Marine Wildlife",
    "Business Leaders Discuss Future of Remote Work at Annual Summit",
    "Space Agency Announces Mission Timeline for Lunar Exploration",
    "Agriculture Sector Faces Challenges From Changing Weather Patterns",
    "New Study Reveals Impact of Social Media on Mental Health",
    "Government Proposes New Regulations for Digital Privacy Protection",
    "Urban Planning Experts Debate Solutions for Housing Affordability",
    "International Trade Agreement Opens New Market Opportunities",
    "Technology Conference Showcases Latest Innovation in Robotics",
    "Healthcare System Implements New Patient Care Protocol",
    "Energy Companies Invest in Renewable Infrastructure Projects",
    "Cultural Festival Attracts Record Number of International Visitors",
    "Scientific Community Debates Ethics of Emerging Technologies",
    "Legal Experts Analyze Implications of Supreme Court Ruling",
    "Manufacturing Industry Reports Strong Growth in Export Numbers",
    "Tourism Sector Recovers as Travel Restrictions Ease Globally",
]

MOCK_DESCRIPTIONS = [
    "In a significant development that could reshape the industry, experts weigh in on the implications.",
    "The announcement comes after months of speculation and marks a turning point for stakeholders.",
    "Industry observers note that this development reflects broader trends in the global landscape.",
    "Sources familiar with the matter indicate that further announcements may follow in coming weeks.",
    "Analysts suggest this move could have far-reaching consequences for related sectors.",
    "The decision has been met with mixed reactions from various stakeholder groups.",
    "Experts emphasize the importance of understanding the full context of these developments.",
    "This marks a significant shift from previous approaches and signals new priorities.",
    "The impact of this development is expected to be felt across multiple regions.",
    "Observers note that this aligns with recent trends in the broader ecosystem.",
]

MOCK_TAGS = [
    "technology", "science", "politics", "economy", "health", "sports", "entertainment",
    "environment", "education", "business", "finance", "innovation", "research",
    "climate", "security", "international", "local", "culture", "society", "digital",
    "energy", "transportation", "healthcare", "industry", "markets", "policy",
    "development", "community", "infrastructure", "sustainability",
]

MOCK_COMMENTS = [
    "This is really interesting! Thanks for sharing.",
    "I'm not sure I agree with this perspective.",
    "Great article, very informative.",
    "Can anyone provide more context on this?",
    "This confirms what I've been thinking for a while.",
    "I'd like to see more coverage on this topic.",
    "The implications of this are significant.",
    "Has anyone else noticed this trend?",
    "I think the analysis here is spot on.",
    "This deserves more attention from mainstream media.",
    "Interesting take, but I have some reservations.",
    "Well written and thoroughly researched.",
    "I wonder how this will affect us locally.",
    "This is exactly the kind of journalism we need.",
    "I have a different perspective on this issue.",
    "Looking forward to following this story.",
    "The data presented here is compelling.",
    "I'd recommend reading the original source too.",
    "This raises some important questions.",
    "Thank you for covering this topic.",
]

MOCK_REPLY_COMMENTS = [
    "I see your point, but have you considered...",
    "Exactly! I was thinking the same thing.",
    "That's a fair point, thanks for sharing.",
    "I respectfully disagree with your assessment.",
    "You make some valid arguments here.",
    "Thanks for the additional context!",
    "I hadn't thought about it that way before.",
    "Could you elaborate on that?",
    "That's an interesting perspective.",
    "I think we're on the same page here.",
]

NOTIFICATION_TYPES = [
    "new_comment", "comment_reply", "comment_reaction",
    "friend_request", "friend_accepted", "mentions",
]


# ============================================================================
# Helper Functions
# ============================================================================

def random_date_within_days(days: int) -> datetime:
    """Generate a random datetime within the past N days."""
    now = datetime.utcnow()
    random_days = random.uniform(0, days)
    return now - timedelta(days=random_days)


def get_existing_categories_and_publishers(country: str = None, category_name: str = None):
    """Fetch existing categories and publishers from the database."""
    query = models.Category.query
    if category_name:
        # Filter to exact category name
        query = query.filter(models.Category.name == category_name)
    elif country:
        query = query.filter(models.Category.name.like(f"{country}_%"))

    categories = query.all()

    if categories:
        category_ids = [c.id for c in categories]
        publishers = models.Publisher.query.filter(models.Publisher.category_id.in_(category_ids)).all()
    else:
        publishers = []

    return categories, publishers


# ============================================================================
# Mock Data Creation Functions
# ============================================================================

def create_mock_users() -> list:
    """Create mock users with proper encryption and hashing (bulk insert)."""
    print("\n[1/10] Creating mock users...")

    # Pre-compute fingerprints and fetch existing users in bulk
    user_fingerprints = {
        user_data["username"]: hashing_util.generate_hmac_signature(
            user_data["email"], as_bytes=True
        )
        for user_data in MOCK_USERS
    }

    existing_usernames = {
        u.username for u in models.User.query.filter(
            models.User.username.in_([u["username"] for u in MOCK_USERS])
        ).all()
    }

    existing_fingerprints = {
        bytes(u.email_fingerprint) for u in models.User.query.filter(
            models.User.email_fingerprint.in_(list(user_fingerprints.values()))
        ).all()
    }

    # Build list of new users to insert
    new_users = []
    skipped = 0

    for user_data in MOCK_USERS:
        fingerprint = user_fingerprints[user_data["username"]]

        if user_data["username"] in existing_usernames or fingerprint in existing_fingerprints:
            skipped += 1
            continue

        new_user = models.User(
            public_id=security_util.generate_uuid_bytes(),
            username=user_data["username"],
            email_encrypted=security_util.encrypt(user_data["email"]),
            email_fingerprint=fingerprint,
            password=hashing_util.string_to_argon2_hash(user_data["password"]),
            is_enabled=True,
            role=user_data.get("role", "user"),
            display_name=user_data["username"].replace("_", " ").title(),
            profile_description=f"Hi, I'm {user_data['username']}! This is a test account.",
            created_at=random_date_within_days(90),
        )
        new_users.append(new_user)

    # Bulk insert
    if new_users:
        try:
            db.session.add_all(new_users)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            print("   ERROR: Bulk insert failed, falling back to individual inserts")
            for user in new_users:
                try:
                    db.session.add(user)
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    skipped += 1

    # Fetch all mock users (including previously existing ones)
    all_users = models.User.query.filter(
        models.User.username.in_([u["username"] for u in MOCK_USERS])
    ).all()

    print(f"   Created: {len(new_users)}, Skipped: {skipped}")
    return all_users


def create_mock_stories(categories: list, publishers: list) -> list:
    """Create mock stories with unique URL hashes (bulk insert)."""
    print("\n[2/10] Creating mock stories...")
    target_count = 100

    if not categories or not publishers:
        print("   ERROR: No categories or publishers found. Run insert_feeds_to_database.py first.")
        return []

    # Pre-generate URLs and hashes
    story_data = []
    for i in range(target_count):
        fake_url = f"https://example-news.com/article/{i + 1}-{random.randint(10000, 99999)}"
        url_hash = hashing_util.string_to_md5_binary(fake_url)
        story_data.append((fake_url, url_hash))

    # Fetch existing stories by url_hash in bulk
    url_hashes = [h for _, h in story_data]
    existing_hashes = {
        bytes(s.url_hash) for s in models.Story.query.filter(
            models.Story.url_hash.in_(url_hashes)
        ).all()
    }

    # Build publisher lookup by category for efficiency
    publishers_by_category = {}
    for p in publishers:
        if p.category_id not in publishers_by_category:
            publishers_by_category[p.category_id] = []
        publishers_by_category[p.category_id].append(p)

    # Build list of new stories
    new_stories = []
    skipped = 0

    for fake_url, url_hash in story_data:
        if url_hash in existing_hashes:
            skipped += 1
            continue

        category = random.choice(categories)
        matching_publishers = publishers_by_category.get(category.id, [])
        publisher = random.choice(matching_publishers) if matching_publishers else random.choice(publishers)

        title = random.choice(MOCK_STORY_TITLES)
        if random.random() > 0.5:
            title = f"{title} - Update {random.randint(1, 100)}"

        new_story = models.Story(
            title=title[:250],
            description=random.choice(MOCK_DESCRIPTIONS),
            url=fake_url,
            url_hash=url_hash,
            author=f"Mock Author {random.randint(1, 20)}",
            lang=random.choice(["en", "pt", "es"]),
            pub_date=random_date_within_days(30),
            has_image=True,
            category_id=category.id,
            publisher_id=publisher.id,
            created_at=random_date_within_days(30),
        )
        new_stories.append(new_story)

    # Bulk insert
    if new_stories:
        try:
            db.session.add_all(new_stories)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            print("   ERROR: Bulk insert failed, falling back to individual inserts")
            for story in new_stories:
                try:
                    db.session.add(story)
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    skipped += 1

    # Fetch all mock stories (including previously existing ones)
    all_stories = models.Story.query.filter(
        models.Story.url_hash.in_(url_hashes)
    ).all()

    print(f"   Created: {len(new_stories)}, Skipped: {skipped}")
    return all_stories


def create_mock_tags(stories: list) -> int:
    """Create mock tags for stories (bulk insert)."""
    print("\n[3/10] Creating mock tags...")

    if not stories:
        print("   No stories to tag.")
        return 0

    # Get story IDs
    story_ids = [s.id for s in stories]

    # Fetch existing tags for these stories in bulk
    existing_tags = models.Tag.query.filter(models.Tag.story_id.in_(story_ids)).all()
    existing_pairs = {(t.story_id, t.tag) for t in existing_tags}

    # Build list of new tags
    new_tags = []
    skipped = 0

    for story in stories:
        num_tags = random.randint(2, 4)
        selected_tags = random.sample(MOCK_TAGS, min(num_tags, len(MOCK_TAGS)))

        for tag_text in selected_tags:
            if (story.id, tag_text) in existing_pairs:
                skipped += 1
                continue

            new_tags.append(models.Tag(story_id=story.id, tag=tag_text))
            existing_pairs.add((story.id, tag_text))  # Avoid duplicates within batch

    # Bulk insert
    if new_tags:
        try:
            db.session.add_all(new_tags)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            print("   ERROR: Bulk insert failed, falling back to individual inserts")
            created = 0
            for tag in new_tags:
                try:
                    db.session.add(tag)
                    db.session.commit()
                    created += 1
                except IntegrityError:
                    db.session.rollback()
                    skipped += 1
            print(f"   Created: {created}, Skipped: {skipped}")
            return created

    print(f"   Created: {len(new_tags)}, Skipped: {skipped}")
    return len(new_tags)


def create_mock_story_stats(stories: list) -> int:
    """Create mock statistics for stories (bulk insert)."""
    print("\n[4/10] Creating mock story stats...")

    if not stories:
        print("   No stories for stats.")
        return 0

    # Get story IDs
    story_ids = [s.id for s in stories]

    # Fetch existing stats in bulk
    existing_stats = models.StoryStats.query.filter(
        models.StoryStats.story_id.in_(story_ids)
    ).all()
    existing_story_ids = {s.story_id for s in existing_stats}

    # Build list of new stats
    new_stats = []
    skipped = 0

    for story in stories:
        if story.id in existing_story_ids:
            skipped += 1
            continue

        new_stats.append(models.StoryStats(
            story_id=story.id,
            views=random.randint(10, 5000),
            likes=random.randint(0, 200),
            dislikes=random.randint(0, 50),
        ))

    # Bulk insert
    if new_stats:
        try:
            db.session.add_all(new_stats)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            print("   ERROR: Bulk insert failed, falling back to individual inserts")
            created = 0
            for stat in new_stats:
                try:
                    db.session.add(stat)
                    db.session.commit()
                    created += 1
                except IntegrityError:
                    db.session.rollback()
                    skipped += 1
            print(f"   Created: {created}, Skipped: {skipped}")
            return created

    print(f"   Created: {len(new_stats)}, Skipped: {skipped}")
    return len(new_stats)


def create_mock_comments(users: list, stories: list) -> list:
    """Create mock comments with threaded replies (bulk insert)."""
    print("\n[5/10] Creating mock comments...")
    target_top_level = 100
    target_replies = 50

    if not users or not stories:
        print("   ERROR: No users or stories available.")
        return []

    # Pre-compute page hashes and URLs for stories
    story_page_data = {}
    for story in stories:
        public_id = story.get_public_id()
        story_page_data[story.id] = {
            "page_hash": hashing_util.string_to_md5_binary(f"/story/{public_id}"),
            "url": f"/story/{public_id}",
        }

    # Build top-level comments
    top_level_comments = []
    for _ in range(target_top_level):
        story = random.choice(stories)
        user = random.choice(users)
        page_data = story_page_data[story.id]

        top_level_comments.append(models.Comment(
            page_hash=page_data["page_hash"],
            user_id=user.id,
            story_id=story.id,
            content=random.choice(MOCK_COMMENTS),
            url=page_data["url"],
            created_at=random_date_within_days(20),
        ))

    # Bulk insert top-level comments
    skipped = 0
    if top_level_comments:
        try:
            db.session.add_all(top_level_comments)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            print("   ERROR: Bulk insert of top-level comments failed")
            skipped += len(top_level_comments)
            top_level_comments = []

    # Build replies (need IDs from top-level comments)
    reply_comments = []
    if top_level_comments:
        for _ in range(target_replies):
            parent = random.choice(top_level_comments)
            user = random.choice(users)

            reply_comments.append(models.Comment(
                page_hash=parent.page_hash,
                user_id=user.id,
                story_id=parent.story_id,
                parent_id=parent.id,
                content=random.choice(MOCK_REPLY_COMMENTS),
                url=parent.url,
                created_at=random_date_within_days(15),
            ))

        # Bulk insert replies
        if reply_comments:
            try:
                db.session.add_all(reply_comments)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                print("   ERROR: Bulk insert of replies failed")
                skipped += len(reply_comments)
                reply_comments = []

    all_comments = top_level_comments + reply_comments
    print(f"   Created: {len(all_comments)}, Skipped: {skipped}")
    return all_comments


def create_mock_comment_stats(comments: list) -> int:
    """Create mock statistics for comments (bulk insert)."""
    print("\n[6/10] Creating mock comment stats...")

    if not comments:
        print("   No comments for stats.")
        return 0

    # Get comment IDs
    comment_ids = [c.id for c in comments]

    # Fetch existing stats in bulk
    existing_stats = models.CommentStats.query.filter(
        models.CommentStats.comment_id.in_(comment_ids)
    ).all()
    existing_comment_ids = {s.comment_id for s in existing_stats}

    # Build list of new stats
    new_stats = []
    skipped = 0

    for comment in comments:
        if comment.id in existing_comment_ids:
            skipped += 1
            continue

        new_stats.append(models.CommentStats(
            comment_id=comment.id,
            likes=random.randint(0, 50),
            dislikes=random.randint(0, 10),
        ))

    # Bulk insert
    if new_stats:
        try:
            db.session.add_all(new_stats)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            print("   ERROR: Bulk insert failed, falling back to individual inserts")
            created = 0
            for stat in new_stats:
                try:
                    db.session.add(stat)
                    db.session.commit()
                    created += 1
                except IntegrityError:
                    db.session.rollback()
                    skipped += 1
            print(f"   Created: {created}, Skipped: {skipped}")
            return created

    print(f"   Created: {len(new_stats)}, Skipped: {skipped}")
    return len(new_stats)


def create_mock_reactions(users: list, stories: list, comments: list) -> tuple:
    """Create mock reactions for stories and comments (bulk insert)."""
    print("\n[7/10] Creating mock reactions...")
    skipped = 0

    if not users:
        print("   ERROR: No users available.")
        return 0, 0

    # Fetch existing story reactions in bulk
    existing_story_reactions = models.StoryReaction.query.all()
    existing_story_pairs = {(r.story_id, r.user_id, r.action) for r in existing_story_reactions}

    # Build story reactions (~200)
    new_story_reactions = []
    for _ in range(200):
        user = random.choice(users)
        story = random.choice(stories)
        action = random.choice(["like", "dislike"])

        key = (story.id, user.id, action)
        if key in existing_story_pairs:
            skipped += 1
            continue

        new_story_reactions.append(models.StoryReaction(
            story_id=story.id,
            user_id=user.id,
            action=action,
            created_at=random_date_within_days(25),
        ))
        existing_story_pairs.add(key)  # Avoid duplicates within batch

    # Bulk insert story reactions
    if new_story_reactions:
        try:
            db.session.add_all(new_story_reactions)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            print("   ERROR: Bulk insert of story reactions failed")
            new_story_reactions = []

    # Fetch existing comment reactions in bulk
    existing_comment_reactions = models.CommentReaction.query.all()
    existing_comment_pairs = {(r.comment_id, r.user_id) for r in existing_comment_reactions}

    # Build comment reactions (~100)
    new_comment_reactions = []
    if comments:
        for _ in range(100):
            user = random.choice(users)
            comment = random.choice(comments)
            action = random.choice(["like", "dislike"])

            key = (comment.id, user.id)
            if key in existing_comment_pairs:
                skipped += 1
                continue

            new_comment_reactions.append(models.CommentReaction(
                comment_id=comment.id,
                user_id=user.id,
                action=action,
                created_at=random_date_within_days(15),
            ))
            existing_comment_pairs.add(key)  # Avoid duplicates within batch

        # Bulk insert comment reactions
        if new_comment_reactions:
            try:
                db.session.add_all(new_comment_reactions)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                print("   ERROR: Bulk insert of comment reactions failed")
                new_comment_reactions = []

    print(f"   Story reactions: {len(new_story_reactions)}, Comment reactions: {len(new_comment_reactions)}, Skipped: {skipped}")
    return len(new_story_reactions), len(new_comment_reactions)


def create_mock_friendships(users: list) -> list:
    """Create mock friendships between users (bulk insert)."""
    print("\n[8/10] Creating mock friendships...")
    target = 30

    if len(users) < 2:
        print("   ERROR: Need at least 2 users to create friendships.")
        return []

    # Fetch existing friendships in bulk
    existing_friendships = models.Friendship.query.all()
    existing_pairs = set()
    for f in existing_friendships:
        existing_pairs.add((f.user_id, f.friend_id))
        existing_pairs.add((f.friend_id, f.user_id))

    # Build list of new friendships
    new_friendships = []
    skipped = 0
    attempts = 0
    max_attempts = target * 3

    while len(new_friendships) < target and attempts < max_attempts:
        attempts += 1
        user1, user2 = random.sample(users, 2)

        # Check both directions
        if (user1.id, user2.id) in existing_pairs:
            skipped += 1
            continue

        status = random.choice(["pending", "accepted", "accepted", "accepted"])  # Bias toward accepted
        accepted_at = datetime.utcnow() if status == "accepted" else None

        new_friendships.append(models.Friendship(
            user_id=user1.id,
            friend_id=user2.id,
            status=status,
            accepted_at=accepted_at,
            created_at=random_date_within_days(60),
        ))

        # Mark both directions as used
        existing_pairs.add((user1.id, user2.id))
        existing_pairs.add((user2.id, user1.id))

    # Bulk insert
    if new_friendships:
        try:
            db.session.add_all(new_friendships)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            print("   ERROR: Bulk insert failed, falling back to individual inserts")
            created = []
            for friendship in new_friendships:
                try:
                    db.session.add(friendship)
                    db.session.commit()
                    created.append(friendship)
                except IntegrityError:
                    db.session.rollback()
                    skipped += 1
            print(f"   Created: {len(created)}, Skipped: {skipped}")
            return created

    print(f"   Created: {len(new_friendships)}, Skipped: {skipped}")
    return new_friendships


def create_mock_notifications(users: list, comments: list, friendships: list) -> int:
    """Create mock notifications for users (bulk insert)."""
    print("\n[9/10] Creating mock notifications...")
    target = 50

    if not users:
        print("   ERROR: No users available.")
        return 0

    # Build list of notifications
    new_notifications = []

    for _ in range(target):
        user = random.choice(users)
        notif_type = random.choice(NOTIFICATION_TYPES)

        # Build notification based on type
        comment_id = None
        friendship_id = None
        message = ""
        url = None

        if notif_type in ("new_comment", "comment_reply", "comment_reaction") and comments:
            comment = random.choice(comments)
            comment_id = comment.id
            message = "New activity on a comment"
            url = comment.url
        elif notif_type in ("friend_request", "friend_accepted") and friendships:
            friendship = random.choice(friendships)
            friendship_id = friendship.id
            other_user = friendship.user if friendship.friend_id == user.id else friendship.friend
            message = f"{other_user.username} sent you a friend request" if notif_type == "friend_request" else f"{other_user.username} accepted your friend request"
            url = f"/user/{other_user.username}"
        else:
            message = "You were mentioned in a discussion"
            url = "/notifications"

        new_notifications.append(models.Notification(
            user_id=user.id,
            type=notif_type,
            comment_id=comment_id,
            friendship_id=friendship_id,
            message=message[:100],
            url=url,
            is_read=random.choice([True, False]),
            created_at=random_date_within_days(14),
        ))

    # Bulk insert
    skipped = 0
    if new_notifications:
        try:
            db.session.add_all(new_notifications)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            print("   ERROR: Bulk insert failed, falling back to individual inserts")
            created = 0
            for notif in new_notifications:
                try:
                    db.session.add(notif)
                    db.session.commit()
                    created += 1
                except IntegrityError:
                    db.session.rollback()
                    skipped += 1
            print(f"   Created: {created}, Skipped: {skipped}")
            return created

    print(f"   Created: {len(new_notifications)}, Skipped: {skipped}")
    return len(new_notifications)


def create_mock_bookmarks_messages_views(users: list, stories: list) -> tuple:
    """Create mock bookmarks, messages, and story views (bulk insert)."""
    print("\n[10/10] Creating mock bookmarks, messages, and story views...")
    skipped = 0

    if not users or not stories:
        print("   ERROR: No users or stories available.")
        return 0, 0, 0

    # Fetch existing bookmarks in bulk
    existing_bookmarks = models.Bookmark.query.all()
    existing_bookmark_pairs = {(b.user_id, b.story_id) for b in existing_bookmarks}

    # Build bookmarks (~40)
    new_bookmarks = []
    for _ in range(40):
        user = random.choice(users)
        story = random.choice(stories)

        key = (user.id, story.id)
        if key in existing_bookmark_pairs:
            skipped += 1
            continue

        new_bookmarks.append(models.Bookmark(
            user_id=user.id,
            story_id=story.id,
            created_at=random_date_within_days(30),
        ))
        existing_bookmark_pairs.add(key)  # Avoid duplicates within batch

    # Bulk insert bookmarks
    if new_bookmarks:
        try:
            db.session.add_all(new_bookmarks)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            print("   ERROR: Bulk insert of bookmarks failed")
            new_bookmarks = []

    # Build messages (~30)
    new_messages = []
    if len(users) >= 2:
        for _ in range(30):
            sender, receiver = random.sample(users, 2)
            content = f"Mock message content {random.randint(1000, 9999)}"

            new_messages.append(models.Message(
                sender_id=sender.id,
                receiver_id=receiver.id,
                content_encrypted=content,  # In dev, just store as plain text
                timestamp=random_date_within_days(14),
            ))

        # Bulk insert messages
        if new_messages:
            try:
                db.session.add_all(new_messages)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                print("   ERROR: Bulk insert of messages failed")
                new_messages = []

    # Build story views (~100)
    new_views = []
    for _ in range(100):
        user = random.choice(users)
        story = random.choice(stories)

        new_views.append(models.UserStoryView(
            user_id=user.id,
            story_id=story.id,
            viewed_at=random_date_within_days(20),
        ))

    # Bulk insert views
    if new_views:
        try:
            db.session.add_all(new_views)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            print("   ERROR: Bulk insert of views failed")
            new_views = []

    print(f"   Bookmarks: {len(new_bookmarks)}, Messages: {len(new_messages)}, Views: {len(new_views)}, Skipped: {skipped}")
    return len(new_bookmarks), len(new_messages), len(new_views)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main function to orchestrate mock data creation."""
    args = parse_args()

    print("=" * 60)
    print("Mock Data Generator for Development Database")
    print("=" * 60)
    print(f"Environment: {flask_env}")

    if args.country:
        print(f'Filtering to country {args.country}')
    
    if args.category:
        print(f'Filterinf to category: {args.category}')
    
    print(f"Started at: {datetime.utcnow().isoformat()}")

    with app.app_context():
        # Check prerequisites
        categories, publishers = get_existing_categories_and_publishers(country=args.country, category_name=args.category)
        if not categories or not publishers:
            print("\nERROR: No categories or publishers found in database.")
            print("Please run 'python -m utils.extra.insert_feeds_to_database' first.")
            sys.exit(1)

        print(f"\nFound {len(categories)} categories and {len(publishers)} publishers.")

        # Create mock data in order
        users = create_mock_users()
        stories = create_mock_stories(categories, publishers)
        create_mock_tags(stories)
        create_mock_story_stats(stories)
        comments = create_mock_comments(users, stories)
        create_mock_comment_stats(comments)
        create_mock_reactions(users, stories, comments)
        friendships = create_mock_friendships(users)
        create_mock_notifications(users, comments, friendships)
        create_mock_bookmarks_messages_views(users, stories)

        # Summary
        print("\n" + "=" * 60)
        print("Mock Data Generation Complete!")
        print("=" * 60)
        print("\nTest User Credentials:")
        print("-" * 40)
        for user_data in MOCK_USERS[:5]:
            print(f"  {user_data['email']} / {user_data['password']}")
        print(f"  ... and {len(MOCK_USERS) - 5} more users")
        print(f"\nAdmin account: admin@example.com / adminpass123")
        print("=" * 60)


if __name__ == "__main__":
    main()
