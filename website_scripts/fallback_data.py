"""
Fallback data for the world feed when database is empty or unavailable.
This ensures the homepage always displays content even during errors.
"""

from datetime import datetime, timedelta


def _days_ago(now: datetime, n: int) -> str:
    """Return an ISO timestamp for n days ago."""
    return (now - timedelta(days=n)).isoformat() + "Z"


def _get_europe_countries(now: datetime) -> list:
    """Return fallback countries for Europe region."""
    return [
        {"code": "FR", "name": "France", "cca2": "FR", "topStories": [
            {"title": "France invests in high-speed rail expansion", "source": "AFP",
             "summary": "New TGV routes will connect major cities with reduced travel times.",
             "url": "#", "published_at": _days_ago(now, 0)},
            {"title": "Paris launches urban cooling program", "source": "Le Monde",
             "summary": "Shaded corridors and misting stations to mitigate heatwaves.",
             "url": "#", "published_at": _days_ago(now, 3)}]},
        {"code": "DE", "name": "Germany", "cca2": "DE", "topStories": [
            {"title": "Germany leads EU renewable energy goals", "source": "DW",
             "summary": "Electricity generation crosses a new renewable benchmark.",
             "url": "#", "published_at": _days_ago(now, 1)}]},
        {"code": "IT", "name": "Italy", "cca2": "IT", "topStories": [
            {"title": "Italy unveils green tourism plan", "source": "ANSA",
             "summary": "Incentives to preserve coastal parks and villages.",
             "url": "#", "published_at": _days_ago(now, 2)}]},
        {"code": "GB", "name": "United Kingdom", "cca2": "GB", "topStories": [
            {"title": "UK announces new tech investment fund", "source": "BBC",
             "summary": "Government backs AI and clean energy startups with major funding.",
             "url": "#", "published_at": _days_ago(now, 1)}]},
        {"code": "ES", "name": "Spain", "cca2": "ES", "topStories": [
            {"title": "Spain expands solar energy capacity", "source": "El País",
             "summary": "New solar farms to power millions of homes across the country.",
             "url": "#", "published_at": _days_ago(now, 2)}]},
    ]


def _get_north_america_countries(now: datetime) -> list:
    """Return fallback countries for North America region."""
    return [
        {"code": "US", "name": "United States", "cca2": "US", "topStories": [
            {"title": "US tech stocks rally after earnings", "source": "Bloomberg",
             "summary": "Major indexes close higher on strong guidance.",
             "url": "#", "published_at": _days_ago(now, 0)},
            {"title": "Federal infrastructure grants announced", "source": "Reuters",
             "summary": "Funding targets bridges and broadband in rural areas.",
             "url": "#", "published_at": _days_ago(now, 2)}]},
        {"code": "CA", "name": "Canada", "cca2": "CA", "topStories": [
            {"title": "Canada expands EV charging network", "source": "CBC",
             "summary": "New coast-to-coast fast chargers planned along Trans-Canada.",
             "url": "#", "published_at": _days_ago(now, 1)}]},
        {"code": "MX", "name": "Mexico", "cca2": "MX", "topStories": [
            {"title": "Mexico City launches air quality initiative", "source": "El Universal",
             "summary": "Low-emission zones to phase in over the next year.",
             "url": "#", "published_at": _days_ago(now, 3)}]},
    ]


def _get_latin_america_countries(now: datetime) -> list:
    """Return fallback countries for Latin America region."""
    return [
        {"code": "BR", "name": "Brazil", "cca2": "BR", "topStories": [
            {"title": "Brazil accelerates Amazon reforestation", "source": "Folha",
             "summary": "Public-private partnerships aim to restore key corridors.",
             "url": "#", "published_at": _days_ago(now, 0)},
            {"title": "São Paulo invests in public transport modernization", "source": "Estadão",
             "summary": "New metro lines and bus corridors planned for the metropolitan area.",
             "url": "#", "published_at": _days_ago(now, 2)}]},
        {"code": "AR", "name": "Argentina", "cca2": "AR", "topStories": [
            {"title": "Argentina announces export incentives", "source": "La Nación",
             "summary": "New measures target agribusiness and lithium.",
             "url": "#", "published_at": _days_ago(now, 2)}]},
        {"code": "CL", "name": "Chile", "cca2": "CL", "topStories": [
            {"title": "Chile expands national park system", "source": "BioBio",
             "summary": "New protected areas designated in Patagonia.",
             "url": "#", "published_at": _days_ago(now, 4)}]},
        {"code": "CO", "name": "Colombia", "cca2": "CO", "topStories": [
            {"title": "Colombia launches digital economy initiative", "source": "El Tiempo",
             "summary": "Government supports tech startups and digital infrastructure.",
             "url": "#", "published_at": _days_ago(now, 1)}]},
    ]


