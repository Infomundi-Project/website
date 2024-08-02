from .extensions import db
from .models import Country, State, City


def get_countries() -> dict:
    countries = Country.query.all()
    result = []
    for country in countries:
        result.append({
            'id': country.id,
            'name': country.name,
            'iso3': country.iso3,
            'iso2': country.iso2
        })
    return result


def get_states(country_id) -> dict:
    states = State.query.filter_by(country_id=country_id).all()
    result = []
    for state in states:
        result.append({
            'id': state.id,
            'name': state.name,
            'country_id': state.country_id,
            'country_code': state.country_code
        })
    return result


def get_cities(state_id) -> dict:
    cities = City.query.filter_by(state_id=state_id).all()
    result = []
    for city in cities:
        result.append({
            'id': city.id,
            'name': city.name,
            'state_id': city.state_id,
            'state_code': city.state_code,
            'country_id': city.country_id,
            'country_code': city.country_code
        })
    return result
