import logging
import os

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands
from dotenv import load_dotenv

from bot.database import init_db
from bot.delivery import deliver_reminder
from bot.help_cmd import register_help_command
from bot.log_config import setup_logging

discord.voice_client.VoiceClient.warn_nacl = False

setup_logging()
logger = logging.getLogger(__name__)
load_dotenv()


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            help_command=None,
        )
        self.scheduler = AsyncIOScheduler()

    async def setup_hook(self) -> None:
        logger.info("Инициализация бота и базы данных ...")
        await init_db()
        self.scheduler.start()
        register_help_command(self)

        # Load cogs
        await self.load_extension("bot.cogs.status")
        await self.load_extension("bot.cogs.reminders")

        await self.tree.sync()
        logger.info("Бот готов к работе")

    async def send_reminder(
        self,
        user_id: int,
        channel_id: int,
        message: str,
        reminder_id: int,
        version: int,
    ) -> None:
        await deliver_reminder(self, user_id, channel_id, message, reminder_id, version)


bot = MyBot()


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN не задан: укажите его в файле .env")
    try:
        logger.info("Starting bot...")
        bot.run(token)
    except Exception:
        logger.critical("Failed to start bot", exc_info=True)
        raise
