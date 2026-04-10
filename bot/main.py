import os
import logging
import discord
import datetime
from discord.ext import commands, tasks
from discord import Activity, ActivityType
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dateparser import parse
from typing import List
from dotenv import load_dotenv
from bot.database import init_db, add_reminder, get_pending_reminders, delete_reminder, get_user_reminders, update_reminder, get_reminder
from bot.help_cmd import register_help_command

discord.voice_client.VoiceClient.warn_nacl = False

REMINDERS_PER_PAGE = 10


class EditReminderModal(discord.ui.Modal, title="Редактировать напоминание"):
    time_input = discord.ui.TextInput(
        label="Время (например: 18:00 или in 2 hours)",
        style=discord.TextStyle.short,
        required=True
    )
    message_input = discord.ui.TextInput(
        label="Текст напоминания",
        style=discord.TextStyle.paragraph,
        required=True
    )

    def __init__(self, reminder_id: int, current_time: str, current_message: str, view: "ReminderListView"):
        super().__init__()
        self.reminder_id = reminder_id
        self.view = view
        self.time_input.default = current_time
        self.message_input.default = current_message

    async def on_submit(self, interaction: discord.Interaction):
        try:
            now = datetime.datetime.now()
            new_time = parse(self.time_input.value, settings={'RELATIVE_BASE': now})
            if not new_time or new_time < now:
                await interaction.response.send_message("Укажите корректное время в будущем", ephemeral=True)
                return

            await update_reminder(self.reminder_id, reminder_time=new_time, message=self.message_input.value)
            try:
                bot.scheduler.remove_job(str(self.reminder_id))
            except Exception:
                pass
            bot.scheduler.add_job(
                send_reminder, 'date', run_date=new_time,
                args=(interaction.user.id, interaction.channel.id, self.message_input.value, self.reminder_id),
                id=str(self.reminder_id)
            )
            logger.info(f"Edited reminder {self.reminder_id} by user {interaction.user.id}")

            # Обновить view
            reminders, total = await get_user_reminders(interaction.user.id, REMINDERS_PER_PAGE, self.view.offset)
            self.view.reminders = reminders
            self.view.total = total
            self.view.clear_items()
            self.view._build_buttons()
            embed = self.view._build_embed()
            await interaction.response.edit_message(embed=embed, view=self.view)
        except Exception as e:
            logger.error(f"Error editing reminder {self.reminder_id}: {str(e)}")
            await interaction.response.send_message(f"Ошибка: {str(e)}", ephemeral=True)


