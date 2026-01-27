"""
Background job to cluster recently ingested stories.

Run periodically via cron (recommended: every 30 minutes):
    */30 * * * * cd /home/admin/website && python -m utils.cluster_stories

Or run manually:
    python -m utils.cluster_stories --hours 6 --prune
"""
import argparse
import logging
import os
import sys
from datetime import datetime

# Add the website root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from website_scripts import config

# Setup logging
log_dir = f"{config.WEBSITE_ROOT}/logs"
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    filename=f"{log_dir}/cluster_stories.log",
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_clustering(hours: int = 6, prune: bool = True, batch_size: int = 500) -> dict:
    """
    Run the clustering job within Flask app context.

    Args:
        hours: Number of hours to look back for unclustered stories
        prune: Whether to prune old clusters (> 7 days)
        batch_size: Maximum stories to process per run

    Returns:
        Statistics about the clustering run
    """
    # Import Flask app to get app context
    from app import app
    from website_scripts import clustering_util

    results = {
        "start_time": datetime.utcnow().isoformat(),
        "clustering": {},
        "pruning": {},
        "errors": [],
    }

    with app.app_context():
        # Run clustering
        try:
            logger.info(f"Starting clustering for stories from last {hours} hours...")
            cluster_stats = clustering_util.cluster_recent_stories(
                hours=hours,
                batch_size=batch_size,
            )
            results["clustering"] = cluster_stats
            logger.info(
                f"Clustering complete: {cluster_stats['stories_clustered']} stories "
                f"clustered into {cluster_stats['new_clusters']} new clusters"
            )
        except Exception as e:
            error_msg = f"Clustering error: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg)

        # Prune old clusters
        if prune:
            try:
                logger.info("Pruning old clusters...")
                prune_stats = clustering_util.prune_old_clusters(days=7)
                results["pruning"] = prune_stats
                logger.info(f"Pruning complete: {prune_stats['clusters_deleted']} clusters deleted")
            except Exception as e:
                error_msg = f"Pruning error: {str(e)}"
                results["errors"].append(error_msg)
                logger.error(error_msg)

    results["end_time"] = datetime.utcnow().isoformat()
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Cluster recent news stories from different sources/countries"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=6,
        help="Look back N hours for unclustered stories (default: 6)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Maximum stories to process per run (default: 500)",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        default=True,
        help="Prune old clusters older than 7 days (default: True)",
    )
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="Skip pruning old clusters",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print results to stdout",
    )

    args = parser.parse_args()

    # Run clustering
    results = run_clustering(
        hours=args.hours,
        prune=not args.no_prune,
        batch_size=args.batch_size,
    )

    if args.verbose:
        import json
        print(json.dumps(results, indent=2))

    # Exit with error code if there were errors
    if results["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
