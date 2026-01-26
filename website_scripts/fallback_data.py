"""
Fallback data for the world feed when database is empty or unavailable.
This ensures the homepage always displays content even during errors.
"""

from datetime import datetime, timedelta


def _days_ago(now: datetime, n: int) -> str:
    """Return an ISO timestamp for n days ago."""
    return (now - timedelta(days=n)).isoformat() + "Z"


# Complete country name mapping for all regions
COUNTRY_NAMES = {
    # North America
    "US": "United States", "CA": "Canada", "MX": "Mexico",
    # Latin America
    "BR": "Brazil", "AR": "Argentina", "CL": "Chile", "CO": "Colombia",
    "PE": "Peru", "VE": "Venezuela", "EC": "Ecuador", "UY": "Uruguay",
    "PY": "Paraguay", "BO": "Bolivia", "CR": "Costa Rica", "PA": "Panama",
    "CU": "Cuba", "DO": "Dominican Republic", "GT": "Guatemala",
    "HN": "Honduras", "NI": "Nicaragua", "SV": "El Salvador",
    # Europe
    "GB": "United Kingdom", "DE": "Germany", "FR": "France", "IT": "Italy",
    "ES": "Spain", "PT": "Portugal", "NL": "Netherlands", "BE": "Belgium",
    "SE": "Sweden", "NO": "Norway", "PL": "Poland", "AT": "Austria",
    "CH": "Switzerland", "IE": "Ireland", "GR": "Greece", "FI": "Finland",
    "DK": "Denmark", "CZ": "Czech Republic", "RO": "Romania", "HU": "Hungary",
    "UA": "Ukraine", "RU": "Russia",
    # Asia
    "CN": "China", "JP": "Japan", "IN": "India", "KR": "South Korea",
    "ID": "Indonesia", "TH": "Thailand", "VN": "Vietnam", "PH": "Philippines",
    "MY": "Malaysia", "SG": "Singapore", "PK": "Pakistan", "BD": "Bangladesh",
    "IL": "Israel", "SA": "Saudi Arabia", "AE": "United Arab Emirates",
    "TR": "Turkey", "IR": "Iran", "TW": "Taiwan", "HK": "Hong Kong",
    # Africa
    "ZA": "South Africa", "NG": "Nigeria", "KE": "Kenya", "EG": "Egypt",
    "ET": "Ethiopia", "GH": "Ghana", "TZ": "Tanzania", "UG": "Uganda",
    "DZ": "Algeria", "MA": "Morocco", "TN": "Tunisia", "SN": "Senegal", "CI": "Ivory Coast",
    # Oceania
    "AU": "Australia", "NZ": "New Zealand", "FJ": "Fiji", "PG": "Papua New Guinea",
}

# Region to country codes mapping (must match scripts.py WORLD_FEED_REGION_MAP)
REGION_COUNTRIES = {
    "North America": ["US", "CA", "MX"],
    "Latin America": ["BR", "AR", "CL", "CO", "PE", "VE", "EC", "UY", "PY", "BO",
                      "CR", "PA", "CU", "DO", "GT", "HN", "NI", "SV"],
    "Europe": ["GB", "DE", "FR", "IT", "ES", "PT", "NL", "BE", "SE", "NO", "PL",
               "AT", "CH", "IE", "GR", "FI", "DK", "CZ", "RO", "HU", "UA", "RU"],
    "Asia": ["CN", "JP", "IN", "KR", "ID", "TH", "VN", "PH", "MY", "SG", "PK",
             "BD", "IL", "SA", "AE", "TR", "IR", "TW", "HK"],
    "Africa": ["ZA", "NG", "KE", "EG", "ET", "GH", "TZ", "UG", "DZ", "MA", "TN", "SN", "CI"],
    "Oceania": ["AU", "NZ", "FJ", "PG"],
}


def _build_region_countries(region: str, stories_by_code: dict, now: datetime) -> list:
    """Build country list for a region, including all countries even without stories."""
    countries = []
    for code in REGION_COUNTRIES.get(region, []):
        country_entry = {
            "code": code,
            "name": COUNTRY_NAMES.get(code, code),
            "cca2": code,
            "topStories": stories_by_code.get(code, [])
        }
        countries.append(country_entry)
    return countries


def _get_europe_countries(now: datetime) -> list:
    """Return fallback countries for Europe region."""
    stories = {
        "FR": [
            {"title": "France invests in high-speed rail expansion", "source": "AFP",
             "summary": "New TGV routes will connect major cities with reduced travel times.",
             "url": "#", "published_at": _days_ago(now, 0)},
            {"title": "Paris launches urban cooling program", "source": "Le Monde",
             "summary": "Shaded corridors and misting stations to mitigate heatwaves.",
             "url": "#", "published_at": _days_ago(now, 3)}],
        "DE": [
            {"title": "Germany leads EU renewable energy goals", "source": "DW",
             "summary": "Electricity generation crosses a new renewable benchmark.",
             "url": "#", "published_at": _days_ago(now, 1)}],
        "IT": [
            {"title": "Italy unveils green tourism plan", "source": "ANSA",
             "summary": "Incentives to preserve coastal parks and villages.",
             "url": "#", "published_at": _days_ago(now, 2)}],
        "GB": [
            {"title": "UK announces new tech investment fund", "source": "BBC",
             "summary": "Government backs AI and clean energy startups with major funding.",
             "url": "#", "published_at": _days_ago(now, 1)}],
        "ES": [
            {"title": "Spain expands solar energy capacity", "source": "El País",
             "summary": "New solar farms to power millions of homes across the country.",
             "url": "#", "published_at": _days_ago(now, 2)}],
    }
    return _build_region_countries("Europe", stories, now)


