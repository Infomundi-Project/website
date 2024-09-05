import pymysql
import os

from website_scripts import config


db_params = {
        'host': 'localhost',
        'user': config.MYSQL_USERNAME,
        'password': config.MYSQL_PASSWORD,
        'db': 'infomundi',
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor
    }


def insert_passwords_to_db(db_connection, passwords):
    with db_connection.cursor() as cursor:
        for password in passwords:
            cursor.execute("INSERT INTO common_passwords (password) VALUES (%s)", (password,))

    # Commit the transaction to save all inserts
    db_connection.commit()
    print(f"Inserted {len(passwords)} to the database (hopefully!).")


if __name__ == "__main__":
    db_connection = pymysql.connect(**db_params)
    
    with open('common-passwords.txt') as f:
        passwords = [x.strip() for x in f.readlines()]
    
    insert_passwords_to_db(db_connection, passwords)
