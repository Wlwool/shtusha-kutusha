from __future__ import annotations
import datetime
import logging
from typing import TYPE_CHECKING
from discord.ext import commands
from bot.database import add_reminder, get_user_reminders
from bot.ui.reminder_view import REMINDERS_PER_PAGE, ReminderListView, _scheduler_add
from bot.utils import parse_time

if TYPE_CHECKING:
    from bot.main import MyBot

logger = logging.getLogger(__name__)


class RemindersCog(commands.Cog, name="Напоминания"):
    """Команды для создания и просмотра напоминаний."""
    def __init__(self, bot: MyBot) -> None:
        self.bot = bot

    @commands.hybrid_command()
    async def remind(self, ctx: commands.Context, time_str: str, *, message: str) -> None:
        """Установить напоминание.
        Примеры:
            /remind in 1 hour Приготовить пюрешку
            /remind через 30 минут Позвонить тёще
            /remind 18:30 Встреча с дружочками-пирожочками
            /remind tomorrow at 9am Погладить кота
        """
        try:
            now = datetime.datetime.now()
            reminder_time = parse_time(time_str)

            if not reminder_time or reminder_time < now:
                await ctx.send(
                    "Пожалуйста, укажите корректное время в будущем (Например: 18:25)",
                    ephemeral=True,
                )
                logger.warning("Invalid time format from user %s: %s", ctx.author.id, time_str)
                return

            reminder_id = await add_reminder(
                ctx.author.id, ctx.channel.id, reminder_time, message
            )
            _scheduler_add(
                self.bot,
                reminder_id,
                reminder_time,
                (ctx.author.id, ctx.channel.id, message, reminder_id),
            )
            await ctx.send(
                f"Напоминание установлено на {reminder_time.strftime('%d-%m-%Y %H:%M')}"
            )
            logger.info(
                "New reminder added by %s: %s at %s", ctx.author.id, message, reminder_time
            )
        except Exception as e:
            logger.error("Error in remind command: %s", e)
            await ctx.send(f"Ошибка: {e}", ephemeral=True)

    @commands.hybrid_command()
    async def list_reminders(self, ctx: commands.Context) -> None:
        """Просмотреть свои напоминания."""
        reminders, total = await get_user_reminders(ctx.author.id, REMINDERS_PER_PAGE, 0)
        view = ReminderListView(ctx.author.id, reminders, total, 0)
        embed = view._build_embed()
        await ctx.send(embed=embed, view=view, ephemeral=True)


async def setup(bot: MyBot) -> None:
    """Регистрация cog в боте."""
    await bot.add_cog(RemindersCog(bot))
