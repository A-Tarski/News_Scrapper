FROM python:3.7-slim

RUN apt-get -y update && apt-get -y upgrade
RUN apt-get -y install cron

WORKDIR /parsing

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY crontab /etc/cron.d/cjob
RUN chmod 0644 /etc/cron.d/cjob
RUN crontab /etc/cron.d/cjob

COPY /parsing /parsing

CMD cron && touch /var/log/cron.log && tail -F /var/log/cron.log