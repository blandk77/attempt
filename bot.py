import logging
from telethon import TelegramClient, events
from config import Config
import asyncio
import subprocess
import time
import math
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = TelegramClient('bot_session', Config.TELEGRAM_API_ID, Config.TELEGRAM_API_HASH).start(bot_token=Config.TELEGRAM_BOT_TOKEN)

async def progress_for_pyrogram(current, total, client, ud_type, message, start):
    now = time.time()
    diff = now - start
    if round(diff % 10.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff)
        time_to_completion = round((total - current) / speed)
        estimated_total_time = elapsed_time + time_to_completion
        elapsed_time = TimeFormatter(seconds=elapsed_time)
        estimated_total_time = TimeFormatter(seconds=estimated_total_time)
        progress = "[{0}{1}]".format(
            ''.join(["⬢" for i in range(math.floor(percentage / 10))]),
            ''.join(["⬡" for i in range(10 - math.floor(percentage / 10))])
        )
        tmp = progress + PROGRESS.format(
            humanbytes(current),
            humanbytes(total),
            humanbytes(speed) + "/s",
            estimated_total_time if estimated_total_time != '' else "Calculating"
        )
        try:
            await client.edit_message_text(chat_id=message.chat.id, message_id=message.id,
                text="{}\n{}".format(
                    ud_type,
                    tmp
                ),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Owner", url='https://t.me/ninja_obito_sai')]])
            )
        except Exception as e:
            logger.error(f'Senpai Error: {e}')
            pass
        await asyncio.sleep(5)

PROGRESS = """
• {0} of {1}
• Speed: {2}
• ETA: {3}
"""

async def execute_crunchy_command(crunchyroll_link, message):
    try:
        current_progress = 0
        total_progress = 1000  # Placeholder value for demonstration purposes

        command = [
            './crunchy-cli-v3.2.5-linux-x86_64',
            '--anonymous', 'archive', '-r', '1280x720', '-a', 'en-US', '--ffmpeg-preset', 'h265-normal',
            crunchyroll_link
        ]
        process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        start_time = time.time()
        progress_message = await client.send_message(message.chat_id, "Ripping in progress...")

        while True:
            data = await process.stdout.read(1024)
            if not data:
                break
            current_progress += len(data)
            await progress_for_pyrogram(
                current_progress,
                total_progress,
                client,
                "Ripping Status",
                progress_message,
                start_time
            )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return stdout
        else:
            logger.error(f'Error executing command: {stderr.decode()}')
            return None
    except subprocess.CalledProcessError as e:
        logger.error(f'Error executing command: {str(e)}')
        logger.info('Trying to rip without account credentials...')
        command_without_credentials = [
            './crunchy-cli-v3.2.5-linux-x86_64',
            'archive', '-r', '1280x720', '-a', 'en-US', '--ffmpeg-preset', 'h265-normal',
            crunchyroll_link
        ]
        process_without_credentials = await asyncio.create_subprocess_exec(*command_without_credentials, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        start_time_without_credentials = time.time()
        progress_message_without_credentials = await client.send_message(message.chat_id, "Ripping in progress...")

        while True:
            data = await process_without_credentials.stdout.read(1024)
            if not data:
                break
            current_progress += len(data)
            await progress_for_pyrogram(
                current_progress,
                total_progress,
                client,
                "Ripping Status",
                progress_message_without_credentials,
                start_time_without_credentials
            )

        stdout_without_credentials, stderr_without_credentials = await process_without_credentials.communicate()

        if process_without_credentials.returncode == 0:
            return stdout_without_credentials
        else:
            logger.error(f'Error executing command without credentials: {stderr_without_credentials.decode()}')
            return None
    except Exception as e:
        logger.exception(f'Error executing command: {str(e)}')
        return None

@client.on(events.NewMessage(pattern='/rip'))
async def handle_rip_command(event):
    try:
        crunchyroll_link = event.raw_text.split('/rip', 1)[1].strip()
        logger.info(f'Received rip command for {crunchyroll_link}')

        await event.respond("Ripping process started...")

        ripped_video = await execute_crunchy_command(crunchyroll_link, event.message)

        if ripped_video:
            await client.send_file(event.chat_id, ripped_video, caption="Here is your ripped video!")
            logger.info(f'Successfully uploaded video to {event.chat_id}')
        else:
            await event.respond("Ripping process failed. Please try again later.")
    except Exception as e:
        await event.respond(f'Error: {str(e)}')
        logger.exception(f'Error: {str(e)}')

def humanbytes(size):
    if not size:
        return ""
    power = 1024
    t_n = 0
    power_dict = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        t_n += 1
    return "{:.2f} {}B".format(size, power_dict[t_n])

def TimeFormatter(seconds: float) -> str:
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
        ((str(hours) + "h, ") if hours else "") + \
        ((str(minutes) + "m, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "")
    return tmp[:-2]

client.run_until_disconnected()
