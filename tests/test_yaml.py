"""Test the yaml loading."""

from io import StringIO
from pathlib import Path
from typing import Any, cast

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


def test_variable_substitution_in_include(tmp_path: Path) -> None:
    """Test variable substitution in included YAML files."""
    config_content = """
    brightness: 100
    state_entity_id: binary_sensor.anyone_home
    auto_reload: true
    return_to_home_after_no_presses:
      duration: 10
      home_page: Home
    pages:
      - !include {file: includes/light_page_plus.yaml, vars: {name: living-room-lights, eid: light.living_room}}
    """
    light_page_plus_content = """
    name: ${name}
    dials:
      - entity_id: ${eid}
        service: light.turn_on
        service_data:
          color_temp_kelvin: '{{ dial_value() | int}}'
        icon: >
          light-temperature-bar:
        text: Color Temp
        state_attribute: color_temp_kelvin
        allow_touchscreen_events: true
        delay: 0.5
        dial_event_type: TURN
        attributes:
          step: 500
          min: 2202
          max: 6535
    """

    # Create directory structure
    includes_dir = tmp_path / "includes"
    includes_dir.mkdir()
    config_file = tmp_path / "config.yaml"
    light_page_plus_file = includes_dir / "light_page_plus.yaml"

    config_file.write_text(config_content)
    light_page_plus_file.write_text(light_page_plus_content)

    # Load config with safe_load_yaml
    with config_file.open() as f:
        data = safe_load_yaml(f)

    # Assert that data is a dictionary to satisfy MyPy
    data = cast("dict[str, Any]", data)

    assert data["pages"][0]["dials"][0]["entity_id"] == "light.living_room", (
        "Failed to substitute ${eid} with light.living_room in entity_id"
    )

    # Additional check: name field should be substituted correctly
    assert data["pages"][0]["name"] == "living-room-lights", (
        "Failed to substitute ${eid} with light.living_room in name"
    )
