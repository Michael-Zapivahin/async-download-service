from aiohttp import web
import aiofiles
import datetime
import argparse
import asyncio
import os
import logging

logger = logging.getLogger(__name__)
INTERVAL_SECS = 1
PHOTOS_CATALOG = 'test_photos'
DELAY = True


async def archive(request, read_up_bytes=102400):
    archive_hash = request.match_info['archive_hash']
    photos_filepath = os.path.join(PHOTOS_CATALOG, archive_hash)
    if not os.path.exists(photos_filepath):
        async with aiofiles.open('404.html', mode='r') as error_file:
            error_contents = await error_file.read()
        raise web.HTTPNotFound(text=error_contents, content_type='text/html')
    cmd = ['zip', '-r', '-', *os.listdir(photos_filepath)]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        cwd=photos_filepath,
    )
    response = web.StreamResponse()
    response.headers['Content-Disposition'] = f'attachment; filename={archive_hash}.zip'
    await response.prepare(request)
    try:
        while not process.stdout.at_eof():
            zip_binary = await process.stdout.read(read_up_bytes)
            logger.info('Sending archive chunk ...')
            await response.write(zip_binary)
            if DELAY:
                await asyncio.sleep(5)
        return response
    except asyncio.CancelledError:
        logger.info('Download was interrupted')
        raise
    finally:
        if process.returncode is None:
            process.kill()
            await process.communicate()
            logger.info('Process was killed')


async def uptime_handler(request):
    response = web.StreamResponse()

    # Большинство браузеров не отрисовывают частично загруженный контент, только если это не HTML.
    # Поэтому отправляем клиенту именно HTML, указываем это в Content-Type.
    response.headers['Content-Type'] = 'text/html'

    # Отправляет клиенту HTTP заголовки
    await response.prepare(request)

    while True:
        formatted_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f'{formatted_date}<br>'  # <br> — HTML тег переноса строки

        # Отправляет клиенту очередную порцию ответа
        await response.write(message.encode('utf-8'))

        await asyncio.sleep(INTERVAL_SECS)


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--logging', default='true', help='enable logging')
    parser.add_argument('-d', '--delay', default='false', help='enable delay')
    parser.add_argument('-p', '--path', default='test_photos', help='photos catalog path')
    args = parser.parse_args()

    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    DELAY = bool(args.delay)
    PHOTOS_CATALOG = args.path
    logger.disabled = bool(args.logging)

    if not os.path.exists(PHOTOS_CATALOG):
        print(f"The photos catalog {PHOTOS_CATALOG} doesn't exist")
        return

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archive),
    ])
    web.run_app(app)


if __name__ == '__main__':
    main()
