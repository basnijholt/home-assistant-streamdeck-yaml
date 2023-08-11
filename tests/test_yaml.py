"""Test the yaml loading."""
from io import StringIO
from pathlib import Path

import pytest
import yaml

from home_assistant_streamdeck_yaml import safe_load_yaml


def test_basic_yaml_loading(tmp_path: Path) -> None:
    """Test basic yaml loading."""
    content = """
    key: value
    """
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(content)

    with yaml_file.open() as f:
        data = safe_load_yaml(f)

    assert data == {"key": "value"}


def test_include_yaml_loading(tmp_path: Path) -> None:
    """Test yaml loading with includes."""
    main_content = """
    main_key: !include included.yaml
    """
    included_content = """
    included_key: included_value
    """
    main_file = tmp_path / "main.yaml"
    included_file = tmp_path / "included.yaml"
    main_file.write_text(main_content)
    included_file.write_text(included_content)

    with main_file.open() as f:
        data = safe_load_yaml(f)

    assert data == {"main_key": {"included_key": "included_value"}}


def test_string_io_yaml_loading() -> None:
    """Test yaml loading with a string io."""
    content = """
    key: value
    """
    data = safe_load_yaml(StringIO(content))
    assert data == {"key": "value"}


def test_invalid_yaml() -> None:
    """Test yaml loading with invalid yaml."""
    content = """
    key: value
      another_key: another_value
    """
    with pytest.raises(yaml.YAMLError):
        safe_load_yaml(StringIO(content))


def test_missing_include_file(tmp_path: Path) -> None:
    """Test yaml loading where the !include file is missing."""
    main_content = """
    main_key: !include missing.yaml
    """
    main_file = tmp_path / "main.yaml"
    main_file.write_text(main_content)

    with pytest.raises(FileNotFoundError), main_file.open() as f:
        safe_load_yaml(f)


def test_non_existent_file(tmp_path: Path) -> None:
    """Test yaml loading with a non-existent file."""
    non_existent_file = tmp_path / "non_existent.yaml"

    with pytest.raises(FileNotFoundError), non_existent_file.open() as f:
        safe_load_yaml(f)
