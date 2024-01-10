from random import randint as random_integer
from requests import get as get_request
from json import dump as json_dump
from bs4 import BeautifulSoup
from time import sleep

from website_scripts import json_util, config, immutable


def format_world_data():
    path = f'{config.WEBSITE_ROOT}/data/json'

    common_currency = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/common_currency')
    currencies = json_util.read_json(f'{path}/currencies')
    for currency in currencies:
        name = currency['name']
        currency_name = name.replace('USD', '')
        
        currency['price'] = round(float(currency['price']), 2)
        
        if currency_name in common_currency:
            currency['symbol'] = common_currency[currency_name]['symbol']
            currency['name_plural'] = common_currency[currency_name]['name_plural'].title()
        
        if currency_name == 'DXY':
            currency['price'] = 1
            currency['name'] = 'USD'
            currency['symbol'] = '$'
            currency['name_plural'] = 'US Dollars'
  
    countries = config.COUNTRY_LIST
    stocks = json_util.read_json(f'{path}/stocks')
    for stock in stocks:
        stock_country = stock['country']['name'].lower()
        
        for item in countries:
            if item['name'].lower() == stock_country:
                stock['country']['code'] = item['code'].lower()
                break

        if stock_country in immutable.EU_COUNTRIES:
            stock_country = 'euro area'

        for currency in currencies:
            currency_country = currency['country']['name'].lower()
            
            if stock_country == currency_country:
                stock['currency'] = currency
                break

    json_util.write_json(stocks, f'{path}/stocks')
    json_util.write_json(currencies, f'{path}/currencies')
    print('[+] Data formatted.')


def get_world_finance_data():
    """Function to collect data about currencies, crypto and stocks around the globe. Scrapes from 'tradingeconomics' website and saves the data to a json file to be used in Infomundi."""
    endpoints = ['currencies', 'crypto', 'stocks']

    for endpoint in endpoints:
        sleep_seconds = random_integer(5, 15)
        print(f'\n[~] Sleeping for {sleep_seconds} seconds...')
        sleep(sleep_seconds)
        print(f'[~] Collecting {endpoint} data.')
        
        url = f"https://tradingeconomics.com/{endpoint}"
        
        headers = {
            'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        response = get_request(url, headers=headers)

        if response.status_code != 200:
            print(f'[+] Error getting {endpoint}. Response code: {response.status_code}')
            continue

        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        continent_data = []

        datatables = [row for row in soup.select('.datatable-row')]

        index = 1
        for row in soup.select('.datatable-row-alternating'):
            datatables.insert(index, row)
            index += 2
        
        for row in datatables:
            symbol = row['data-symbol']
            name = row.select_one('.datatable-item-first a b').text.strip()
            price = row.select_one('#p').text.strip()
            
            day_change = row.select_one('#nch').text.strip()
            percent_change = row.select_one('#pch').text.strip()
            weekly_change = row.select('.datatable-heatmap')[0].text.strip()
            monthly_change = row.select('.datatable-heatmap')[1].text.strip()
            yoy_change = row.select('.datatable-heatmap')[2].text.strip()
            
            href = row.select_one('.datatable-item-first a')['href']
            country_name = href.split('/')[1].replace('-', ' ').title()

            if country_name.startswith('ndx:'):
                country_name = 'United States'
            
            date = row.select_one('#date').text.strip()

            save_data = {
                'symbol': symbol,
                'name': name,
                'price': price,
                
                'changes': {
                    'day': day_change,
                    'percent': percent_change,
                    'weekly': weekly_change,
                    'monthly': monthly_change,
                    'yoy': yoy_change
                },
                
                'country': {
                    'name': country_name
                },

                'color': 'red' if '-' in percent_change else 'green',

                'date': date
            }

            continent_data.append(save_data)

        json_util.write_json(continent_data, f'{config.WEBSITE_ROOT}/data/json/{endpoint}')
        print(f'[+] {endpoint.title()} data has been collected.')

    return format_world_data()


if __name__ == '__main__':
    get_world_finance_data()