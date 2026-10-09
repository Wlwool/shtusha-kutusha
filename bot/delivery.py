"""Доставка напоминаний в Discord."""

from __future__ import annotations

import datetime
import logging

import discord

from bot.database import delete_reminder, get_reminder

logger = logging.getLogger(__name__)

# Напоминание считается опоздавшим, если оно отправлено позже этого срока.
LATE_AFTER = datetime.timedelta(minutes=1)


def _is_late(scheduled: datetime.datetime, now: datetime.datetime) -> bool:
    return now - scheduled > LATE_AFTER


def _build_text(
    mention: str, message: str, scheduled: datetime.datetime, late: bool
) -> str:
    text = f"{mention}, Вы просили напомнить: {message}"
    if late:
        text += (
            f"\n(Напоминание опоздало: оно было назначено на "
            f"{scheduled:%d-%m-%Y %H:%M}, но бот в это время был недоступен.)"
        )
    return text


async def _drop_undeliverable(
    reminder_id: int, user_id: int, channel_id: int, message: str
) -> None:
    """Удалить напоминание, которое доставить нельзя: канал или пользователь удалены."""
    logger.warning(
        "Напоминание %d удалено: канал %d или пользователь %d не найдены. "
        "Текст напоминания: %s",
        reminder_id,
        channel_id,
        user_id,
        message,
    )
    await delete_reminder(reminder_id)


async def deliver_reminder(
    bot: discord.Client,
    user_id: int,
    channel_id: int,
    message: str,
    reminder_id: int,
    version: int,
) -> None:
    """Отправить напоминание и удалить его из базы.

    Устаревшие задачи (напоминание удалено или изменено) пропускаются.
    Вовремя сработавшее напоминание уходит в канал. Опоздавшее сначала
    отправляется в личные сообщения, а если не получилось, то в канал.
    Если канал или пользователь удалены, напоминание доставить нельзя:
    оно пишется в лог и удаляется. При других ошибках отправки напоминание
    остаётся в базе и будет отправлено при следующем запуске бота.
    """
    try:
        reminder = await get_reminder(reminder_id)
        if reminder is None:
            logger.info("Напоминание %d уже удалено, пропуск", reminder_id)
            return
        if reminder.version != version:
            logger.info(
                "Напоминание %d: версия задачи %d устарела (в базе %d), пропуск",
                reminder_id,
                version,
                reminder.version,
            )
            return

        try:
            user = bot.get_user(user_id) or await bot.fetch_user(user_id)
        except discord.NotFound:
            await _drop_undeliverable(reminder_id, user_id, channel_id, message)
            return

        late = _is_late(reminder.reminder_time, datetime.datetime.now())
        text = _build_text(user.mention, message, reminder.reminder_time, late)

        if late:
            try:
                await user.send(text)
            except discord.HTTPException:
                logger.warning(
                    "Напоминание %d: личные сообщения недоступны, отправляю в канал",
                    reminder_id,
                )
            else:
                await delete_reminder(reminder_id)
                logger.info(
                    "Опоздавшее напоминание %d отправлено в личные сообщения %d",
                    reminder_id,
                    user_id,
                )
                return

        try:
            channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
        except discord.NotFound:
            await _drop_undeliverable(reminder_id, user_id, channel_id, message)
            return

        await channel.send(text)
        await delete_reminder(reminder_id)
        logger.info("Отправлено напоминание %d пользователю %d", reminder_id, user_id)
    except Exception:
        logger.exception("Ошибка отправки напоминания %d", reminder_id)
