from datetime import datetime
from unidecode import unidecode

from website_scripts import json_util, config, scripts

def get_current_time_in_timezone(cca2: str) -> str:
    data = json_util.read_json(f'{config.COUNTRIES_DATA_PATH}/{cca2}')
    current_utc_time = datetime.utcnow()

    country_capital = unidecode(data[0]['capital'][0].lower())
    capitals_time = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/capitals_time')

    for item in capitals_time:
        if country_capital in unidecode(item['capital']).lower():
            timezone = item['gmt_offset']
            break
    else:
        timezone = ''

    if '+' in timezone or '-' in timezone:
        utc_offset = scripts.parse_utc_offset(timezone)
        current_time = current_utc_time + utc_offset
    else:
        current_time = current_utc_time
    
    formatted_time = current_time.strftime("%Y/%m/%d - %H:%M:%S")
    return formatted_time

print(get_current_time_in_timezone('us'))