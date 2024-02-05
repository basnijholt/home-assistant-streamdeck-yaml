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


def test_include_file_paths(tmp_path: Path) -> None:
    """Test yaml loading returns all included file paths when return_included_paths is True."""
    main_content = """
    main_key1: !include included1.yaml
    main_key2: !include included2.yaml
    """
    included_content1 = """
    included_key1: included_value1
    """
    included_content2 = """
    included_key2: included_value2
    """
    main_file = tmp_path / "main.yaml"
    included_file1 = tmp_path / "included1.yaml"
    included_file2 = tmp_path / "included2.yaml"

    main_file.write_text(main_content)
    included_file1.write_text(included_content1)
    included_file2.write_text(included_content2)

    with main_file.open() as f:
        data, included_files = safe_load_yaml(f, return_included_paths=True)

    assert data == {
        "main_key1": {"included_key1": "included_value1"},
        "main_key2": {"included_key2": "included_value2"},
    }
    assert set(included_files) == {included_file1, included_file2}
