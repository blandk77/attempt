import logging
import time
import math
import asyncio
import subprocess
import os
from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonUrl
from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = TelegramClient('bot_session', Config.TELEGRAM_API_ID, Config.TELEGRAM_API_HASH).start(bot_token=Config.TELEGRAM_BOT_TOKEN)

# Progress functions adapted for Telethon
PROGRESS = """
• {0} of {1}
• Speed: {2}
• ETA: {3}
"""

async def progress_for_telethon(current, total, ud_type, message, start, total_size=None):
    total = total_size if total_size is not None else total
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
            await client.edit_message(
                message,
                text="{}\n{}".format(ud_type, tmp),
                buttons=[KeyboardButtonUrl("Owner", "https://t.me/ninja_obito_sai")]
            )
        except Exception as e:
            logger.error(f'Error updating progress: {e}')
            pass
        await asyncio.sleep(5)

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

@client.on(events.NewMessage(pattern='/start'))
async def start_message(event):
    await event.respond(
        "Welcome to the Crunchyroll Downloader Bot! Use /rip <Crunchyroll URL> to download a video (e.g., /rip https://www.crunchyroll.com/watch/...). "
        "Note: Rate limits may apply; try again after 10-20 minutes if it fails."
    )

async def execute_crunchy_command(crunchyroll_link, message):
    try:
        # Base command without authentication
        command = ['./crunchy-cli-v3.2.5-linux-x86_64', 'archive', '-r', '1280x720', '-a', 'en-US', crunchyroll_link]
        
        # Try authenticated mode if credentials are provided
        use_auth = False
        if hasattr(Config, 'CR_EMAIL') and hasattr(Config, 'CR_PASSWORD') and Config.CR_EMAIL and Config.CR_PASSWORD:
            # Format credentials as "email:password" for --credentials flag
            credentials = f"{Config.CR_EMAIL}:{Config.CR_PASSWORD}"
            command = ['./crunchy-cli-v3.2.5-linux-x86_64', '--credentials', credentials,
                       'archive', '-r', '1280x720', '-a', 'en-US', crunchyroll_link]
            use_auth = True
        else:
            command.insert(1, '--anonymous')
            logger.info("No valid credentials found; using anonymous mode")

        process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        start_time = time.time()
        progress_message = await client.send_message(message.chat_id, "Ripping in progress...")

        # Estimate total size for download progress (placeholder)
        total_size = 1000  # TODO: Replace with actual size if available from crunchy-cli
        total_data_read = 0

        while True:
            data = await process.stdout.read(1024)
            if not data:
                break
            total_data_read += len(data)
            await progress_for_telethon(total_data_read, total_size, "Downloading", progress_message, start_time, total_size)

        stdout, stderr = await process.communicate()
        error_msg = stderr.decode().lower()

        if process.returncode == 0:
            # Assume stdout contains the path to the downloaded video
            video_path = stdout.decode().strip()
            logger.info(f"crunchy-cli stdout: {video_path}")
            if video_path and os.path.exists(video_path):
                return video_path
            else:
                logger.error("No valid video path returned by crunchy-cli")
                await client.edit_message(progress_message, "Error: No video file produced")
                return None
        else:
            logger.error(f'Error executing command: {error_msg}')
            if "rate limit" in error_msg:
                await client.edit_message(progress_message, "Rate limit hit. Please try again in 10-20 minutes.")
            elif "invalid credentials" in error_msg and use_auth:
                logger.info("Invalid credentials; retrying with anonymous mode")
                command = ['./crunchy-cli-v3.2.5-linux-x86_64', '--anonymous', 'archive', '-r', '1280x720', '-a', 'en-US', crunchyroll_link]
                process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = await process.communicate()
                if process.returncode == 0:
                    video_path = stdout.decode().strip()
                    logger.info(f"crunchy-cli stdout (anonymous): {video_path}")
                    if video_path and os.path.exists(video_path):
                        return video_path
                error_msg = stderr.decode().lower()
                if "rate limit" in error_msg:
                    await client.edit_message(progress_message, "Rate limit hit in anonymous mode. Please try again in 10-20 minutes.")
                else:
                    await client.edit_message(progress_message, f"Ripping failed: {error_msg}")
            else:
                await client.edit_message(progress_message, f"Ripping failed: {error_msg}")
            return None
    except Exception as e:
        logger.exception(f'Error executing command: {str(e)}')
        await client.edit_message(progress_message, f"Error: {str(e)}")
        return None

@client.on(events.NewMessage(pattern='/rip'))
async def handle_rip_command(event):
    try:
        # Extract URL
        args = event.raw_text.split(maxsplit=1)
        if len(args) < 2 or not args[1].strip():
            await event.respond("Error: No URL provided. Use /rip <Crunchyroll URL>")
            return
        crunchyroll_link = args[1].strip()
        if not crunchyroll_link.startswith('https://www.crunchyroll.com/watch/'):
            await event.respond("Error: Please provide a valid Crunchyroll watch URL (e.g., https://www.crunchyroll.com/watch/...)")
            return

        logger.info(f'Received rip command for {crunchyroll_link}')
        await event.respond("Ripping process started...")

        video_path = await execute_crunchy_command(crunchyroll_link, event.message)

        if video_path:
            start_time = time.time()
            total_size = os.path.getsize(video_path)  # Get actual file size for upload progress
            await client.send_file(
                event.chat_id,
                video_path,
                caption="Here is your ripped video!",
                progress=progress_for_telethon,
                progress_args=("Uploading", event.message, start_time, total_size)
            )
            logger.info(f'Successfully uploaded video to {event.chat_id}')
            # Clean up the video file
            try:
                os.remove(video_path)
                logger.info(f"Deleted video file: {video_path}")
            except Exception as e:
                logger.error(f"Failed to delete video file: {e}")
        else:
            logger.error("No video path returned; upload skipped")
    except Exception as e:
        await event.respond(f'Error: {str(e)}')
        logger.exception(f'Error: {str(e)}')

client.run_until_disconnected()