class ReminderListView(discord.ui.View):
    """Пагинации списка напоминаний с кнопками удаления и редактирования"""
    def __init__(self, user_id: int, reminders: list, total: int, offset: int = 0):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.reminders = reminders
        self.total = total
        self.offset = offset
        self._build_buttons()

    def _build_buttons(self):
        """Кнопки: удаление, редактирование, пагинация"""
        for r in self.reminders:
            rid = r[0]
            # Кнопка удаления
            del_btn = discord.ui.Button(label=f"🗑️ {rid}", style=discord.ButtonStyle.red, custom_id=f"del:{rid}")
            del_btn.callback = self._make_delete_callback(rid)
            self.add_item(del_btn)
            # Кнопка редактирования
            edit_btn = discord.ui.Button(label=f"✏️ {rid}", style=discord.ButtonStyle.secondary, custom_id=f"edit:{rid}")
            edit_btn.callback = self._make_edit_callback(rid)
            self.add_item(edit_btn)

        prev_btn = discord.ui.Button(label="⬅️", style=discord.ButtonStyle.secondary, custom_id="prev", disabled=self.offset == 0)
        prev_btn.callback = self.prev_page
        self.add_item(prev_btn)

        next_btn = discord.ui.Button(label="➡️", style=discord.ButtonStyle.secondary, custom_id="next", disabled=self.offset + REMINDERS_PER_PAGE >= self.total)
        next_btn.callback = self.next_page
        self.add_item(next_btn)

    def _make_delete_callback(self, reminder_id: int):
        async def callback(interaction: discord.Interaction):
            await delete_reminder(reminder_id)
            try:
                bot.scheduler.remove_job(str(reminder_id))
            except Exception:
                pass
            logger.info(f"Deleted reminder {reminder_id} by user {self.user_id}")

            reminders, total = await get_user_reminders(self.user_id, REMINDERS_PER_PAGE, self.offset)
            self.reminders = reminders
            self.total = total
            self.clear_items()
            self._build_buttons()
            embed = self._build_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

    def _make_edit_callback(self, reminder_id: int):
        async def callback(interaction: discord.Interaction):
            reminder = await get_reminder(reminder_id)
            if not reminder:
                await interaction.response.send_message("Напоминание не найдено", ephemeral=True)
                return
            _rid, _uid, _cid, r_time, r_msg, _ = reminder
            dt = datetime.datetime.fromisoformat(r_time)
            time_str = dt.strftime("%d-%m-%Y %H:%M")

            modal = EditReminderModal(
                reminder_id=reminder_id,
                current_time=time_str,
                current_message=r_msg,
                view=self
            )
            await interaction.response.send_modal(modal)
        return callback

    async def prev_page(self, interaction: discord.Interaction):
        self.offset = max(0, self.offset - REMINDERS_PER_PAGE)
        await self._update_view(interaction)

    async def next_page(self, interaction: discord.Interaction):
        self.offset += REMINDERS_PER_PAGE
        await self._update_view(interaction)

    async def _update_view(self, interaction: discord.Interaction):
        reminders, _ = await get_user_reminders(self.user_id, REMINDERS_PER_PAGE, self.offset)
        self.reminders = reminders
        self.clear_items()
        self._build_buttons()
        embed = self._build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Это не ваши напоминания", ephemeral=True)
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
            rid, reminder_time, message, channel_id, _ = r
            dt = datetime.datetime.fromisoformat(reminder_time)
            time_str = dt.strftime("%d-%m-%Y %H:%M")
            embed.add_field(
                name=f"`#{rid}` — {time_str}",
                value=message[:100] + ("..." if len(message) > 100 else ""),
                inline=False
            )
        return embed


def is_admin():
    """Проверка админ прав пользователя"""
    async def predicate(ctx: commands.Context) -> bool:
        return ctx.author.id == int(os.getenv('ADMIN_ID'))
    return commands.check(predicate)


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )
    logging.getLogger('apscheduler').setLevel(logging.WARNING)

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
            help_command=None
        )
        self.status_cycle = 0
        self.scheduler = AsyncIOScheduler()

    async def setup_hook(self):
        logger.info('Инициализация бота и базы данных ...')
        await init_db()
        self.scheduler.start()
        register_help_command(self)
        await self.tree.sync()
        logger.info('Бот готов к работе')

    async def get_live_stats(self) -> List[Activity]:
        """Генерирует статусы с живой статистикой"""
        return [
            Activity(
                type=ActivityType.watching,
                name=f"за {len(self.guilds)} сервером(-ами)"
            ),
            Activity(
                type=ActivityType.watching,
                name=f"на онлайн: {sum(g.member_count for g in self.guilds)}"
            ),
            Activity(
                type=ActivityType.playing,
                name=f"игры в {round(self.latency * 1000)}мс"
            )
        ]


bot = MyBot()

@tasks.loop(minutes=15)
async def update_status():
    """Обновление статуса через определенное время tasks.loop(minutes=?)"""
    try:
        activities = await bot.get_live_stats()
        bot.status_cycle = (bot.status_cycle + 1) % len(activities)

        await bot.change_presence(
            activity=activities[bot.status_cycle],
            status=discord.Status.online
        )
        logger.info(f"Updated status to: {activities[bot.status_cycle].name}")
    except Exception as e:
        logger.error(f"Status update error: {str(e)}")


