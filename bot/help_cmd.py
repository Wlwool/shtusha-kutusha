import discord
from discord.ext import commands


def register_help_command(bot: commands.Bot):
    @bot.tree.command(name="help_remind", description="Список доступных команд и примеры использования")
    async def help_remind(interaction: discord.Interaction):
        embed = discord.Embed(title="Доступные команды", color=discord.Color.blue())

        embed.add_field(
            name="/remind <время> <текст>",
            value=(
                "Установить напоминание.\n"
                "Примеры:\n"
                "`/remind in 1 hour Приготовить пюрешку`\n"
                "`/remind через 30 минут Позвонить тёще`\n"
                "`/remind 18:30 Встреча с дружочками-пирожочками`\n"
                "`/remind tomorrow at 9am Погладить кота`"
            ),
            inline=False
        )

        embed.add_field(
            name="/list_reminders",
            value="Показать список активных напоминаний.\nКнопки удаления и редактирования доступны в самом сообщении.",
            inline=False
        )

        embed.add_field(
            name="/help_remind",
            value="Инструкция, как пользоваться ботом",
            inline=False
        )

        embed.add_field(
            name="Форматы времени",
            value=(
                "Относительное: `in 1 hour`, `через 30 минут`, `tomorrow at 9am`\n"
                "Абсолютное: `18:30`, `15.03.2025 09:00`, `15/03/2025 09:00`, `15-03-2025 09:00`"
            ),
            inline=False
        )

        embed.set_footer(text="Напоминания работают в рамках данного сервера")
        await interaction.response.send_message(embed=embed, ephemeral=True)
