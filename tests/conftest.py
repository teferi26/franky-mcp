from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from franky_mcp.data import Dataset, default_data_dir, load_dataset
from franky_mcp.service import FrankyService

SAMPLE_DIR = default_data_dir()


@pytest.fixture(scope="session")
def dataset() -> Dataset:
    return load_dataset(SAMPLE_DIR)


@pytest.fixture(scope="session")
def service(dataset: Dataset) -> FrankyService:
    return FrankyService(dataset)


@pytest.fixture
def sample_copy(tmp_path: Path) -> Path:
    """A writable copy of the sample dataset for corruption tests."""
    target = tmp_path / "data"
    shutil.copytree(SAMPLE_DIR, target)
    return target


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