def _get_north_america_countries(now: datetime) -> list:
    """Return fallback countries for North America region."""
    stories = {
        "US": [
            {"title": "US tech stocks rally after earnings", "source": "Bloomberg",
             "summary": "Major indexes close higher on strong guidance.",
             "url": "#", "published_at": _days_ago(now, 0)},
            {"title": "Federal infrastructure grants announced", "source": "Reuters",
             "summary": "Funding targets bridges and broadband in rural areas.",
             "url": "#", "published_at": _days_ago(now, 2)}],
        "CA": [
            {"title": "Canada expands EV charging network", "source": "CBC",
             "summary": "New coast-to-coast fast chargers planned along Trans-Canada.",
             "url": "#", "published_at": _days_ago(now, 1)}],
        "MX": [
            {"title": "Mexico City launches air quality initiative", "source": "El Universal",
             "summary": "Low-emission zones to phase in over the next year.",
             "url": "#", "published_at": _days_ago(now, 3)}],
    }
    return _build_region_countries("North America", stories, now)


def _get_latin_america_countries(now: datetime) -> list:
    """Return fallback countries for Latin America region."""
    stories = {
        "BR": [
            {"title": "Brazil accelerates Amazon reforestation", "source": "Folha",
             "summary": "Public-private partnerships aim to restore key corridors.",
             "url": "#", "published_at": _days_ago(now, 0)},
            {"title": "São Paulo invests in public transport modernization", "source": "Estadão",
             "summary": "New metro lines and bus corridors planned for the metropolitan area.",
             "url": "#", "published_at": _days_ago(now, 2)}],
        "AR": [
            {"title": "Argentina announces export incentives", "source": "La Nación",
             "summary": "New measures target agribusiness and lithium.",
             "url": "#", "published_at": _days_ago(now, 2)}],
        "CL": [
            {"title": "Chile expands national park system", "source": "BioBio",
             "summary": "New protected areas designated in Patagonia.",
             "url": "#", "published_at": _days_ago(now, 4)}],
        "CO": [
            {"title": "Colombia launches digital economy initiative", "source": "El Tiempo",
             "summary": "Government supports tech startups and digital infrastructure.",
             "url": "#", "published_at": _days_ago(now, 1)}],
    }
    return _build_region_countries("Latin America", stories, now)


def _get_africa_countries(now: datetime) -> list:
    """Return fallback countries for Africa region."""
    stories = {
        "NG": [
            {"title": "Nigeria launches fintech regulatory sandbox", "source": "Punch",
             "summary": "Startups to test products with consumer safeguards.",
             "url": "#", "published_at": _days_ago(now, 0)}],
        "ZA": [
            {"title": "Cape Town water resilience plan updated", "source": "News24",
             "summary": "Desalination and reuse projects move forward.",
             "url": "#", "published_at": _days_ago(now, 1)}],
        "KE": [
            {"title": "Kenya expands mobile money interoperability", "source": "Nation",
             "summary": "Transfers between networks become seamless.",
             "url": "#", "published_at": _days_ago(now, 3)}],
        "EG": [
            {"title": "Egypt invests in new Suez Canal expansion", "source": "Al-Ahram",
             "summary": "Infrastructure upgrades aim to increase shipping capacity.",
             "url": "#", "published_at": _days_ago(now, 2)}],
    }
    return _build_region_countries("Africa", stories, now)


def _get_asia_countries(now: datetime) -> list:
    """Return fallback countries for Asia region."""
    stories = {
        "IN": [
            {"title": "India unveils semiconductor cluster incentives", "source": "The Hindu",
             "summary": "States compete to host fab projects.",
             "url": "#", "published_at": _days_ago(now, 0)}],
        "JP": [
            {"title": "Japan tests next-gen wind turbines", "source": "NHK",
             "summary": "Floating platforms deployed off Hokkaido.",
             "url": "#", "published_at": _days_ago(now, 1)}],
        "CN": [
            {"title": "China announces new high-speed rail link", "source": "Xinhua",
             "summary": "Route will reduce travel time by 40%.",
             "url": "#", "published_at": _days_ago(now, 2)}],
        "KR": [
            {"title": "South Korea advances AI research initiatives", "source": "Yonhap",
             "summary": "New funding for AI labs and talent development programs.",
             "url": "#", "published_at": _days_ago(now, 1)}],
        "SG": [
            {"title": "Singapore launches smart city 2.0 initiative", "source": "Straits Times",
             "summary": "New sensors and AI systems to improve urban services.",
             "url": "#", "published_at": _days_ago(now, 3)}],
    }
    return _build_region_countries("Asia", stories, now)


def _get_oceania_countries(now: datetime) -> list:
    """Return fallback countries for Oceania region."""
    stories = {
        "AU": [
            {"title": "Australia expands solar storage rebates", "source": "ABC",
             "summary": "Households to get additional support for batteries.",
             "url": "#", "published_at": _days_ago(now, 0)},
            {"title": "Melbourne announces new public transit expansion", "source": "The Age",
             "summary": "New tram and rail lines planned for the suburbs.",
             "url": "#", "published_at": _days_ago(now, 2)}],
        "NZ": [
            {"title": "New Zealand launches green hydrogen pilot", "source": "RNZ",
             "summary": "Port operations to trial zero-emission equipment.",
             "url": "#", "published_at": _days_ago(now, 3)}],
    }
    return _build_region_countries("Oceania", stories, now)


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
