"""Test module for image generation functions in home_assistant_streamdeck_yaml.

This module tests the generation of images combining text and icons using
_add_text_to_image and _init_icon, covering MDI-based icons, solid color icons,
and text-only cases.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageChops

from home_assistant_streamdeck_yaml import _add_text_to_image, _init_icon

# Define paths
ASSETS_PATH: Path = Path(__file__).parent.parent / "assets"
TEST_DIR: Path = Path(__file__).parent
FONT_PATH: Path = ASSETS_PATH / "Roboto-Regular.ttf"

# Mock ICON_PIXELS constant
ICON_PIXELS: int = 72

# List of (text_params, icon_params) tuples
# If you update this, you must regenerate the reference images
# to match the new parameters, by running the script directly.
IMAGE_PARAMETERS: list[tuple[dict | None, dict | None]] = [
    # Text + MDI-based icon
    (
        {
            "text": "Home",
            "text_size": 14,
            "text_color": "yellow",
            "text_offset": 5,
        },
        {
            "icon_filename": "xbox.png",
            "icon_mdi_margin": 10,
            "icon_mdi_color": "#FFFFFF",  # White
            "icon_background_color": "#000000",  # Black
            "size": (72, 72),
        },
    ),
    # Text + Solid color icon
    (
        {
            "text": "Blue",
            "text_size": 16,
            "text_color": "white",
            "text_offset": 0,
            "size": (72, 72),
        },
        {
            "icon_background_color": "blue",
            "size": (72, 72),
        },
    ),
    # Text only (no icon)
    (
        {
            "text": "NoIcon",
            "text_size": 12,
            "text_color": "red",
            "text_offset": 0,
            "size": (72, 72),
        },
        None,
    ),
    # Icon only (no text, MDI-based)
    (
        None,
        {
            "icon_mdi": "home",
            "icon_mdi_margin": 10,
            "icon_mdi_color": "#FFFFFF",
            "icon_background_color": "#000000",
            "size": (72, 72),
        },
    ),
    # Rectangle
    (
        {
            "text": "NoIcon",
            "text_size": 12,
            "text_color": "red",
            "text_offset": 0,
        },
        {
            "icon_mdi": "home",
            "icon_mdi_margin": 10,
            "icon_mdi_color": "#FFFFFF",
            "icon_background_color": "#000000",
            "size": (200, 100),
        },
    ),
]


def generate_image(text_params: dict | None, icon_params: dict | None) -> Image.Image:
    """Generate an image with the specified text and icon parameters."""
    # Determine image size
    size = (72, 72)  # Default
    if icon_params and "size" in icon_params:
        size = icon_params["size"]
    elif text_params and "size" in text_params:
        size = text_params["size"]

    # Generate base image
    if icon_params:
        icon_params = icon_params.copy()  # Avoid modifying original
        icon_params["size"] = size
        base_image = _init_icon(**icon_params)
    else:
        # Default to black image if no icon_params
        base_image = Image.new("RGB", size, (0, 0, 0))

    # Add text if text_params provided
    if text_params:
        assert FONT_PATH.exists(), f"Font not found at {FONT_PATH}"
        if "size" in text_params:
            assert text_params["size"] == size, (
                f"Text size {text_params['size']} must match image size {size}"
            )
        base_image = _add_text_to_image(
            image=base_image,
            font_filename=str(FONT_PATH),
            text_size=text_params["text_size"],
            text=text_params["text"],
            text_color=text_params["text_color"],
            text_offset=text_params["text_offset"],
        )

    return base_image


def create_reference_images() -> None:
    """Create reference images for testing and save them to the test directory."""
    for i, (text_params, icon_params) in enumerate(IMAGE_PARAMETERS, 1):
        reference_path = TEST_DIR / f"reference_image_{i}.png"
        image = generate_image(text_params, icon_params)
        image.save(reference_path)
        print(f"Reference image saved to {reference_path}")


@pytest.mark.parametrize(("text_params", "icon_params"), IMAGE_PARAMETERS)
def test_image_generation(text_params: dict | None, icon_params: dict | None) -> None:
    """Test that the generated image matches the reference image for each parameter set."""
    # Determine index to match reference filename
    index = IMAGE_PARAMETERS.index((text_params, icon_params)) + 1
    reference_path = TEST_DIR / f"reference_image_{index}.png"

    # Ensure reference image exists
    assert reference_path.exists(), f"Reference image not found at {reference_path}"

    # Generate the image
    generated_image = generate_image(text_params, icon_params)

    # Load the reference image
    reference_image = Image.open(reference_path)

    # Ensure both images are in RGB mode
    if generated_image.mode != "RGB":
        generated_image = generated_image.convert("RGB")
    if reference_image.mode != "RGB":
        reference_image = reference_image.convert("RGB")

    # Compare images
    diff = ImageChops.difference(generated_image, reference_image)
    diff_bbox = diff.getbbox()

    # Save generated and diff images for debugging if test fails
    if diff_bbox is not None:
        generated_filename = f"generated_image_{index}.png"
        diff_filename = f"diff_image_{index}.png"
        generated_image.save(TEST_DIR / generated_filename)
        diff.save(TEST_DIR / diff_filename)
        pytest.fail(
            f"Generated image differs from reference_image_{index}.png. "
            f"Check {generated_filename} and {diff_filename}",
        )

    # Assert no differences (bbox is None if images are identical)
    assert diff_bbox is None, f"Generated image differs from reference_image_{index}.png"


if __name__ == "__main__":
    # Run this manually to create all reference images
    create_reference_images()
