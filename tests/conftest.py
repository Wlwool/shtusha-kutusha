"""Общие фикстуры: каждый тест работает с отдельной базой во временном каталоге."""

import pytest

from bot import database


@pytest.fixture(autouse=True)
async def temp_db(tmp_path, monkeypatch):
    """Подменяет путь к базе на временный файл и создаёт таблицу."""
    monkeypatch.setattr(database, "DB_NAME", tmp_path / "test.db")
    await database.init_db()
