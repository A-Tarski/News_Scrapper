import aiohttp
import asyncio
import datetime
import logging
import sys
from bs4 import BeautifulSoup
from contextlib import contextmanager

from db_handler import get_db_connection


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


class BaseParser:

    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_1) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36',
    }

    def __init__(self, url_base=None, complex_name=None, x_req=False, limit_per_host=200, debug=False, timeout=60 * 5, raise_for_status=False):
        self.url_base = url_base
        connector = aiohttp.TCPConnector(limit_per_host=limit_per_host)
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        self.session = aiohttp.ClientSession(connector=connector, timeout=client_timeout, raise_for_status=raise_for_status)

    async def request(self, url=None, data=None, x_req=False, to_bs=False, params=None, headers=None, method=None, retry=5, to_js=False):
        if x_req:
            self.update_header('x_req')
        if not url:
            url = self.url_base
        if headers:
            self.update_header(headers)
        if not method:
            method = 'POST' if data else 'GET'
        self.last_url = url
        logger_params = {}
        if data:
            logger_params['data'] = data
        if params:
            logger_params['params'] = params
        logger.debug(f'{method}, {url}, {logger_params}')
        return await self._rerequest(method, url, data, params, to_bs, retry, to_js)

    async def _rerequest(self, method, url, data, params, to_bs, retry, to_js):
        wait_time = retry * 1.5
        while True:
            try:
                with Utils.suppress_ssl_exception_report():
                    resp = await self.session._request(method, url, data=data, params=params, headers=self.headers, ssl=False)
                    if to_bs:
                        return BeautifulSoup(await resp.read(), 'lxml')
                    elif to_js:
                        return await resp.json(content_type=None)
                    return await resp.text()
            except (aiohttp.client_exceptions.ServerDisconnectedError, asyncio.TimeoutError,
                    aiohttp.client_exceptions.ClientConnectorError,
                    aiohttp.client_exceptions.ClientResponseError,
                    aiohttp.client_exceptions.ClientOSError,
                    aiohttp.client_exceptions.ClientPayloadError) as e:
                logger.warning(f"Can't load url {url}, {e} retry: , {retry}")
                await asyncio.sleep(wait_time - retry)
                retry -= 1
                if retry <= 0:
                    raise

    async def start(self):
        try:
            await self.load_data()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception('')
        finally:
            await self.tear_down()

    async def tear_down(self):
        await self.session.close()


class Utils:

    @staticmethod
    @contextmanager
    def suppress_ssl_exception_report():
        loop = asyncio.get_event_loop()
        old_handler = loop.get_exception_handler()

        def default_handler(_loop, ctx):
            loop.default_exception_handler(ctx)

        old_handler_fn = old_handler or default_handler

        def ignore_exc(_loop, ctx):
            exc = ctx.get('exception')
            import ssl
            if isinstance(exc, ssl.SSLError):
                return
            old_handler_fn(loop, ctx)

        loop.set_exception_handler(ignore_exc)
        try:
            yield
        finally:
            loop.set_exception_handler(old_handler)

    @staticmethod
    def test_out(data, file='Output.txt'):
        with open(file, 'w', encoding='utf-8') as f:
            f.write(str(data))


class NewsParser(BaseParser):

    def __init__(self, db_connection, *args, **kwargs):
        self.db_conn = db_connection
        super().__init__(*args, **kwargs)

    async def load_data(self):
        logger.debug('Start loading top news page')
        main_page = await self.request('http://feeds.reuters.com/reuters/topNews', to_bs=True)
        # Utils.test_out(main_page.prettify())
        tasks = []
        for news in main_page.select('item'):
            title = news.select_one('title').text
            description = news.select_one('description').text
            # lxml can't parse link park at the bottom the news due to encoding troubles
            description = BeautifulSoup(description, 'lxml').p.text
            link = news.select_one('guid').text
            publish_date = news.select_one('pubdate').text
            publish_date = datetime.datetime.strptime(publish_date, "%a, %d %b %Y %H:%M:%S %z")
            with self.db_conn.cursor() as cursor:
                news_id = self.save_news_to_db(cursor, title, description, link, publish_date)
            if news_id:
                tasks.append(self.load_news_full_text(link, news_id))
        await asyncio.gather(*tasks)

    async def load_news_full_text(self, news_link, news_id):
        logger.debug(f'Try get news ID={news_id} full text from {news_link}')
        news_page = await self.request(news_link, to_bs=True)
        # Utils.test_out(news_page.prettify())
        full_text = news_page.select_one('.StandardArticleBody_container').text
        with self.db_conn.cursor() as cursor:
            self.save_full_text_to_news(cursor, news_id, full_text)

    def save_news_to_db(self, cursor, title, description, link, publish_date):
        if not self.is_news_already_in_db(cursor, title, publish_date):
            cursor.execute("""
                           INSERT INTO news (title, description, link, publish_date)
                           VALUES (%s, %s, %s, %s) RETURNING id;
                           """,
                           (title, description, link, publish_date))
            news_id = cursor.fetchone()[0]
            logger.debug(f'Save news ID={news_id} to db {link}')
            return news_id

    @staticmethod
    def is_news_already_in_db(cursor, title, publish_date):
        cursor.execute("""
                       SELECT title, publish_date FROM news
                       WHERE title=%s and publish_date=%s;
                       """,
                       (title, publish_date))
        if cursor.fetchone():
            logger.debug(f'News "{title}" already exist in db - skipped')
            return True

    @staticmethod
    def save_full_text_to_news(cursor, news_id, full_text):
        cursor.execute("""
                       UPDATE news SET full_text=(%s)
                       WHERE id = (%s);
                       """,
                       (full_text, news_id,))
        logger.debug(f'Success save news ID={news_id} full text LEN={len(full_text)}')


async def parsing():
    conn = get_db_connection()
    parser = NewsParser(conn)
    with conn:
        await parser.start()
    conn.close()


if __name__ == "__main__":
    asyncio.run(parsing())
