import datetime
from unittest.mock import AsyncMock, MagicMock

from bot import database
from bot.ui.reminder_view import EditReminderModal, ReminderListView

ORIGINAL_CHANNEL_ID = 111
OTHER_CHANNEL_ID = 222


async def test_edit_keeps_original_channel_in_scheduler(tmp_path, monkeypatch):
    """Правка из другого канала не меняет канал доставки в расписании."""
    monkeypatch.setattr(database, "DB_NAME", tmp_path / "edit_modal.db")
    await database.init_db()
    soon = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
    reminder_id = await database.add_reminder(1, ORIGINAL_CHANNEL_ID, soon, "text")
    reminders, total = await database.get_user_reminders(1)

    bot = MagicMock()
    view = ReminderListView(bot, 1, reminders, total)
    modal = EditReminderModal(bot, reminder_id, "18:00", "text", view)
    modal.time_input._value = "in 2 hours"
    modal.message_input._value = "new text"

    interaction = MagicMock()
    interaction.user.id = 1
    interaction.channel.id = OTHER_CHANNEL_ID
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_message = AsyncMock()

    await modal.on_submit(interaction)

    interaction.response.edit_message.assert_awaited_once()
    bot.scheduler.add_job.assert_called_once()
    job_args = bot.scheduler.add_job.call_args.kwargs["args"]
    assert job_args[1] == ORIGINAL_CHANNEL_ID
