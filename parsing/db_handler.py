import psycopg2
import time


def get_db_connection(create_if_not_exist=True):
    while True:
        try:
            # TODO read from ENV
            conn = psycopg2.connect(host='db', port='5432', password='123', user='postgres')
            break
        except Exception as e:
            print(f'Cant connect to db {e}, retry')
            time.sleep(3)
    if create_if_not_exist:
        create_db_structure(conn)
    return conn


def create_db_structure(db_connection=None):
    if not db_connection:
        db_connection = get_db_connection()
    cursor = db_connection.cursor()
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS news
                   (id serial PRIMARY KEY,
                    title text,
                    description text,
                    link text,
                    publish_date timestamp,
                    full_text text);
                   """)
    db_connection.commit()
    cursor.close()
