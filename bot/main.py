import os
import logging
import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from bot.database import init_db
from bot.help_cmd import register_help_command
from bot.log_config import setup_logging
from bot.utils import parse_time as _parse_time  # noqa: F401 для тестов

discord.voice_client.VoiceClient.warn_nacl = False

setup_logging()
logger = logging.getLogger(__name__)
load_dotenv()


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True
        super().__init__(
            command_prefix=commands.when_mentioned_or('!'),
            intents=intents,
            help_command=None,
        )
        self.scheduler = AsyncIOScheduler()

    async def setup_hook(self) -> None:
        logger.info('Инициализация бота и базы данных ...')
        await init_db()
        self.scheduler.start()
        register_help_command(self)

        # Load cogs
        await self.load_extension('bot.cogs.status')
        await self.load_extension('bot.cogs.reminders')

        await self.tree.sync()
        logger.info('Бот готов к работе')

    async def send_reminder(
        self, user_id: int, channel_id: int, message: str, reminder_id: int
    ) -> None:
        """Отправить напоминание пользователю и удалить из БД."""
        from bot.database import delete_reminder  # noqa: PLC0415

        try:
            channel = self.get_channel(channel_id)
            user = self.get_user(user_id)
            if channel and user:
                await channel.send(f'{user.mention}, Вы просили напомнить: {message}')
                await delete_reminder(reminder_id)
                logger.info("Sent reminder %d to user %d", reminder_id, user_id)
            else:
                logger.warning(
                    "Не удается отправить напоминание %d - канал или юзер не найдены",
                    reminder_id,
                )
        except Exception as e:
            logger.error("Ошибка отправки напоминания %d: %s", reminder_id, e)


bot = MyBot()


if __name__ == '__main__':
    try:
        logger.info("Starting bot...")
        bot.run(os.getenv('DISCORD_TOKEN'))
    except Exception as e:
        logger.critical("Failed to start bot: %s", e)
        raise
