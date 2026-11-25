from pathlib import Path

from studybuddy.database import open_database
from studybuddy.queries import list_concepts


def concept_id(database: Path) -> str:
    with open_database(database) as connection:
        return list_concepts(connection)[0]["id"]


def database_dump(database: Path) -> list[str]:
    with open_database(database) as connection:
        return list(connection.iterdump())