@bot.event
async def on_ready():
    logger.info(f'{bot.user} успешно запущен!')
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    await restore_reminders()
    update_status.start()


async def restore_reminders():
    """Восстановление напоминаний из базы данных"""
    try:
        reminders = await get_pending_reminders()
        logger.info(f"Восстановление {len(reminders)} напоминания из базы данных")
        for reminder in reminders:
            reminder_id, user_id, channel_id, reminder_time, message, _ = reminder
            reminder_time = datetime.datetime.fromisoformat(reminder_time)
            bot.scheduler.add_job(
                send_reminder,
                'date',
                run_date=reminder_time,
                args=(user_id, channel_id, message, reminder_id),
                id=str(reminder_id)
            )
        logger.info("Успешно восстановлены все напоминания")
    except Exception as e:
        logger.error(f"Ошибка восстановления напоминаний: {str(e)}")

async def send_reminder(user_id: int, channel_id: int, message: str, reminder_id: int):
    try:
        channel = bot.get_channel(channel_id)
        user = bot.get_user(user_id)
        if channel and user:
            await channel.send(f'{user.mention}, Вы просили напомнить: {message}')
            await delete_reminder(reminder_id)
            logger.info(f"Sent reminder {reminder_id} to user {user_id}")
        else:
            logger.warning(f"Не удается отправить напоминание {reminder_id} - канал или юзер не найдены")
    except Exception as e:
        logger.error(f"Ошибка отправки напоминания {reminder_id}: {str(e)}")


@bot.hybrid_command()
async def list_reminders(ctx: commands.Context):
    """Просмотреть свои напоминания"""
    reminders, total = await get_user_reminders(ctx.author.id, REMINDERS_PER_PAGE, 0)
    view = ReminderListView(ctx.author.id, reminders, total, 0)
    embed = view._build_embed()
    await ctx.send(embed=embed, view=view, ephemeral=True)


@bot.hybrid_command()
async def remind(ctx: commands.Context, time_str: str, *, message: str):
    """Установить напоминание: "через 1 час" или время "18:15" без кавычек
    Пример: /remind in 1 hour Приготовить пюрешечку с котлетками или /remind через 1 час(либо минуты)
    Пример 2: /remind 18:25 Приготовить пюрешечку с котлетками
    Поддерживаемые форматы:
        "in 1 hour" (через 1 час)
        "in 30 minutes" (через 30 минут)
        "tomorrow at 9am" (завтра в 9 утра)

    Абсолютное время:
    "2025-02-28 18:00"
    "28.02.2025 18:00"
    """
    try:
        now = datetime.datetime.now()
        reminder_time = parse(time_str, settings={'RELATIVE_BASE': now})

        if not reminder_time or reminder_time < now:
            await ctx.send("Пожалуйста, укажите корректное время в будущем (Например: 18:25)", ephemeral=True)
            logger.warning(f"Invalid time format from user {ctx.author.id}: {time_str}")
            return

        reminder_id = await add_reminder(ctx.author.id, ctx.channel.id, reminder_time, message)
        bot.scheduler.add_job(
            send_reminder,
            'date',
            run_date=reminder_time,
            args=(ctx.author.id, ctx.channel.id, message, reminder_id),
            id=str(reminder_id)
        )
        await ctx.send(f"Напоминание установлено на {reminder_time.strftime('%d-%m-%Y %H:%M')}")
        logger.info(f"New reminder added by {ctx.author.id}: {message} at {reminder_time}")
    except Exception as e:
        logger.error(f"Error in remind command: {str(e)}")
        await ctx.send(f"Ошибка: {str(e)}", ephemeral=True)


if __name__ == '__main__':
    try:
        logger.info("Starting bot...")
        bot.run(os.getenv('DISCORD_TOKEN'))
    except Exception as e:
        logger.critical(f"Failed to start bot: {str(e)}")
        raise
