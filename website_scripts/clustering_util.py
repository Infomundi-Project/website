"""
Story clustering utilities for grouping related news stories.

This module provides functions to cluster news stories about the same event
from different countries and sources.
"""
from datetime import datetime, timedelta
from collections import Counter
from typing import List, Dict, Optional, Set

from sqlalchemy import func, desc

from . import models, extensions, hashing_util, scripts


# Configuration
CLUSTER_TIME_WINDOW_HOURS = 48
MIN_TAG_OVERLAP = 2
MIN_TITLE_SIMILARITY = 0.60
MAX_CLUSTER_SIZE = 50


def compute_tag_overlap(tags1: Set[str], tags2: Set[str]) -> int:
    """Count overlapping tags between two sets."""
    return len(tags1 & tags2)


def get_story_tags(story: models.Story) -> Set[str]:
    """Extract tag strings from a story as lowercase set."""
    return {tag.tag.lower() for tag in story.tags}


def get_country_code(story: models.Story) -> str:
    """Extract country code from story's category name."""
    if story.category and story.category.name:
        return story.category.name.split("_")[0].upper()
    return "XX"


def find_candidate_stories(
    story: models.Story,
    time_window_hours: int = CLUSTER_TIME_WINDOW_HOURS
) -> List[models.Story]:
    """
    Find stories within time window that share tags with the given story.
    Excludes stories from the same publisher to ensure diversity.
    """
    story_tags = get_story_tags(story)
    if len(story_tags) < MIN_TAG_OVERLAP:
        return []

    cutoff_start = story.pub_date - timedelta(hours=time_window_hours)
    cutoff_end = story.pub_date + timedelta(hours=time_window_hours)

    # Find story IDs with matching tags (at least MIN_TAG_OVERLAP matches)
    matching_story_ids = (
        extensions.db.session.query(models.Tag.story_id)
        .filter(
            func.lower(models.Tag.tag).in_(story_tags),
            models.Tag.story_id != story.id
        )
        .group_by(models.Tag.story_id)
        .having(func.count(models.Tag.id) >= MIN_TAG_OVERLAP)
        .subquery()
    )

    # Get candidate stories from different publishers within time window
    candidates = (
        models.Story.query
        .filter(
            models.Story.id.in_(matching_story_ids),
            models.Story.pub_date >= cutoff_start,
            models.Story.pub_date <= cutoff_end,
            models.Story.publisher_id != story.publisher_id  # Different source
        )
        .all()
    )

    return candidates


def calculate_story_similarity(story1: models.Story, story2: models.Story) -> float:
    """
    Calculate similarity between two stories using title and tag overlap.
    Returns a score between 0 and 1.
    """
    # Title similarity using existing function (returns 0-100)
    title_sim = scripts.string_similarity(
        story1.title.lower(),
        story2.title.lower()
    ) / 100.0

    # Tag overlap ratio
    tags1 = get_story_tags(story1)
    tags2 = get_story_tags(story2)
    tag_union = tags1 | tags2
    tag_overlap = compute_tag_overlap(tags1, tags2)
    tag_sim = tag_overlap / len(tag_union) if tag_union else 0

    # Weighted average (title more important)
    return (0.6 * title_sim) + (0.4 * tag_sim)


def find_or_create_cluster(story: models.Story) -> Optional[models.StoryCluster]:
    """
    Find an existing cluster for a story or create a new one if matches found.
    Returns the cluster if story was added, None otherwise.
    """
    # Check if story is already in a cluster
    existing_membership = models.StoryClusterMember.query.filter_by(
        story_id=story.id
    ).first()
    if existing_membership:
        return existing_membership.cluster

    # Find candidate stories
    candidates = find_candidate_stories(story)

    # Find best matches based on similarity threshold
    matches = []
    for candidate in candidates:
        similarity = calculate_story_similarity(story, candidate)
        if similarity >= MIN_TITLE_SIMILARITY:
            matches.append((candidate, similarity))

    if not matches:
        return None

    # Sort by similarity (highest first)
    matches.sort(key=lambda x: x[1], reverse=True)

    # Check if any match is already in a cluster
    for matched_story, similarity in matches:
        existing = models.StoryClusterMember.query.filter_by(
            story_id=matched_story.id
        ).first()
        if existing:
            # Add to existing cluster if not at capacity
            cluster = existing.cluster
            if cluster.story_count < MAX_CLUSTER_SIZE:
                add_story_to_cluster(cluster, story, similarity)
                return cluster

    # Create new cluster with the best match
    best_match, best_similarity = matches[0]
    cluster = create_cluster([story, best_match], [1.0, best_similarity])

    return cluster