def _get_africa_countries(now: datetime) -> list:
    """Return fallback countries for Africa region."""
    return [
        {"code": "NG", "name": "Nigeria", "cca2": "NG", "topStories": [
            {"title": "Nigeria launches fintech regulatory sandbox", "source": "Punch",
             "summary": "Startups to test products with consumer safeguards.",
             "url": "#", "published_at": _days_ago(now, 0)}]},
        {"code": "ZA", "name": "South Africa", "cca2": "ZA", "topStories": [
            {"title": "Cape Town water resilience plan updated", "source": "News24",
             "summary": "Desalination and reuse projects move forward.",
             "url": "#", "published_at": _days_ago(now, 1)}]},
        {"code": "KE", "name": "Kenya", "cca2": "KE", "topStories": [
            {"title": "Kenya expands mobile money interoperability", "source": "Nation",
             "summary": "Transfers between networks become seamless.",
             "url": "#", "published_at": _days_ago(now, 3)}]},
        {"code": "EG", "name": "Egypt", "cca2": "EG", "topStories": [
            {"title": "Egypt invests in new Suez Canal expansion", "source": "Al-Ahram",
             "summary": "Infrastructure upgrades aim to increase shipping capacity.",
             "url": "#", "published_at": _days_ago(now, 2)}]},
    ]


def _get_asia_countries(now: datetime) -> list:
    """Return fallback countries for Asia region."""
    return [
        {"code": "IN", "name": "India", "cca2": "IN", "topStories": [
            {"title": "India unveils semiconductor cluster incentives", "source": "The Hindu",
             "summary": "States compete to host fab projects.",
             "url": "#", "published_at": _days_ago(now, 0)}]},
        {"code": "JP", "name": "Japan", "cca2": "JP", "topStories": [
            {"title": "Japan tests next-gen wind turbines", "source": "NHK",
             "summary": "Floating platforms deployed off Hokkaido.",
             "url": "#", "published_at": _days_ago(now, 1)}]},
        {"code": "CN", "name": "China", "cca2": "CN", "topStories": [
            {"title": "China announces new high-speed rail link", "source": "Xinhua",
             "summary": "Route will reduce travel time by 40%.",
             "url": "#", "published_at": _days_ago(now, 2)}]},
        {"code": "KR", "name": "South Korea", "cca2": "KR", "topStories": [
            {"title": "South Korea advances AI research initiatives", "source": "Yonhap",
             "summary": "New funding for AI labs and talent development programs.",
             "url": "#", "published_at": _days_ago(now, 1)}]},
        {"code": "SG", "name": "Singapore", "cca2": "SG", "topStories": [
            {"title": "Singapore launches smart city 2.0 initiative", "source": "Straits Times",
             "summary": "New sensors and AI systems to improve urban services.",
             "url": "#", "published_at": _days_ago(now, 3)}]},
    ]


def _get_oceania_countries(now: datetime) -> list:
    """Return fallback countries for Oceania region."""
    return [
        {"code": "AU", "name": "Australia", "cca2": "AU", "topStories": [
            {"title": "Australia expands solar storage rebates", "source": "ABC",
             "summary": "Households to get additional support for batteries.",
             "url": "#", "published_at": _days_ago(now, 0)},
            {"title": "Melbourne announces new public transit expansion", "source": "The Age",
             "summary": "New tram and rail lines planned for the suburbs.",
             "url": "#", "published_at": _days_ago(now, 2)}]},
        {"code": "NZ", "name": "New Zealand", "cca2": "NZ", "topStories": [
            {"title": "New Zealand launches green hydrogen pilot", "source": "RNZ",
             "summary": "Port operations to trial zero-emission equipment.",
             "url": "#", "published_at": _days_ago(now, 3)}]},
    ]


def get_fallback_world_feed() -> dict:
    """Returns fallback news data for all world regions."""
    now = datetime.utcnow()
    return {
        "regions": {
            "Europe": {"countries": _get_europe_countries(now)},
            "North America": {"countries": _get_north_america_countries(now)},
            "Latin America": {"countries": _get_latin_america_countries(now)},
            "Africa": {"countries": _get_africa_countries(now)},
            "Asia": {"countries": _get_asia_countries(now)},
            "Oceania": {"countries": _get_oceania_countries(now)},
        }
    }


def merge_with_fallback(db_result: dict) -> dict:
    """
    Merges database results with fallback data.
    If a region has no countries with stories, uses fallback data for that region.
    """
    fallback = get_fallback_world_feed()

    if not db_result or "regions" not in db_result:
        return fallback

    result = {"regions": {}}
    all_regions = set(db_result.get("regions", {}).keys()) | set(fallback["regions"].keys())

    for region_name in all_regions:
        db_region = db_result.get("regions", {}).get(region_name, {})
        fallback_region = fallback["regions"].get(region_name, {})

        db_countries = db_region.get("countries", [])
        fallback_countries = fallback_region.get("countries", [])

        if db_countries:
            result["regions"][region_name] = {"countries": db_countries}
        elif fallback_countries:
            result["regions"][region_name] = {"countries": fallback_countries}
        else:
            result["regions"][region_name] = {"countries": []}

    return result
