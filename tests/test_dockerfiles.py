"""Regression tests for Docker image layout."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILES = ("Dockerfile.latest", "Dockerfile.locked")
APP_SOURCE_DIR = "/opt/home-assistant-streamdeck-yaml"
RUNTIME_CONFIG = "/app/configuration.yaml"


def test_docker_images_install_application_outside_user_config_mount() -> None:
    """Bind-mounting user config onto /app must not hide the installed module."""
    for dockerfile in DOCKERFILES:
        text = (ROOT / dockerfile).read_text()

        assert f"WORKDIR {APP_SOURCE_DIR}" in text, dockerfile
        assert f"COPY . {APP_SOURCE_DIR}/" in text, dockerfile
        assert f"COPY .git {APP_SOURCE_DIR}/.git" in text, dockerfile


def test_docker_images_default_to_mounted_configuration() -> None:
    """The documented Docker command mounts configuration.yaml into /app."""
    for dockerfile in DOCKERFILES:
        text = (ROOT / dockerfile).read_text()

        assert f"ENV STREAMDECK_CONFIG={RUNTIME_CONFIG}" in text, dockerfile
        assert "WORKDIR /app" in text, dockerfile
