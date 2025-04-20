import logging
from telethon import TelegramClient, events
from config import Config
import asyncio
import subprocess
import time
import math
from progress import progress_for_pyrogram, humanbytes, TimeFormatter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = TelegramClient('bot_session', Config.TELEGRAM_API_ID, Config.TELEGRAM_API_HASH).start(bot_token=Config.TELEGRAM_BOT_TOKEN)

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
            command = ['./crunchy-cli-v3.2.5-linux-x86_64', '--username', Config.CR_EMAIL, '--password', Config.CR_PASSWORD,
                       'archive', '-r', '1280x720', '-a', 'en-US', crunchyroll_link]
            use_auth = True
        else:
            command.insert(1, '--anonymous')
            logger.info("No valid credentials found; using anonymous mode")

        process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        start_time = time.time()
        progress_message = await client.send_message(message.chat_id, "Ripping in progress...")

        # Estimate total size (placeholder; ideally get from crunchy-cli output or metadata)
        total_size = 1000  # TODO: Replace with actual size if available
        total_data_read = 0

        while True:
            data = await process.stdout.read(1024)
            if not data:
                break
            total_data_read += len(data)
            # Use bot.py's progress_for_pyrogram for download progress
            await progress_for_pyrogram(total_data_read, total_size, "Downloading", progress_message, start_time)

        stdout, stderr = await process.communicate()
        error_msg = stderr.decode().lower()

        if process.returncode == 0:
            # Assume stdout contains the path to the downloaded video
            video_path = stdout.decode().strip()
            if video_path:
                return video_path
            else:
                logger.error("No video path returned by crunchy-cli")
                await client.edit_message_text(message.chat_id, progress_message.id, "Error: No video file produced")
                return None
        else:
            logger.error(f'Error executing command: {error_msg}')
            if "rate limit" in error_msg:
                await client.edit_message_text(message.chat_id, progress_message.id,
                                              "Rate limit hit. Please try again in 10-20 minutes.")
            elif "invalid credentials" in error_msg and use_auth:
                logger.info("Invalid credentials; retrying with anonymous mode")
                # Retry with anonymous mode
                command = ['./crunchy-cli-v3.2.5-linux-x86_64', '--anonymous', 'archive', '-r', '1280x720', '-a', 'en-US', crunchyroll_link]
                process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = await process.communicate()
                if process.returncode == 0:
                    video_path = stdout.decode().strip()
                    if video_path:
                        return video_path
                error_msg = stderr.decode().lower()
                if "rate limit" in error_msg:
                    await client.edit_message_text(message.chat_id, progress_message.id,
                                                  "Rate limit hit in anonymous mode. Please try again in 10-20 minutes.")
                else:
                    await client.edit_message_text(message.chat_id, progress_message.id, f"Ripping failed: {error_msg}")
            else:
                await client.edit_message_text(message.chat_id, progress_message.id, f"Ripping failed: {error_msg}")
            return None
    except Exception as e:
        logger.exception(f'Error executing command: {str(e)}')
        await client.edit_message_text(message.chat_id, progress_message.id, f"Error: {str(e)}")
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
            # Upload the video using progress.py's progress_for_pyrogram
            start_time = time.time()
            await client.send_file(
                event.chat_id,
                video_path,
                caption="Here is your ripped video!",
                progress=progress_for_pyrogram,
                progress_args=("Uploading", event.message, start_time)
            )
            logger.info(f'Successfully uploaded video to {event.chat_id}')
        else:
            logger.error("No video path returned; upload skipped")
    except Exception as e:
        await event.respond(f'Error: {str(e)}')
        logger.exception(f'Error: {str(e)}')

# Local progress_for_pyrogram for download progress (simplified)
async def progress_for_pyrogram(current, total, ud_type, message, start):
    now = time.time()
    diff = now - start
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
        progress_message = f"{ud_type}...\n\n" \
                          f"{progress} {percentage:.2f}%\n" \
                          f"Speed: {humanbytes(speed)}/s\n" \
                          f"ETA: {estimated_total_time_str}"
        await client.edit_message_text(chat_id=message.chat.id, message_id=message.id, text=progress_message)

client.run_until_disconnected()
