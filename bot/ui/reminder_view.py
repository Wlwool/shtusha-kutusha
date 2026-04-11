from __future__ import annotations

import datetime
import logging

import discord
from apscheduler.jobstores.base import ConflictingIdError, JobLookupError

from bot.database import delete_reminder, get_reminder, get_user_reminders, update_reminder
from bot.utils import parse_time

logger = logging.getLogger(__name__)

REMINDERS_PER_PAGE = 10


def _scheduler_remove(bot, reminder_id: int) -> None:
    """Удалить задачу из scheduler, игнорируя 'не найдено'."""
    try:
        bot.scheduler.remove_job(str(reminder_id))
        logger.info("Removed scheduler job %s", reminder_id)
    except JobLookupError:
        logger.debug("Scheduler job %s already fired or removed", reminder_id)


def _scheduler_add(bot, reminder_id: int, run_date, args) -> None:
    """Добавить задачу, заменяя существующую с тем же ID."""
    try:
        bot.scheduler.add_job(
            bot.send_reminder,
            "date",
            run_date=run_date,
            args=args,
            id=str(reminder_id),
            replace_existing=True,
        )
        logger.info("Added scheduler job %s for %s", reminder_id, run_date)
    except ConflictingIdError:
        # На случай гонки — удалить и добавить заново
        _scheduler_remove(bot, reminder_id)
        bot.scheduler.add_job(
            bot.send_reminder,
            "date",
            run_date=run_date,
            args=args,
            id=str(reminder_id),
        )
        logger.info("Re-added scheduler job %s for %s", reminder_id, run_date)


class EditReminderModal(discord.ui.Modal, title="Редактировать напоминание"):
    """Модальное окно для редактирования напоминания."""

    time_input = discord.ui.TextInput(
        label="Время (например: 18:00 или in 2 hours)",
        style=discord.TextStyle.short,
        required=True,
    )
    message_input = discord.ui.TextInput(
        label="Текст напоминания",
        style=discord.TextStyle.paragraph,
        required=True,
    )

    def __init__(
        self,
        reminder_id: int,
        current_time: str,
        current_message: str,
        view: ReminderListView,
    ) -> None:
        super().__init__()
        self.reminder_id = reminder_id
        self.view = view
        self.time_input.default = current_time
        self.message_input.default = current_message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from bot.main import bot  # noqa: PLC0415

        try:
            new_time = parse_time(self.time_input.value)
            if not new_time or new_time < datetime.datetime.now():
                await interaction.response.send_message(
                    "Укажите корректное время в будущем", ephemeral=True
                )
                return

            await update_reminder(
                self.reminder_id,
                reminder_time=new_time,
                message=self.message_input.value,
            )

            job_args = (
                interaction.user.id,
                interaction.channel.id,
                self.message_input.value,
                self.reminder_id,
            )
            job_id = str(self.reminder_id)

            try:
                # reschedule_job корредно вычисляет next_run_time
                bot.scheduler.reschedule_job(
                    job_id,
                    trigger="date",
                    run_date=new_time,
                )
                # отдельно обновить аргументы (сообщение, channel_id и т.д.)
                bot.scheduler.modify_job(job_id, args=job_args)
                logger.info(
                    "Rescheduled job %s to %s for user %s",
                    self.reminder_id,
                    new_time,
                    interaction.user.id,
                )
            except JobLookupError:
                # Задача уже выполнилась или удалена — пересоздаём
                logger.warning(
                    "Scheduler job %s not found, re-creating", self.reminder_id
                )
                _scheduler_add(bot, self.reminder_id, new_time, job_args)

            logger.info(
                "Edited reminder %s by user %s", self.reminder_id, interaction.user.id
            )

            reminders, total = await get_user_reminders(
                interaction.user.id, REMINDERS_PER_PAGE, self.view.offset
            )
            self.view.reminders = reminders
            self.view.total = total
            self.view.clear_items()
            self.view._build_buttons()
            embed = self.view._build_embed()
            await interaction.response.edit_message(embed=embed, view=self.view)
        except Exception as e:
            logger.error("Error editing reminder %s: %s", self.reminder_id, e)
            await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)


