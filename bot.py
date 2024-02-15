import logging
from telethon import TelegramClient, events
from config import Config
import asyncio
import subprocess
import time
import math
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = TelegramClient('bot_session', Config.TELEGRAM_API_ID, Config.TELEGRAM_API_HASH).start(bot_token=Config.TELEGRAM_BOT_TOKEN)

async def progress_for_pyrogram(current, total, client, message, start_time):
    try:
        now = time.time()
        diff = now - start_time
        if round(diff % 10.00) == 0 or current == total:
            percentage = current * 100 / total
            speed = current / diff
            elapsed_time = round(diff)
            time_to_completion = round((total - current) / speed)
            estimated_total_time = elapsed_time + time_to_completion
            elapsed_time_str = TimeFormatter(elapsed_time)
            estimated_total_time_str = TimeFormatter(estimated_total_time)
            progress = "[{0}{1}]".format(
                ''.join(["⬢" for _ in range(math.floor(percentage / 10))]),
                ''.join(["⬡" for _ in range(10 - math.floor(percentage / 10))])
            )
            progress_message = f"Ripping in progress...\n\n" \
                               f"{progress} {percentage:.2f}%\n" \
                               f"Speed: {humanbytes(speed)}/s\n" \
                               f"ETA: {estimated_total_time_str}"
            await client.edit_message_text(chat_id=message.chat.id, message_id=message.id, text=progress_message)
    except Exception as e:
        logger.error(f'Error in progress_for_pyrogram: {e}')

async def execute_crunchy_command(crunchyroll_link, message):
    try:
        command = ['./crunchy-cli-v3.2.5-linux-x86_64',
                   '--anonymous', 'archive', '-r', '1280x720', '-a', 'en-US',
                   crunchyroll_link]
        process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        start_time = time.time()
        progress_message = await client.send_message(message.chat_id, "Ripping in progress...")

        while True:
            data = await process.stdout.read(1024)
            if not data:
                break
            await progress_for_pyrogram(process.stdout.tell(), 1000, client, progress_message, start_time)

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return stdout
        else:
            logger.error(f'Error executing command: {stderr.decode()}')
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
    time_str = ((str(days) + "d, ") if days else "") + \
               ((str(hours) + "h, ") if hours else "") + \
               ((str(minutes) + "m, ") if minutes else "") + \
               ((str(seconds) + "s, ") if seconds else "")
    return time_str[:-2]

client.run_until_disconnected()
