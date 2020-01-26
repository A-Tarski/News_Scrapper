import argparse
import datetime
import csv

from db_handler import get_db_connection

parser = argparse.ArgumentParser(description='Specify publish date in format "01-01-2020"')
parser.add_argument('publish_date', type=str, nargs=1,
                    help='TO get all news from that date')
args = parser.parse_args()


publish_date = datetime.datetime.strptime(args.publish_date[0], "%d-%m-%Y")

db_conn = get_db_connection()
with db_conn.cursor() as cursor:
    cursor.execute("""
                   SELECT title, link, description, publish_date, full_text FROM news
                   WHERE CAST(publish_date as date)=%s;
                   """,
                   (publish_date, ))
    result = cursor.fetchall()
    print(f'Total loaded news: {len(result)}')

db_conn.close()

with open('/parsing/output/News_of_' + args.publish_date[0] + '.csv', 'w') as csv_file:
    writer = csv.writer(csv_file, delimiter=';')
    for news in result:
        writer.writerow(news)
