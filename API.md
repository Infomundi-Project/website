# API Reference

Base URL: `/api`

All endpoints return JSON. Errors follow this format:
```json
{
  "success": false,
  "error": {
    "status": "400",
    "title": "Invalid Request",
    "detail": "Description of what went wrong"
  }
}
```

## Authentication

Endpoints marked with 🔒 require authentication (Flask-Login session).

Unauthenticated requests to protected endpoints return `401 Unauthorized`.

---

## Table of Contents

- [Stories](#stories)
- [Comments](#comments)
- [Users](#users)
- [Friends](#friends)
- [Messages](#messages)
- [Notifications](#notifications)
- [Bookmarks](#bookmarks)
- [Two-Factor Authentication](#two-factor-authentication)
- [Blocking & Reporting](#blocking--reporting)
- [Geographic Data](#geographic-data)
- [Financial Data](#financial-data)
- [Miscellaneous](#miscellaneous)

---

## Stories

### Get Trending Stories

```
GET /api/story/trending
```

Returns trending stories based on engagement metrics.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `day` | Time window: `hour`, `day`, `week`, `all` |
| `metric` | string | `views` | Sort by: `views`, `likes`, `dislikes` |
| `limit` | int | 7 | Max results (capped at 15) |
| `country` | string | - | Filter by country ISO2 (e.g., `br`) |
| `category` | string | - | Filter by category slug (e.g., `general`) |
| `author` | string | - | Filter by author name (substring match) |
| `tag` | string | - | Filter by tag |
| `publisher` | string | - | Filter by publisher name (substring match) |

**Rate Limit:** 15/minute

**Response:**
```json
[
  {
    "story_id": "5d41402abc4b2a76b9719d911017c592",
    "title": "Story Title",
    "url": "https://example.com/article",
    "pub_date": "2024-01-15T10:30:00",
    "views": 1250,
    "likes": 45,
    "dislikes": 3,
    "image_url": "https://bucket.infomundi.net/stories/br_general/5d41402abc4b2a76b9719d911017c592.avif",
    "author": "John Doe",
    "tags": ["politics", "economy"],
    "publisher": {
      "name": "Example News",
      "url": "https://example.com",
      "favicon_url": "/static/favicons/example.png"
    }
  }
]
```

---

### Get Homepage Trending

```
GET /api/home/trending
```

Returns up to 10 relevant stories for the homepage (must have images, max 3 per category).

**Rate Limit:** 18/minute

**Response:** Same structure as `/story/trending`, plus:
- `num_comments`: Comment count
- `category`: Category name (e.g., `br_general`)

---

### Get Stories (Paginated)

```
GET /api/get_stories
```

Returns paginated stories for a specific country/category.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `country` | string | `br` | Country ISO2 code |
| `category` | string | `general` | Category slug |
| `page` | int | 1 | Page number |
| `order_by` | string | `pub_date` | Sort field: `views`, `likes`, `comments`, `pub_date` |
| `order_dir` | string | `desc` | Sort direction: `asc`, `desc` |
| `start_date` | string | - | Filter start date (YYYY-MM-DD) |
| `end_date` | string | - | Filter end date (YYYY-MM-DD) |

**Rate Limit:** 20/minute

**Response:**
```json
[
  {
    "story_id": "5d41402abc4b2a76b9719d911017c592",
    "id": 12345,
    "title": "Story Title",
    "tags": ["tag1", "tag2"],
    "author": "Author Name",
    "description": "Story description...",
    "views": 100,
    "likes": 10,
    "dislikes": 2,
    "url": "https://example.com/article",
    "pub_date": "2024-01-15T10:30:00",
    "publisher": {
      "name": "Publisher Name",
      "url": "https://publisher.com",
      "favicon_url": "/static/favicons/pub.png"
    },
    "image_url": "https://bucket.infomundi.net/stories/...",
    "num_comments": 5
  }
]
```

---

### React to Story 🔒

```
POST /api/story/<action>
```

Like or dislike a story. Toggle behavior: calling same action twice removes reaction.

**URL Parameters:**
- `action`: `like` or `dislike`

**Request Body:**
```json
{
  "id": "5d41402abc4b2a76b9719d911017c592"
}
```

> Note: `id` is the story's public ID (MD5 hex of URL), not the internal database ID.

**Rate Limit:** 10/minute

**Response:**
```json
{
  "message": "Story liked",
  "is_liked": true,
  "is_disliked": false,
  "likes": 46,
  "dislikes": 3
}
```

---

### Summarize Story (AI)

```
GET /api/story/summarize/<story_url_hash>
```

Returns an AI-generated summary of the story. Results are cached in database.

**URL Parameters:**
- `story_url_hash`: Story's public ID (MD5 hex)

**Rate Limit:** 120/day, 60/hour, 6/minute

**Response:**
```json
{
  "response": {
    "summary": "Brief summary of the article...",
    "key_points": ["Point 1", "Point 2"],
    "sentiment": "neutral"
  }
}
```

---

### Chat About Story (AI)

```
POST /api/story/chat/<story_url_hash>
```

Have a conversation about a story with AI.

**URL Parameters:**
- `story_url_hash`: Story's public ID (MD5 hex)

**Request Body:**
```json
{
  "message": "What are the main implications of this?",
  "history": [
    {"role": "user", "content": "Previous question"},
    {"role": "assistant", "content": "Previous answer"}
  ]
}
```

**Rate Limit:** 240/day, 120/hour, 20/minute

**Response:**
```json
{
  "response": "Based on the article, the main implications are..."
}
```

---

## Comments

### Create Comment

```
POST /api/comments
```

Create a comment on a story, user profile, or page. Anonymous comments are allowed.

**Request Body:**
```json
{
  "page_id": "5d41402abc4b2a76b9719d911017c592",
  "type": "story",
  "content": "This is my comment",
  "parent_id": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `page_id` | string | Yes | Story hash, user UUID, or page identifier |
| `type` | string | Yes | `story`, `user`, or `page` |
| `content` | string | Yes | Comment text (max 1000 chars, HTML sanitized) |
| `parent_id` | int | No | Parent comment ID for replies |

**Rate Limit:** 120/day, 60/hour, 12/minute

**Response:**
```json
{
  "message": "Comment created",
  "comment_id": 123,
  "comment": "This is my comment"
}
```

---

### Get Comments

```
GET /api/comments/get/<page_id>
```

Get paginated comments for a page.

**URL Parameters:**
- `page_id`: Story hash, user UUID, or page identifier

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `sort` | string | `recent` | Sort order: `recent`, `old`, `best` |
| `search` | string | - | Search within comment content |

**Rate Limit:** 20/minute

**Response:**
```json
{
  "has_more": true,
  "total": 45,
  "comments": [
    {
      "id": 123,
      "content": "Comment text",
      "is_edited": false,
      "is_deleted": false,
      "created_at": "2024-01-15T10:30:00",
      "user": {
        "id": 1,
        "username": "johndoe",
        "avatar_url": "/static/img/avatar.webp"
      },
      "stats": {
        "likes": 5,
        "dislikes": 1
      },
      "replies": []
    }
  ]
}
```

---

### Edit Comment 🔒

```
PUT /api/comments/<comment_id>
```

Edit your own comment.

**Request Body:**
```json
{
  "content": "Updated comment text"
}
```

**Response:**
```json
{
  "content": "Updated comment text",
  "message": "Comment updated.",
  "updated_at": "2024-01-15T11:00:00"
}
```

---

### Delete Comment 🔒

```
DELETE /api/comments/<comment_id>
```

Soft-delete your own comment.

**Response:**
```json
{
  "message": "Comment deleted"
}
```

---

### React to Comment 🔒

```
POST /api/comments/<comment_id>/<action>
```

Like or dislike a comment. Toggle behavior.

**URL Parameters:**
- `comment_id`: Comment ID
- `action`: `like` or `dislike`

**Rate Limit:** 150/hour, 15/minute

**Response:**
```json
{
  "likes": 6,
  "dislikes": 1
}
```

---

## Users

### Get User Reading Stats

```
GET /api/user/<uid>/stats/reading
```

Get reading statistics for a user.

**URL Parameters:**
- `uid`: User's internal ID

**Response:**
```json
{
  "counts": {
    "daily": 5,
    "weekly": 23,
    "monthly": 89
  },
  "top_publishers": [
    {"name": "Example News", "count": 15}
  ],
  "top_tags": [
    {"tag": "politics", "count": 12}
  ],
  "top_countries": [
    {"country": "BR", "count": 45}
  ],
  "daily_counts": [
    {"date": "2024-01-15", "count": 3}
  ]
}
```

---

### Get User Online Status

```
GET /api/user/<user_public_id>/status
```

Check if a user is online.

**URL Parameters:**
- `user_public_id`: User's public UUID string

**Response:**
```json
{
  "is_online": true,
  "last_activity": "2024-01-15T10:30:00"
}
```

---

### Update Online Status 🔒

```
GET /api/user/status/update
```

Update current user's online status (call periodically from frontend).

**Response:**
```json
{
  "message": "Your status has been updated."
}
```

---

### Upload Profile Image 🔒

```
POST /api/user/image/<category>
```

Upload avatar, banner, or wallpaper.

**URL Parameters:**
- `category`: `avatar`, `banner`, or `wallpaper`

**Request:** `multipart/form-data` with file field matching category name.

**Response:**
```json
{
  "success": true
}
```

---

## Friends

### Manage Friendship 🔒

```
POST /api/user/friend
```

Send, accept, reject, or delete friend requests.

**Request Body:**
```json
{
  "friend_id": 123,
  "action": "add"
}
```

| Action | Description |
|--------|-------------|
| `add` | Send friend request |
| `accept` | Accept pending request |
| `reject` | Reject pending request |
| `delete` | Remove existing friend |

**Rate Limit:** 54/hour, 18/minute

**Response:**
```json
{
  "message": "Friend request sent"
}
```

---

### Get Friendship Status 🔒

```
GET /api/user/<user_id>/friend/status
```

Check friendship status with another user.

**Response:**
```json
{
  "status": "accepted",
  "is_sent_by_current_user": true
}
```

Status values: `none`, `pending`, `accepted`, `rejected`

---

### Get Friends List 🔒

```
GET /api/user/friends
```

Get paginated list of friends.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `per_page` | int | 10 | Items per page |

**Response:**
```json
{
  "friends": [
    {
      "username": "janedoe",
      "display_name": "Jane Doe",
      "user_id": 456,
      "avatar_url": "/static/img/avatar.webp",
      "level": 5,
      "is_online": true,
      "last_activity": "2024-01-15T10:30:00"
    }
  ],
  "total_friends": 25,
  "online_friends": 3,
  "page": 1,
  "per_page": 10,
  "total_pages": 3
}
```

---

## Messages

### Get Messages 🔒

```
GET /api/user/<friend_id>/messages
```

Get encrypted message history with a friend (last 50 messages).

**URL Parameters:**
- `friend_id`: Friend's internal user ID

**Response:**
```json
{
  "messages": [
    {
      "id": 789,
      "from": 123,
      "ciphertext": "base64_encrypted_content...",
      "timestamp": "2024-01-15T10:30:00",
      "deliveredAt": "2024-01-15T10:30:01",
      "readAt": "2024-01-15T10:31:00",
      "reply_to": null
    }
  ]
}
```

> Note: Messages are end-to-end encrypted. Server stores only ciphertext.

---

### Update Public Key 🔒

```
POST /api/user/pubkey
```

Update your encryption public key (for E2E encrypted messaging).

**Request Body:**
```json
{
  "publicKey": { "kty": "EC", "crv": "P-256", ... }
}
```

**Response:** `204 No Content`

---

### Get Friend's Public Key 🔒

```
GET /api/user/<friend_id>/pubkey
```

Get a friend's public key for encrypting messages.

**Response:**
```json
{
  "publicKey": { "kty": "EC", "crv": "P-256", ... }
}
```

---

## Notifications

### List Notifications 🔒

```
GET /api/notifications
```

Get paginated notifications.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `per_page` | int | 20 | Items per page |
| `show_read` | string | `true` | Include read notifications |

**Response:**
```json
{
  "notifications": [
    {
      "id": 100,
      "type": "friend_request",
      "message": "johndoe sent you a friend request",
      "url": "/user/abc-123-def",
      "is_read": false,
      "created_at": "2024-01-15T10:30:00",
      "comment_id": null,
      "friendship_id": 50
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 45,
  "pages": 3
}
```

**Notification Types:**
- `friend_request` - New friend request
- `friend_accepted` - Friend request accepted
- `new_comment` - New comment on bookmarked story or profile
- `comment_reply` - Reply to your comment
- `profile_edit` - Profile update confirmation
- `security` - Security-related notifications

---

### Get Unread Count 🔒

```
GET /api/notifications/unread_count
```

**Response:**
```json
{
  "unread_count": 5
}
```

---

### Mark Notification Read 🔒

```
POST /api/notifications/<notification_id>/read
```

**Response:**
```json
{
  "message": "Notification marked as read.",
  "id": 100
}
```

---

### Mark All Read 🔒

```
POST /api/notifications/read_all
```

**Rate Limit:** 5/minute

**Response:**
```json
{
  "message": "All notifications marked as read.",
  "notifications_updated": 5
}
```

---

## Bookmarks

### List Bookmarks 🔒

```
GET /api/bookmark
```

Get all bookmarked stories.

**Response:**
```json
[
  {
    "story_id": "5d41402abc4b2a76b9719d911017c592",
    "title": "Story Title",
    ...
  }
]
```

---

### Add Bookmark 🔒

```
POST /api/bookmark
```

**Request Body:**
```json
{
  "story_id": 12345
}
```

> Note: Uses internal story ID, not public hash.

**Rate Limit:** 100/hour, 20/minute

**Response:**
```json
{
  "message": "Bookmarked!"
}
```

---

### Remove Bookmark 🔒

```
DELETE /api/bookmark/<story_id>
```

**URL Parameters:**
- `story_id`: Internal story ID

**Response:**
```json
{
  "message": "Removed bookmark"
}
```

---

## Two-Factor Authentication

### Generate TOTP Secret 🔒

```
GET /api/totp/generate
```

Generate a new TOTP secret for authenticator app setup.

**Response:**
```json
{
  "secret_key": "JBSWY3DPEHPK3PXP",
  "qr_code": "data:image/png;base64,..."
}
```

---

### Setup TOTP 🔒

```
GET /api/totp/setup?code=123456
```

Verify TOTP code and enable 2FA.

**Query Parameters:**
- `code`: 6-digit TOTP code from authenticator app

**Response (success):**
```json
{
  "valid": true,
  "totp_recovery_token": "abc123xyz..."
}
```

> Important: Save the recovery token! It's shown only once.

**Response (invalid code):**
```json
{
  "valid": false
}
```

---

### Send Email 2FA Code

```
POST /api/2fa/mail/send
```

Send a 2FA code to user's email (used during login flow).

**Rate Limit:** 30/day, 3/minute

**Response:**
```json
{
  "message": "2FA code has been sent to your email."
}
```

---

### Verify Email 2FA Code 🔒

```
POST /api/2fa/mail/verify
```

Verify email-based 2FA code.

**Request Body:**
```json
{
  "code": "123456"
}
```

**Rate Limit:** 10/minute

**Response:**
```json
{
  "message": "2FA code is valid!"
}
```

---

## Blocking & Reporting

### Block/Unblock User 🔒

```
POST /api/user/<uid>/block    # Block user
DELETE /api/user/<uid>/block  # Unblock user
GET /api/user/<uid>/block     # Check block status
```

Blocking a user also removes any existing friendship.

**Response:**
```json
{
  "message": "You blocked johndoe. Take care of your peace!"
}
```

---

### Report User 🔒

```
GET /api/user/<uid>/reports                    # List your reports against user
POST /api/user/<uid>/reports                   # Create report
PATCH /api/user/<uid>/reports/<report_id>      # Update report
DELETE /api/user/<uid>/reports/<report_id>     # Delete report
```

**Request Body (POST/PATCH):**
```json
{
  "category": "harassment",
  "reason": "Description of the issue..."
}
```

**Categories:** `spam`, `harassment`, `hate_speech`, `inappropriate`, `other`

**Response:**
```json
{
  "message": "That's done."
}
```

---

## Geographic Data

### Get Countries 🔒

```
GET /api/countries
```

Returns list of all countries. Cached for 30 days.

---

### Get States 🔒

```
GET /api/countries/<country_id>/states
```

Returns states/provinces for a country. Cached for 30 days.

---

### Get Cities 🔒

```
GET /api/states/<state_id>/cities
```

Returns cities for a state. Cached for 30 days.

---

### Get Country Code

```
GET /api/get_country_code?country=Brazil
```

**Response:**
```json
{
  "countryCode": "BR"
}
```

---

### Autocomplete Countries

```
GET /api/autocomplete?query=bra
```

Returns matching country names (min 2 characters).

**Response:**
```json
["Brazil", "Gibraltar"]
```

---

## Financial Data

### Get Currencies

```
GET /api/currencies
```

Returns currency exchange data. Cached for 30 minutes.

---

### Get Stocks

```
GET /api/stocks
```

Returns stock market data. Cached for 30 minutes.

---

### Get Crypto

```
GET /api/crypto
```

Returns cryptocurrency data. Cached for 30 minutes.

---

## Miscellaneous

### Homepage Dashboard

```
GET /api/home/dashboard
```

Returns aggregated stats for homepage widgets.

**Response:**
```json
{
  "stories_last_7_days": [120, 145, 132, 156, 178, 143, 165],
  "days": ["2024-01-09", "2024-01-10", ...],
  "top_countries": [
    {"country": "BR", "count": 450},
    {"country": "US", "count": 320}
  ],
  "engagement": {
    "likes": 1250,
    "dislikes": 89,
    "comments": 456,
    "shares": 234
  }
}
```

---

### Search

```
POST /api/search
```

Search for a country and redirect to its news page.

**Form Data:**
- `query`: Country name (partial match)

**Response:** Redirects to `/news?country=<iso2>`

---

### Generate CAPTCHA

```
GET /api/captcha
```

Generate a CAPTCHA image for form validation.

**Rate Limit:** 20/minute

**Response:**
```json
{
  "captcha": "data:image/png;base64,..."
}
```

---

## WebSocket Events

The application uses Socket.IO for real-time features. Connect to the main app URL.

### Connection

Requires authentication. On connect, user joins their personal room `user_{id}`.

### Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `send_message` | Client → Server | Send encrypted message to friend |
| `receive_message` | Server → Client | Receive message from friend |
| `typing` | Bidirectional | Typing indicator |
| `message_read` | Client → Server | Mark message as read |

**send_message payload:**
```json
{
  "to": 456,
  "message": "base64_ciphertext...",
  "parent_id": null
}
```

**receive_message payload:**
```json
{
  "from": 123,
  "fromName": "johndoe",
  "message": "base64_ciphertext...",
  "messageId": 789,
  "timestamp": "2024-01-15T10:30:00",
  "deliveredAt": "2024-01-15T10:30:01",
  "reply_to": null
}
```

---

## Error Codes

| Code | Title | Common Causes |
|------|-------|---------------|
| 400 | Invalid Request | Missing parameters, invalid data format |
| 401 | Unauthorized | Not logged in, session expired |
| 403 | Forbidden | No permission for this action |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | Internal error (check logs) |

---

## Rate Limiting

Rate limits are enforced per-IP and noted on each endpoint. When exceeded, you'll receive:

```json
{
  "success": false,
  "error": {
    "status": "429",
    "title": "Too Many Requests",
    "detail": "Your lightning-fast requests have exceeded the rate limit. The limit is: 10 per 1 minute"
  }
}
```

---

## Notes for Developers

### Story IDs

Stories have two IDs:
- **Internal ID** (`id`): Auto-increment integer, used in some endpoints like bookmarks
- **Public ID** (`story_id`): MD5 hex hash of URL, used in most public-facing endpoints

When in doubt, check the endpoint documentation for which ID type is expected.

### User IDs

Similarly, users have:
- **Internal ID** (`id`): Integer, used in friend/message endpoints
- **Public ID**: UUID string, used in profile URLs

### Authentication

The API uses Flask-Login session cookies. For AJAX requests, ensure:
1. Cookies are included (`credentials: 'include'` in fetch)
2. CSRF token is sent for non-GET requests (from cookie or meta tag)

### Caching

Many endpoints are cached (noted in descriptions). If you need fresh data, the cache typically expires within 5-30 minutes depending on the endpoint.
