## Installing

To start service just use:

```
docker-compose up -d
```

Note! There're no need to create separatly db and tables. 
All preparations wll be made automaticly with starting of containers.

After starting service start to update data every 1 hour. 

## Commands

### Start db container only

```
docker-compose up -d db
```

Use `docker logs <CONTAINER ID>` to see progress of cron tasks

### Create db structure (title, link, desription, publish_date, full_text)

```
docker-compose build worker
docker-compose run --rm worker python /parsing/create_db_news_table.py
```

### Check current db tables

```
docker exec -ti <DB_CONTAINER_ID> psql -U postgres
\dt
```

Also to check created columns `select * from news where false;`

### Start scraper right now

```
docker-compose run --rm worker python /parsing/parser.py
```

### Get news for specific date

Data will be loaded to csv file at local host.

```
docker-compose run -v "$PWD"/output:/parsing/output --rm worker python get_news.py '26-01-2020'
```
