from requests import get as get_request
from bs4 import BeautifulSoup
from random import choice

from website_scripts import json_util, immutable
from website_scripts.config import LOCAL_ROOT
from website_scripts.qol_util import is_file_creation_within_threshold_minutes

path = f"{LOCAL_ROOT}/assets/data/json"


def format_world_data():
    common_currency = json_util.read_json(f"{path}/common_currency")
    currencies = json_util.read_json(f"{path}/currencies")
    for currency in currencies:
        name = currency["name"]
        currency_name = name.replace("USD", "")

        currency["price"] = round(float(currency["price"]), 2)

        if currency_name in common_currency:
            currency["symbol"] = common_currency[currency_name]["symbol"]
            currency["name_plural"] = common_currency[currency_name][
                "name_plural"
            ].title()

        if currency_name == "DXY":
            currency["price"] = 1
            currency["name"] = "USD"
            currency["symbol"] = "$"
            currency["name_plural"] = "US Dollars"

    countries = json_util.read_json(f"{path}/countries")
    stocks = json_util.read_json(f"{path}/stocks")
    for stock in stocks:
        stock_country = stock["country"]["name"].lower()

        for item in countries:
            if item["name"].lower() == stock_country:
                stock["country"]["code"] = item["code"].lower()
                break

        if stock_country in immutable.EU_COUNTRIES:
            stock_country = "euro area"

        for currency in currencies:
            currency_country = currency["country"]["name"].lower()

            if stock_country == currency_country:
                stock["currency"] = currency
                break

    json_util.write_json(stocks, f"{path}/stocks")
    json_util.write_json(currencies, f"{path}/currencies")
    print("[+] Data formatted.")


def scrape_data(url: str, endpoint: str):
    # Send a request to the URL
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    response = get_request(url, timeout=4, headers=headers)

    if response.status_code != 200:
        print(f"[+] Error getting {url}. Response code: {response.status_code}")
        return

    # Initialize BeautifulSoup
    soup = BeautifulSoup(response.content, "html.parser")

    # Initialize an empty list to store all items
    all_data = []

    trs = soup.find_all("tr")

    countries = json_util.read_json(f"{path}/countries")
    for row in trs:
        # Extract the needed data using the appropriate selectors
        symbol = row.get("data-symbol", "")
        name = row.find("b").text if row.find("b") else ""
        price = row.find(id="p").text.strip() if row.find(id="p") else ""

        day_change = row.find(id="nch").text.strip() if row.find(id="nch") else ""
        percent_change = row.find(id="pch").text.strip() if row.find(id="pch") else ""

        weekly_change = (
            row.find("td", class_="datatable-heatmap").text.strip()
            if row.find("td", class_="datatable-heatmap")
            else ""
        )
        monthly_change = (
            row.find_all("td", class_="datatable-heatmap")[1].text.strip()
            if len(row.find_all("td", class_="datatable-heatmap")) > 1
            else ""
        )
        yoy_change = (
            row.find_all("td", class_="datatable-heatmap")[2].text.strip()
            if len(row.find_all("td", class_="datatable-heatmap")) > 2
            else ""
        )

        # Get Country Name
        try:
            href = row.select_one(".datatable-item-first a")["href"]
            country_name = href.split("/")[1].replace("-", " ").title()
        except TypeError:
            continue

        if country_name.startswith("ndx:"):
            country_name = "United States"

        date = row.find(id="date").text.strip() if row.find(id="date") else ""

        # Compile the data into a dictionary
        data = {
            "symbol": symbol,
            "name": name,
            "price": price,
            "changes": {
                "day": day_change,
                "percent": percent_change,
                "weekly": weekly_change,
                "monthly": monthly_change,
                "yoy": yoy_change,
            },
            "country": {"name": country_name},
            "color": (
                "#FF6666" if "-" in percent_change else "#00FF00"
            ),  # HEX code for red and green respectively
            "date": date,
        }

        for item in countries:
            if item["name"].lower() == country_name.lower():
                data["country"]["code"] = item["code"].lower()
                break
        else:
            data["country"]["code"] = "eu"

        # Add the item to the list
        all_data.append(data)

    json_util.write_json(all_data, f"{path}/{endpoint}")
    print(f"[+] {endpoint.title()} data has been collected.")


def scrape_stock_data(country_name: str):
    """Uses tradingeconomics website to scrape stock info."""

    # Checks if cache is old enough (4 hours)
    filepath = f"{path}/stock_data/{country_name}_stock"
    if not is_file_creation_within_threshold_minutes(
        f"{filepath}.json", 4, is_hours=True
    ):
        stock_data = json_util.read_json(filepath)
        return stock_data

    response = get_request(
        f"https://tradingeconomics.com/{country_name}/stock-market",
        timeout=5,
        headers={"User-Agent": choice(immutable.USER_AGENTS)},
    )
    if response.status_code != 200:
        return []

    stock_data = []

    soup = BeautifulSoup(response.content, "html.parser")
    for tr in soup.find_all(
        "tr", {"data-decimals": "2"}
    ):  # Filter based on the data-decimals attribute
        symbol = tr.get("data-symbol")

        name_element = tr.find("td", style="max-width: 150px;")
        name = name_element.text.strip() if name_element else None

        price_element = tr.find("td", id="p")
        price = price_element.text.strip() if price_element else None

        day_element = tr.find("td", id="pch")
        day = day_element.text.strip() if day_element else None

        date_element = tr.find("td", id="date")
        date = date_element.text.strip() if date_element else None

        year_element = tr.find(
            "td", class_="d-none d-sm-table-cell", style="text-align: center;"
        )
        year = year_element.text.strip() if year_element else None

        # Check if the 'market_cap' element is present
        market_cap_element = tr.find(
            "td", {"class": "d-none d-md-table-cell", "data-value": True}
        )
        market_cap = market_cap_element.text.strip() if market_cap_element else None

        stock_info = {
            "symbol": symbol,
            "name": name,
            "price": price,
            "day_change": day,
            "year_change": year,
            "date": date,
            "market_cap": market_cap,
        }

        stock_data.append(stock_info)

    json_util.write_json(stock_data, filepath)


if __name__ == "__main__":
    countries = [x["name"] for x in json_util.read_json(f"{path}/countries")]
    for country_name in countries:
        scrape_stock_data(country_name)

    endpoints = ["currencies", "crypto", "stocks"]
    for endpoint in endpoints:
        scrape_data(f"https://tradingeconomics.com/{endpoint}", endpoint)

    format_world_data()