def create_cluster(
    stories: List[models.Story],
    similarities: List[float]
) -> models.StoryCluster:
    """Create a new cluster with the given stories."""
    # Sort stories by pub_date to find representative (earliest)
    sorted_stories = sorted(stories, key=lambda s: s.pub_date)
    representative = sorted_stories[0]

    # Compute dominant tags
    all_tags = []
    for s in stories:
        all_tags.extend(get_story_tags(s))
    tag_counts = Counter(all_tags)
    dominant_tags = [tag for tag, _ in tag_counts.most_common(5)]

    # Get unique country codes
    country_codes = {get_country_code(s) for s in stories}

    # Create cluster hash from dominant tags and representative pub_date
    hash_input = f"{'-'.join(sorted(dominant_tags))}-{representative.pub_date.isoformat()}"
    cluster_hash = hashing_util.string_to_md5_binary(hash_input)

    # Check if cluster with this hash already exists (edge case)
    existing_cluster = models.StoryCluster.query.filter_by(
        cluster_hash=cluster_hash
    ).first()
    if existing_cluster:
        # Add stories to existing cluster instead
        for story, similarity in zip(stories, similarities):
            if not models.StoryClusterMember.query.filter_by(
                cluster_id=existing_cluster.id, story_id=story.id
            ).first():
                add_story_to_cluster(existing_cluster, story, similarity)
        return existing_cluster

    cluster = models.StoryCluster(
        cluster_hash=cluster_hash,
        representative_story_id=representative.id,
        dominant_tags=dominant_tags,
        story_count=len(stories),
        country_count=len(country_codes),
        first_pub_date=min(s.pub_date for s in stories),
        last_pub_date=max(s.pub_date for s in stories),
    )
    extensions.db.session.add(cluster)
    extensions.db.session.flush()

    # Add members
    for story, similarity in zip(stories, similarities):
        member = models.StoryClusterMember(
            cluster_id=cluster.id,
            story_id=story.id,
            similarity_score=similarity,
        )
        extensions.db.session.add(member)

    extensions.db.session.commit()
    return cluster


def add_story_to_cluster(
    cluster: models.StoryCluster,
    story: models.Story,
    similarity: float
) -> None:
    """Add a story to an existing cluster and update cluster stats."""
    # Check if already a member
    if models.StoryClusterMember.query.filter_by(
        cluster_id=cluster.id, story_id=story.id
    ).first():
        return

    member = models.StoryClusterMember(
        cluster_id=cluster.id,
        story_id=story.id,
        similarity_score=similarity,
    )
    extensions.db.session.add(member)

    # Update cluster stats
    cluster.story_count += 1
    cluster.last_pub_date = max(cluster.last_pub_date, story.pub_date)
    cluster.first_pub_date = min(cluster.first_pub_date, story.pub_date)

    # Update country count
    country_codes = set()
    for m in cluster.members:
        country_codes.add(get_country_code(m.story))
    country_codes.add(get_country_code(story))
    cluster.country_count = len(country_codes)

    # Update dominant tags
    all_tags = []
    for m in cluster.members:
        all_tags.extend(get_story_tags(m.story))
    all_tags.extend(get_story_tags(story))
    tag_counts = Counter(all_tags)
    cluster.dominant_tags = [tag for tag, _ in tag_counts.most_common(5)]

    extensions.db.session.commit()


def get_cluster_stories(cluster_id: int) -> Dict[str, List[Dict]]:
    """Get all stories in a cluster, grouped by country code."""
    cluster = extensions.db.session.get(models.StoryCluster, cluster_id)
    if not cluster:
        return {}

    stories_by_country: Dict[str, List[Dict]] = {}
    for member in cluster.members:
        story = member.story
        country_code = get_country_code(story)
        if country_code not in stories_by_country:
            stories_by_country[country_code] = []
        stories_by_country[country_code].append({
            **story.to_dict(),
            "similarity_score": member.similarity_score,
        })

    # Sort stories within each country by pub_date (newest first)
    for country_code in stories_by_country:
        stories_by_country[country_code].sort(
            key=lambda x: x.get("pub_date", ""),
            reverse=True
        )

    return stories_by_country


def get_trending_clusters(
    limit: int = 10,
    min_countries: int = 2,
    min_stories: int = 3,
    max_age_days: int = 7
) -> List[models.StoryCluster]:
    """Get trending clusters based on story count and recency."""
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)

    clusters = (
        models.StoryCluster.query
        .filter(
            models.StoryCluster.country_count >= min_countries,
            models.StoryCluster.story_count >= min_stories,
            models.StoryCluster.last_pub_date >= cutoff,
        )
        .order_by(desc(models.StoryCluster.story_count))
        .limit(limit)
        .all()
    )

    return clusters


def prune_old_clusters(days: int = 7) -> Dict[str, int]:
    """Remove clusters with no recent stories."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    old_clusters = models.StoryCluster.query.filter(
        models.StoryCluster.last_pub_date < cutoff
    ).all()

    deleted_count = len(old_clusters)
    for cluster in old_clusters:
        extensions.db.session.delete(cluster)

    extensions.db.session.commit()
    return {"clusters_deleted": deleted_count}


def cluster_recent_stories(hours: int = 6, batch_size: int = 500) -> Dict[str, int]:
    """
    Cluster stories from the last N hours that aren't already in a cluster.
    Returns statistics about the clustering run.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    # Get stories not yet in clusters
    clustered_story_ids = (
        extensions.db.session.query(models.StoryClusterMember.story_id)
        .subquery()
    )

    unclustered = (
        models.Story.query
        .filter(
            models.Story.id.notin_(clustered_story_ids),
            models.Story.created_at >= cutoff,
        )
        .order_by(desc(models.Story.pub_date))
        .limit(batch_size)
        .all()
    )

    clustered_count = 0
    new_clusters = 0
    errors = 0

    for story in unclustered:
        try:
            cluster = find_or_create_cluster(story)
            if cluster:
                clustered_count += 1
                if cluster.story_count == 2:  # Just created
                    new_clusters += 1
        except Exception:
            errors += 1
            continue

    return {
        "stories_processed": len(unclustered),
        "stories_clustered": clustered_count,
        "new_clusters": new_clusters,
        "errors": errors,
    }
