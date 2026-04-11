"""Cog управления статусом и восстановлением напоминаний."""

from __future__ import annotations
import datetime
import logging
from typing import TYPE_CHECKING, List
import discord
from discord import Activity, ActivityType
from discord.ext import commands, tasks
from bot.database import get_pending_reminders

if TYPE_CHECKING:
    from bot.main import MyBot

logger = logging.getLogger(__name__)


class StatusCog(commands.Cog, name="Статус"):
    """Управление статусом бота и восстановление напоминаний."""
    def __init__(self, bot: MyBot) -> None:
        self.bot = bot
        self._status_cycle = 0

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Срабатывает при запуске бота."""
        logger.info("%s успешно запущен!", self.bot.user)
        logger.info("Logged in as %s (ID: %s)", self.bot.user, self.bot.user.id)
        await self._restore_reminders()
        self._update_status.start()


    @tasks.loop(minutes=15)
    async def _update_status(self) -> None:
        """Обновление статуса каждые 15 минут."""
        try:
            activities = await self._get_live_stats()
            self._status_cycle = (self._status_cycle + 1) % len(activities)
            await self.bot.change_presence(
                activity=activities[self._status_cycle],
                status=discord.Status.online,
            )
            logger.info("Updated status to: %s", activities[self._status_cycle].name)
        except Exception as e:
            logger.error("Status update error: %s", e)


    async def _get_live_stats(self) -> List[Activity]:
        """Генерирует статусы с живой статистикой."""
        return [
            Activity(
                type=ActivityType.watching,
                name=f"за {len(self.bot.guilds)} сервером(-ами)",
            ),
            Activity(
                type=ActivityType.watching,
                name=f"на онлайн: {sum(g.member_count for g in self.bot.guilds)}",
            ),
            Activity(
                type=ActivityType.playing,
                name=f"игры в {round(self.bot.latency * 1000)}мс",
            ),
        ]

    async def _restore_reminders(self) -> None:
        """Восстановление напоминаний из базы данных при старте."""
        try:
            reminders = await get_pending_reminders()
            logger.info("Восстановление %d напоминания из базы данных", len(reminders))
            for reminder in reminders:
                reminder_id, user_id, channel_id, reminder_time, message, _ = reminder
                reminder_time = datetime.datetime.fromisoformat(reminder_time)
                self.bot.scheduler.add_job(
                    self.bot.send_reminder,
                    "date",
                    run_date=reminder_time,
                    args=(user_id, channel_id, message, reminder_id),
                    id=str(reminder_id),
                )
            logger.info("Успешно восстановлены все напоминания")
        except Exception as e:
            logger.error("Ошибка восстановления напоминаний: %s", e)


async def setup(bot: MyBot) -> None:
    """Регистрация cog в боте."""
    await bot.add_cog(StatusCog(bot))
