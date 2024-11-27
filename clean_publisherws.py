import pymysql
from website_scripts import config
from openai import OpenAI
from sys import exit
import json
from random import shuffle

# Database connection parameters
db_params = {
    'host': '127.0.0.1',
    'user': config.MYSQL_USERNAME,
    'password': config.MYSQL_PASSWORD,
    'db': config.MYSQL_DATABASE,
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

db_connection = pymysql.connect(**db_params)


with db_connection.cursor() as cursor:
    sql_query = "SELECT publisher_id, name FROM publishers"
    cursor.execute(sql_query)
    publishers = cursor.fetchall()
    shuffle(publishers)


def gpt_extract_publisher_name(text):
    # One-shot prompt
    prompt = f"""
    Extract only the publisher name from the following string:

    Input: "{text}"
    Output: 
    """
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        messages=[
            {
                "role": "system",
                "content": 'You are a helpful and comprehensive assistant. Your output should be an one shot classification of the publisher name, no further text or explanation.'
            },
            {"role": "user", "content": prompt}
        ],
        n=1,
        max_tokens=50,
        temperature=0
    )

    return response.choices[0].message.content


def calculate_percentage(part, whole):
    return 100 * float(part)/float(whole)


formatted = {}
for publisher in publishers:
    percentage = round(calculate_percentage(len(formatted), len(publishers)), 2)
    try:
        publisher_id = publisher['publisher_id']
        publisher_name = publisher['name']
            
        result = gpt_extract_publisher_name(publisher_name.strip())
        formatted[publisher_id] = result.replace("\"", '').replace('\'', '').replace('Output: ', '')
    except Exception as e:
        print(e)
        continue
    print(f'[%] Formatting publisher names: {percentage}%')

with open('formatted.json', 'a') as f:
    f.write(json.dumps(formatted, indent=2))