class ReminderListView(discord.ui.View):
    """Пагинация списка напоминаний с кнопками удаления и редактирования."""

    def __init__(
        self, user_id: int, reminders: list, total: int, offset: int = 0
    ) -> None:
        super().__init__(timeout=120)
        self.user_id = user_id
        self.reminders = reminders
        self.total = total
        self.offset = offset
        self._build_buttons()

    def _build_buttons(self) -> None:
        """Создать кнопки удаления, редактирования и пагинации."""
        for r in self.reminders:
            rid = r[0]
            del_btn = discord.ui.Button(
                label=f"🗑️ {rid}", style=discord.ButtonStyle.red, custom_id=f"del:{rid}"
            )
            del_btn.callback = self._make_delete_callback(rid)
            self.add_item(del_btn)

            edit_btn = discord.ui.Button(
                label=f"✏️ {rid}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"edit:{rid}",
            )
            edit_btn.callback = self._make_edit_callback(rid)
            self.add_item(edit_btn)

        prev_btn = discord.ui.Button(
            label="⬅️",
            style=discord.ButtonStyle.secondary,
            custom_id="prev",
            disabled=self.offset == 0,
        )
        prev_btn.callback = self.prev_page
        self.add_item(prev_btn)

        next_btn = discord.ui.Button(
            label="➡️",
            style=discord.ButtonStyle.secondary,
            custom_id="next",
            disabled=self.offset + REMINDERS_PER_PAGE >= self.total,
        )
        next_btn.callback = self.next_page
        self.add_item(next_btn)

    def _make_delete_callback(self, reminder_id: int):
        async def callback(interaction: discord.Interaction) -> None:
            from bot.main import bot  # noqa: PLC0415

            await delete_reminder(reminder_id)
            _scheduler_remove(bot, reminder_id)
            logger.info("Deleted reminder %s by user %s", reminder_id, self.user_id)

            reminders, total = await get_user_reminders(
                self.user_id, REMINDERS_PER_PAGE, self.offset
            )
            self.reminders = reminders
            self.total = total
            self.clear_items()
            self._build_buttons()
            embed = self._build_embed()
            await interaction.response.edit_message(embed=embed, view=self)

        return callback

    def _make_edit_callback(self, reminder_id: int):
        async def callback(interaction: discord.Interaction) -> None:
            reminder = await get_reminder(reminder_id)
            if not reminder:
                await interaction.response.send_message(
                    "Напоминание не найдено", ephemeral=True
                )
                return
            _rid, _uid, _cid, r_time, r_msg, _ = reminder
            dt = datetime.datetime.fromisoformat(r_time)
            time_str = dt.strftime("%d-%m-%Y %H:%M")

            modal = EditReminderModal(
                reminder_id=reminder_id,
                current_time=time_str,
                current_message=r_msg,
                view=self,
            )
            await interaction.response.send_modal(modal)

        return callback

    async def prev_page(self, interaction: discord.Interaction) -> None:
        self.offset = max(0, self.offset - REMINDERS_PER_PAGE)
        await self._update_view(interaction)

    async def next_page(self, interaction: discord.Interaction) -> None:
        self.offset += REMINDERS_PER_PAGE
        await self._update_view(interaction)

    async def _update_view(self, interaction: discord.Interaction) -> None:
        reminders, _ = await get_user_reminders(
            self.user_id, REMINDERS_PER_PAGE, self.offset
        )
        self.reminders = reminders
        self.clear_items()
        self._build_buttons()
        embed = self._build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Это не ваши напоминания", ephemeral=True
            )
            return False
        return True

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Ваши напоминания", color=discord.Color.blue())
        page_num = (self.offset // REMINDERS_PER_PAGE) + 1
        total_pages = max(1, (self.total + REMINDERS_PER_PAGE - 1) // REMINDERS_PER_PAGE)
        embed.set_footer(text=f"Страница {page_num}/{total_pages} • Всего: {self.total}")

        if not self.reminders:
            embed.description = "Нет активных напоминаний"
            return embed

        for r in self.reminders:
            rid, reminder_time, message, _channel_id, _created_at = r
            dt = datetime.datetime.fromisoformat(reminder_time)
            time_str = dt.strftime("%d-%m-%Y %H:%M")
            embed.add_field(
                name=f"`# ID: {rid}` — {time_str}",
                value=message[:100] + ("..." if len(message) > 100 else ""),
                inline=False,
            )
        return embed
