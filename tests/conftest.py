from pathlib import Path

import pytest

from studybuddy.indexer import index_vault


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    root.mkdir()
    return root


@pytest.fixture
def database(tmp_path: Path) -> Path:
    return tmp_path / "data" / "studybuddy.sqlite3"


@pytest.fixture
def indexed(vault: Path, database: Path) -> tuple[Path, Path]:
    (vault / "network.md").write_text(
        "---\ntags: [network, 学习]\n---\n# Networking\n## TCP retries\nSee [[HTTP#Idempotency|retry safety]].\n",
        encoding="utf-8",
    )
    index_vault(vault, database)
    return vault, database
