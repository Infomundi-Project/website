from random import randint as random_integer
from requests import get as get_request
from json import dump as json_dump
from bs4 import BeautifulSoup
from time import sleep

from website_scripts import json_util, config

def get_world_data():
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
        

        # Extracting data from each row in the continent's table
        for row in soup.select('.datatable-row'):
            symbol = row['data-symbol']
            name = row.select_one('.datatable-item-first a b').text.strip()
            price = row.select_one('#p').text.strip()
            day_change = row.select_one('#nch').text.strip()
            percent_change = row.select_one('#pch').text.strip()
            weekly_change = row.select('.datatable-heatmap')[0].text.strip()
            monthly_change = row.select('.datatable-heatmap')[1].text.strip()
            yoy_change = row.select('.datatable-heatmap')[2].text.strip()
            href = row.select_one('.datatable-item-first a')['href']
            date = row.select_one('#date').text.strip()

            if endpoint == 'currencies':
                common_currency = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/common_currency')
                from_dollar = True if name.startswith('USD') else False
                currency_name = name.replace('USD', '')
                price = round(float(price), 2)
                
                if currency_name in common_currency:
                    currency_symbol = common_currency[currency_name]['symbol']
                    name_plural = common_currency[currency_name]['name_plural']
                
                if currency_name == 'DXY':
                    currency_symbol = '$'
                    name_plural = 'US dollars'
            else:
                currency_symbol = ''
                from_dollar = ''

            data = {
                'symbol': symbol,
                'name': name,
                'price': price,
                'currency_symbol': currency_symbol,
                'currency_name_plural': name_plural,
                'from_dollar': from_dollar,
                'day_change': day_change,
                'percent_change': percent_change,
                'weekly_change': weekly_change,
                'monthly_change': monthly_change,
                'yoy_change': yoy_change,
                'date': date,
                'country_name': href.split('/')[1],
            }

            continent_data.append(data)

        for row in soup.select('.datatable-row-alternating'):
            symbol = row['data-symbol']
            name = row.select_one('.datatable-item-first a b').text.strip()
            price = row.select_one('#p').text.strip()
            day_change = row.select_one('#nch').text.strip()
            percent_change = row.select_one('#pch').text.strip()
            weekly_change = row.select('.datatable-heatmap')[0].text.strip()
            monthly_change = row.select('.datatable-heatmap')[1].text.strip()
            href = row.select_one('.datatable-item-first a')['href']
            yoy_change = row.select('.datatable-heatmap')[2].text.strip()
            date = row.select_one('#date').text.strip()

            if endpoint == 'currencies':
                common_currency = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/common_currency')
                from_dollar = True if name.startswith('USD') else False
                currency_name = name.replace('USD', '')
                price = round(float(price), 2)
                
                if currency_name in common_currency:
                    currency_symbol = common_currency[currency_name]['symbol']
                    name_plural = common_currency[currency_name]['name_plural']
                
                if currency_name == 'DXY':
                    currency_symbol = '$'
                    name_plural = 'US dollars'
            else:
                currency_symbol = ''
                from_dollar = ''
            
            data = {
                'symbol': symbol,
                'name': name,
                'currency_symbol': currency_symbol,
                'currency_name_plural': name_plural,
                'from_dollar': from_dollar,
                'price': price,
                'day_change': day_change,
                'percent_change': percent_change,
                'weekly_change': weekly_change,
                'monthly_change': monthly_change,
                'yoy_change': yoy_change,
                'date': date,
                'country_name': href.split('/')[1],
            }

            continent_data.append(data)

        if endpoint == 'stocks':
            flags = json_util.read_json(f'{config.STOCK_PATH}/stock_to_flag')
            countries = config.COUNTRY_LIST
            for item in continent_data:
                for flag in flags:
                    for stock_name, flag in flag.items():
                        if stock_name.lower() == item['name'].lower().replace(' ', ''):
                            item['flag'] = flag
                            break

                    for country in countries:
                        try:
                            if item['flag'].split('-')[1].lower() == country['code'].lower():
                                country_name = country['name']
                                
                                item['country'] = country_name
                                break
                        except Exception:
                            pass

        json_util.write_json(continent_data, f'{config.WEBSITE_ROOT}/data/json/{endpoint}')
        print(f'[+] {endpoint.title()} data has been collected.')

if __name__ == '__main__':
    get_world_data()