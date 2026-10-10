"""Cog управления статусом и восстановлением напоминаний."""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING, List
import discord
from discord import Activity, ActivityType
from discord.ext import commands, tasks
from bot.database import get_overdue_reminders, get_pending_reminders
from bot.ui.reminder_view import _scheduler_add

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
        if not self._update_status.is_running():
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
            logger.exception("Ошибка обновления статуса: %s", e)


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
            restored = 0
            for reminder in reminders:
                _scheduler_add(
                    self.bot,
                    reminder.id,
                    reminder.reminder_time,
                    (
                        reminder.user_id,
                        reminder.channel_id,
                        reminder.message,
                        reminder.id,
                        reminder.version,
                    ),
                )
                restored += 1
            logger.info("Успешно восстановлены %d напоминаний", restored)

            overdue = await get_overdue_reminders()
            if overdue:
                logger.warning(
                    "Найдено %d пропущенных напоминаний, отправляю сейчас", len(overdue)
                )
            for reminder in overdue:
                await self.bot.send_reminder(
                    reminder.user_id,
                    reminder.channel_id,
                    reminder.message,
                    reminder.id,
                    reminder.version,
                )
        except Exception:
            logger.exception("Ошибка восстановления напоминаний")


async def setup(bot: MyBot) -> None:
    """Регистрация cog в боте."""
    await bot.add_cog(StatusCog(bot))
