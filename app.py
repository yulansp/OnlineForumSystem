import logging
import handlers
from yulan import runapp
from config import configs
import asyncio
from aiomyorm import close_db_connection
from rds import create_rds, close_rds

logging.basicConfig(level=logging.INFO)


def init():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_rds(loop=loop, **configs['rds']))
    runapp(host=configs['web']['host'], port=configs['web']['port'])
    loop.run_until_complete(close_rds())
    loop.run_until_complete(close_db_connection())
    loop.stop()
    loop.close()


if __name__ == '__main__':
    init()
