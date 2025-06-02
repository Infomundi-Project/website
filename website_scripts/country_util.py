from . import extensions, models, custom_exceptions, scripts


def get_country(name: str = "", iso2: str = "", iso3: str = "", ilike: bool = False):
    """Comprehensive way to look for specific countries in the database.

    Arguments
        name: str
            The country name. Optional.

        iso2: str
            The country cca2. Optional.

        ilike: bool
            Defaults to False. Only used if 'name' is provided. Used when the name is partially complete, so the query to the database is 'ilike'.

    Return
        Depends. If 'ilike' is True, returns all instances where the incomplete 'name' matches. If 'ilike' is False (default) returns the country that matches to the query. Can return None if no country was found.
    """

    if not name and not iso2 and not iso3:
        raise custom_exceptions.InfomundiCustomException(
            "Either 'name' or 'iso2' or 'iso3' should be specified"
        )

    if name:
        if ilike:
            countries = models.Country.query.all()
            similarity_data = []
            for country in countries:
                similarity_data.append(
                    (country, scripts.string_similarity(name, country.name))
                )
            similarity_data.sort(key=lambda x: x[1], reverse=True)  # Sorts the list based on higher similarity
            return similarity_data
        else:
            country = models.Country.query.filter_by(name=name).first()
    elif iso2:
        country = models.Country.query.filter_by(iso2=iso2).first()
    else:
        country = models.Country.query.filter_by(iso3=iso3).first()

    return country


def get_countries() -> list:
    countries = models.Country.query.all()
    result = []
    for country in countries:
        result.append(
            {
                "id": country.id,
                "name": country.name,
                "iso3": country.iso3,
                "iso2": country.iso2,
            }
        )
    return result


def get_states(country_id: int) -> list:
    states = models.State.query.filter_by(country_id=country_id).all()
    result = []
    for state in states:
        result.append(
            {
                "id": state.id,
                "name": state.name,
                "country_id": state.country_id,
                "country_code": state.country_code,
            }
        )
    return result


def get_cities(state_id) -> list:
    cities = models.City.query.filter_by(state_id=state_id).all()
    result = []
    for city in cities:
        result.append(
            {
                "id": city.id,
                "name": city.name,
                "state_id": city.state_id,
                "state_code": city.state_code,
                "country_id": city.country_id,
                "country_code": city.country_code,
            }
        )
    return result
