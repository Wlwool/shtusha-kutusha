from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any

from discord import app_commands
from discord.ext import commands

from bot.database import (
    add_reminder,
    get_saved_utc_offset,
    get_user_reminders,
    get_utc_offset,
    set_utc_offset,
)
from bot.tz import (
    DEFAULT_UTC_OFFSET,
    MAX_UTC_OFFSET,
    MIN_UTC_OFFSET,
    format_local,
    format_utc_offset,
    parse_utc_offset,
)
from bot.ui.reminder_view import REMINDERS_PER_PAGE, ReminderListView, _scheduler_add
from bot.utils import parse_time

if TYPE_CHECKING:
    from bot.main import MyBot

logger = logging.getLogger(__name__)


class RemindersCog(commands.Cog, name="Напоминания"):
    """Команды для создания и просмотра напоминаний."""

    def __init__(self, bot: MyBot) -> None:
        self.bot = bot

    @commands.hybrid_command()  # type: ignore[arg-type]
    async def remind(
        self, ctx: commands.Context[Any], time_str: str, *, message: str
    ) -> None:
        """Установить напоминание.
        Примеры:
            /remind in 1 hour Приготовить пюрешку
            /remind через 30 минут Позвонить тёще
            /remind 18:30 Встреча с дружочками-пирожочками
            /remind tomorrow at 9am Погладить кота
        """
        try:
            saved_offset = await get_saved_utc_offset(ctx.author.id)
            utc_offset = DEFAULT_UTC_OFFSET if saved_offset is None else saved_offset
            now = datetime.datetime.now(datetime.UTC)
            reminder_time = parse_time(time_str, utc_offset)

            if not reminder_time or reminder_time < now:
                await ctx.send(
                    "Пожалуйста, укажите корректное время в будущем (Например: 18:25)",
                    ephemeral=True,
                )
                logger.warning(
                    "Invalid time format from user %s: %s", ctx.author.id, time_str
                )
                return

            reminder_id = await add_reminder(
                ctx.author.id, ctx.channel.id, reminder_time, message
            )
            _scheduler_add(
                self.bot,
                reminder_id,
                reminder_time,
                (ctx.author.id, ctx.channel.id, message, reminder_id, 1),
            )
            text = (
                f"Напоминание установлено на {format_local(reminder_time, utc_offset)} "
                f"({format_utc_offset(utc_offset)})"
            )
            if saved_offset is None:
                text += "\nЕсли у вас другой часовой пояс, укажите его: /timezone +5"
            await ctx.send(text)
            logger.info(
                "New reminder added by %s: %s at %s",
                ctx.author.id,
                message,
                reminder_time,
            )
        except Exception as e:
            logger.exception("Ошибка в команде remind")
            await ctx.send(f"Ошибка: {e}", ephemeral=True)

    @commands.hybrid_command()  # type: ignore[arg-type]
    async def list_reminders(self, ctx: commands.Context[Any]) -> None:
        """Просмотреть свои напоминания."""
        reminders, total = await get_user_reminders(
            ctx.author.id, REMINDERS_PER_PAGE, 0
        )
        utc_offset = await get_utc_offset(ctx.author.id)
        view = ReminderListView(
            self.bot, ctx.author.id, reminders, total, 0, utc_offset=utc_offset
        )
        embed = view._build_embed()
        await ctx.send(embed=embed, view=view, ephemeral=True)

    @commands.hybrid_command()  # type: ignore[arg-type]
    @app_commands.describe(
        offset="Смещение от UTC, например +5 или -3 (от -12 до +14). Пусто: показать текущее"
    )
    async def timezone(self, ctx: commands.Context[Any], offset: str = "") -> None:
        """Задает часовой пояс (смещение от UTC) или показ текущего"""
        text = offset.strip()
        if not text:
            saved = await get_saved_utc_offset(ctx.author.id)
            current = DEFAULT_UTC_OFFSET if saved is None else saved
            note = " (по умолчанию)" if saved is None else ""
            await ctx.send(
                f"Ваш часовой пояс: {format_utc_offset(current)}{note}.\n"
                "Чтобы изменить, укажите смещение от UTC, например: /timezone +5",
                ephemeral=True,
            )
            return

        hours = parse_utc_offset(text)
        if hours is None:
            await ctx.send(
                "Не удалось распознать часовой пояс. Укажите целое число "
                f"от {MIN_UTC_OFFSET} до +{MAX_UTC_OFFSET}, например: /timezone +5",
                ephemeral=True,
            )
            return

        await set_utc_offset(ctx.author.id, hours)
        logger.info(
            "User %s set timezone to %s", ctx.author.id, format_utc_offset(hours)
        )
        await ctx.send(
            f"Часовой пояс установлен: {format_utc_offset(hours)}. Время в ваших "
            "напоминаниях теперь указывается по нему. Уже созданные напоминания "
            "сработают в то же время, изменится только то, как оно показывается.",
            ephemeral=True,
        )


async def setup(bot: MyBot) -> None:
    """Регистрация cog в боте."""
    await bot.add_cog(RemindersCog(bot))
