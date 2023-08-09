from aiohttp import web
import aiofiles
import datetime
import asyncio
import logging
import os


INTERVAL_SECS = 1


async def archive(request, read_up_bytes=102400):
    archive_hash = request.match_info['archive_hash']
    photos_filepath = os.path.join('test_photos', archive_hash)
    process = await asyncio.create_subprocess_exec(
        'zip',
        '-r',
        '-',
        '..',
        stdout=asyncio.subprocess.PIPE,
        cwd=photos_filepath,
    )
    response = web.StreamResponse()
    response.headers['Content-Disposition'] = f'attachment; filename={archive_hash}.zip'
    await response.prepare(request)
    try:
        while not process.stdout.at_eof():
            zip_binary = await process.stdout.read(read_up_bytes)
            await response.write(zip_binary)
            await asyncio.sleep(1)
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


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archive),
    ])
    web.run_app(app)
