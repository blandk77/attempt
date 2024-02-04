import logging
from telethon import TelegramClient, events
from config import Config
import asyncio
import subprocess
import time
from progress import *

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Telegram client
client = TelegramClient('bot_session', Config.TELEGRAM_API_ID, Config.TELEGRAM_API_HASH).start(bot_token=Config.TELEGRAM_BOT_TOKEN)

# Define function to execute the crunchy-cli command asynchronously with progress tracking
async def execute_crunchy_command(crunchyroll_link, message):
    try:
        command = [
            './crunchy-cli-v3.2.5-linux-x86_64',
            '--credentials', f'"{Config.CR_EMAIL}:{Config.CR_PASSWORD}"',
            'archive', '-r', '1280x720', '-a', 'te-IN', '--ffmpeg-preset', 'h265-normal',
            crunchyroll_link
        ]
        process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Start time for progress tracking
        start_time = time.time()  

        # Send initial progress message
        progress_message = await client.send_message(message.chat_id, "Ripping in progress...")
        
        while True:
            data = await process.stdout.read(1024)
            if not data:
                break
            await progress.progress_for_pyrogram(
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
        # Catch the exception when login fails due to invalid credentials
        logger.error(f'Error executing command: {str(e)}')
        logger.info('Trying to rip without account credentials...')
        # Retry the command without account credentials
        command_without_credentials = [
            './crunchy-cli-v3.2.5-linux-x86_64',
            'archive', '-r', '1280x720', '-a', 'te-IN', '--ffmpeg-preset', 'h265-normal',
            crunchyroll_link
        ]
        process_without_credentials = await asyncio.create_subprocess_exec(*command_without_credentials, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return None
    except Exception as e:
        logger.exception(f'Error executing command: {str(e)}')
        return None

# Define event handler for incoming messages
@client.on(events.NewMessage(pattern='/rip'))
async def handle_rip_command(event):
    try:
        # Extract Crunchyroll link from message
        crunchyroll_link = event.raw_text.split('/rip', 1)[1].strip()
        logger.info(f'Received rip command for {crunchyroll_link}')

        # Send feedback to user that the ripping process has started
        await event.respond("Ripping process started...")

        # Execute the crunchy-cli command asynchronously with progress tracking
        ripped_video = await execute_crunchy_command(crunchyroll_link, event.message)

        if ripped_video:
            # Send the ripped video back to the user
            await client.send_file(event.chat_id, ripped_video, caption="Here is your ripped video!")
            logger.info(f'Successfully uploaded video to {event.chat_id}')
        else:
            # Respond to the user in case of errors
            await event.respond("Ripping process failed. Please try again later.")
    except Exception as e:
        # Respond with an error message
        await event.respond(f'Error: {str(e)}')
        logger.exception(f'Error: {str(e)}')

# Start the event loop
client.run_until_disconnected()
