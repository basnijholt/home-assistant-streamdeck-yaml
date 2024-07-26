<img src="https://user-images.githubusercontent.com/6897215/225175629-28f80bfb-3b0a-44ac-8b52-b719953958d7.png" align="right" style="width: 300px;" />

<h1 align="center">Home Assistant on Stream Deck</h1>
<h3 align="center">Configured via YAML (with templates) and running on Linux, MacOS, and Windows</h3>

Introducing: Home Assistant on Stream Deck!

If you use Home Assistant and want a seamless way to control it, you've come to the right place.
With this Python script, you can control your Home Assistant instance via a Stream Deck, making it easier than ever to manage your smart home devices and scenes.

**Key Features:**

- ✅ Easy to use
- 🛠️ Highly customizable
- 🧩 [Home Assistant Add-on support](https://github.com/basnijholt/home-assistant-streamdeck-yaml-addon)
- 🐧 Supports Linux, MacOS, and Windows
- 📁 YAML configuration
- 🏠 Runs from same machine as Home Assistant
- 🚀 Template support for advanced customization
- 💤 Automatically sync state of `entity_id` to turn display on/off
- 🎛️ (NEW!) Stream Deck Plus with dial support

\[[ToC](#books-table-of-contents)\]

**Why choose our solution over others?**

You might have seen a similar project ([`cgiesche/streamdeck-homeassistant`](https://github.com/cgiesche/streamdeck-homeassistant)) on Github before \[[†](https://github.com/cgiesche/streamdeck-homeassistant)\].
However, our solution is more versatile and allows you to connect a Stream Deck to the same Linux machine where Home Assistant is running.
The native Stream Deck software doesn't support Linux, but we've got you covered with the help of the [`python-elgato-streamdeck`](https://github.com/abcminiuser/python-elgato-streamdeck) library.
If you are looking for some inspiration, check out the [>20 Button Configurations ideas](#bulb-more-than-30-button-configurations-ideas) section below.

**Check out the video below to see it in action!**

https://user-images.githubusercontent.com/6897215/226788119-6c198ea6-2950-4f95-95dc-346c9e5b5cee.mp4

## :books: Table of Contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

  - [🌟 Share Your Success](#-share-your-success)
  - [:rocket: Getting Started](#rocket-getting-started)
    - [:house_with_garden: Installation as Home Assistant Add-on](#house_with_garden-installation-as-home-assistant-add-on)
    - [:whale: Installation with Docker](#whale-installation-with-docker)
    - [:computer: Installation without Docker](#computer-installation-without-docker)
      - [:penguin: Linux](#penguin-linux)
      - [:apple: MacOS](#apple-macos)
      - [:desktop_computer: Windows](#desktop_computer-windows)
  - [:gear: Configuration](#gear-configuration)
    - [:page_facing_up: `configuration.yaml`](#page_facing_up-configurationyaml)
    - [:link: Using `!include` for Modular Configuration](#link-using-include-for-modular-configuration)
    - [:clipboard: Config YAML configuration](#clipboard-config-yaml-configuration)
    - [:bookmark_tabs: Page YAML configuration](#bookmark_tabs-page-yaml-configuration)
    - [:white_square_button: Button YAML configuration](#white_square_button-button-yaml-configuration)
- [:bulb: More than 30 Button Configurations ideas](#bulb-more-than-30-button-configurations-ideas)
  - [Additional documentation](#additional-documentation)
    - [Support for Streamdeck Plus :plus:](#support-for-streamdeck-plus-plus)
      - [Configuration.yaml](#configurationyaml)
      - [Configuring the Dials](#configuring-the-dials)
      - [Types of Dial specific attributes](#types-of-dial-specific-attributes)
    - [Jinja variables](#jinja-variables)
    - [Touchscreen events](#touchscreen-events)
    - [Include variables](#include-variables)
      - [page.yaml](#pageyaml)
      - [includes/button.yaml](#includesbuttonyaml)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## 🌟 Share Your Success

I love hearing from users!
If you're using Home Assistant StreamDeck YAML in your projects, please consider opening an issue on the [GitHub repository](https://github.com/basnijholt/home-assistant-streamdeck-yaml/issues/new) to let me know.
Your feedback and success stories not only help to improve the library but also inspire others in the community.
By sharing your experience, you can contribute to the growth and development of Home Assistant StreamDeck YAML.
I truly appreciate your support!

## :rocket: Getting Started

Follow the steps below to get up and running with Home Assistant on Stream Deck.

### :house_with_garden: Installation as Home Assistant Add-on

<details>
<summary>Click to expand.</summary>

1. In your Home Assistant instance, navigate to **Supervisor** > **Add-on Store**.
1. Click the menu icon (three vertical dots) in the top right corner and select **Repositories**.
1. Add the following repository URL: `https://github.com/basnijholt/home-assistant-streamdeck-yaml-addon`.
1. The add-on should now appear in the **Add-on Store**. Click on "Home Assistant Stream Deck YAML" and then click "Install".
1. After the installation is complete, configure the add-on using either the `.env` file or the individual configuration options (see the [add-on configuration documentation](https://github.com/basnijholt/home-assistant-streamdeck-yaml-addon#add-on-configuration-gear) for more information).
1. Start the add-on and check the logs for any errors.

</details>

### :whale: Installation with Docker

<details>
<summary>Click to expand.</summary>

1. Edit the [`.env.example`](.env.example) file and rename it to `.env`.
1. Setup a [`configuration.yaml` file (see below)](#configuration).
1. Install Docker, see [this](https://docs.docker.com/get-docker/) page for instructions
1. Use the [`basnijholt/home-assistant-streamdeck-yaml:latest`](https://hub.docker.com/r/basnijholt/home-assistant-streamdeck-yaml) Docker image with:

```bash
docker run --rm -it --privileged --env-file=$(pwd)/.env -v $(pwd)/:/app/ basnijholt/home-assistant-streamdeck-yaml:latest
```

Or use the a `docker-compose` file, an example of which is here: [`docker-compose.yaml`](docker-compose.yaml)

Optionally, you can build the Docker image yourself with:

```bash
docker build -t basnijholt/home-assistant-streamdeck-yaml:latest .
```

</details>

### :computer: Installation without Docker

<details>
<summary>Click to expand common steps for Linux :penguin:, :apple: MacOS, and :desktop_computer: Windows.</summary>

1. Run `pip install -e .` in the repo folder to install the required dependencies.
1. Edit the [`.env.example`](.env.example) file and rename it to `.env`.
1. Setup a [`configuration.yaml` file (see below)](#configuration).
1. Follow the platform-specific steps for [Linux](#linux), [MacOS](#macos), or [Windows](#windows).

</details>

#### :penguin: Linux

<details>
<summary>Click to expand.</summary>

On **Linux** you need to install some extra dependencies:

```bash
sudo apt-get update
sudo apt-get install -y libudev-dev libusb-1.0-0-dev libhidapi-libusb0 libffi-dev
```

and add a udev rule to allow access to the Stream Deck, run `sudo nano /etc/udev/rules.d/99-streamdeck.rules` and add the following line:

```bash
SUBSYSTEMS=="usb", ATTRS{idVendor}=="0fd9", GROUP="users", TAG+="uaccess"
```

</details>

#### :apple: MacOS

<details>
<summary>Click to expand.</summary>

On **MacOS** you need to install some extra dependencies:

```bash
brew install hidapi cairo libffi
```

</details>

#### :desktop_computer: Windows

<details>
<summary>Click to expand.</summary>

For **Windows**, see [this](https://python-elgato-streamdeck.readthedocs.io/en/stable/pages/backend_libusb_hidapi.html#windows) page.

</details>

## :gear: Configuration

1. Create a `configuration.yaml` file in the same directory.
1. Choose one of the two usage options:

- Option 1: With environment variables. (See [`.env.example`](.env.example) for details)
- Option 2: With command-line arguments. (Run `home-assistant-streamdeck-yaml -h` to see the available options)

You're all set! 🎉

Now you can enjoy controlling your smart home devices with ease.
Check out the [`configuration.yaml`](configuration.yaml) file for an example configuration or feel free to share your own with the community.

Happy controlling! 🏠💡🎮

### :page_facing_up: `configuration.yaml`

Here's an example `configuration.yaml` file to help

```yaml
brightness: 100  # Default brightness of the Stream Deck (0-100)
state_entity_id: binary_sensor.anyone_home  # Entity to sync display state with
auto_reload: true  # Automatically reload the configuration file when it changes
pages:
  - name: Home
    buttons:
      - entity_id: light.bedroom_lights
        service: light.toggle
        text: |
          Bedroom
          lights
      - icon: netflix.png
        service: script.start_spotify
      - icon: xbox.png
        service: script.start_xbox
      - icon_mdi: restart
        service: homeassistant.restart
        text: |
          Restart
          HA
      # Special light control page
      - entity_id: light.living_room_lights
        special_type: light-control
        special_type_data:
          colormap: hsv
        text: |
          Living room
          lights

      # Move pages
      - special_type: previous-page
      - special_type: next-page
  - name: Example
    buttons:
      # Empty button
      - special_type: empty
      # Change pages
      - special_type: go-to-page
        special_type_data: Home
      - special_type: go-to-page
        special_type_data: 0
      - special_type: previous-page
      - special_type: next-page
  - name: Other
    buttons:
      # Spotify playlist
      - service_data:
          id: playlist:37i9dQZF1DXaRycgyh6kXP
          source: KEF LS50
        icon: "spotify:playlist/37i9dQZF1DXaRycgyh6kXP"  # Downloads the cover art
        service: script.start_spotify
      # (Advanced) Use templates!
      - entity_id: media_player.kef_ls50
        service: media_player.volume_set
        service_data:
          volume_level: '{{ (state_attr("media_player.kef_ls50", "volume_level") - 0.05) | max(0) }}'
          entity_id: media_player.kef_ls50
        text: '{{ (100 * state_attr("media_player.kef_ls50", "volume_level")) | int }}%'
        text_size: 16
        icon_mdi: "volume-minus"
      - special_type: go-to-page
        special_type_data: 0
```

### :link: Using `!include` for Modular Configuration

> Warning: This feature does not work in the add-on version of this library at the moment.

To make your configuration more organized and maintainable, you can use the `!include` directive to split your configuration into multiple files, just like you can do in Home Assistant.
This is especially useful for large setups or when you want to share certain configurations across multiple setups.

For example, if you have a set of common buttons that you want to use across multiple pages, you can define them in a separate YAML file and then include them in your main configuration:

```yaml
# includes/home.yaml
- entity_id: light.bedroom_lights
  service: light.toggle
  text: |
    Bedroom
    lights
- icon: netflix.png
  service: script.start_spotify
```

In your main configuration:

```yaml
# configuration.yaml
pages:
  - name: Home
    buttons: !include includes/home.yaml
  ...
```

By using `!include`, you can keep your configuration clean and easily reusable.

> **Warning:** Any other directives that Home Assistant supports, such as `!secret` or `!include_dir_list`, are not supported by this library.

### :clipboard: Config YAML configuration

Each YAML config can take the following configuration

<!-- CODE:START -->
<!-- from home_assistant_streamdeck_yaml import Config -->
<!-- print(Config.to_markdown_table()) -->
<!-- CODE:END -->
<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->
| Variable name     | Description                                                                                                                                                                                                                                                                               | Default   | Type            |
|:------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------|:----------------|
| `pages`           | A list of `Page`s in the configuration.                                                                                                                                                                                                                                                   |           | `List[Page]`    |
| `anonymous_pages` | A list of anonymous Pages in the configuration. These pages are hidden and not displayed when cycling through the pages. They can only be reached using the `special_type: 'go-to-page'` button. Designed for single use, these pages return to the previous page upon clicking a button. |           | `List[Page]`    |
| `state_entity_id` | The entity ID to sync display state with. For example `input_boolean.streamdeck` or `binary_sensor.anyone_home`.                                                                                                                                                                          | `None`    | `Optional[str]` |
| `brightness`      | The default brightness of the Stream Deck (0-100).                                                                                                                                                                                                                                        | `100`     | `int`           |
| `auto_reload`     | If True, the configuration YAML file will automatically be reloaded when it is modified.                                                                                                                                                                                                  | `False`   | `bool`          |

<!-- OUTPUT:END -->

### :bookmark_tabs: Page YAML configuration

Each button can take the following configuration

<!-- CODE:START -->
<!-- from home_assistant_streamdeck_yaml import Page -->
<!-- print(Page.to_markdown_table()) -->
<!-- CODE:END -->
<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->
| Variable name   | Description                    | Default   | Type           |
|:----------------|:-------------------------------|:----------|:---------------|
| `name`          | The name of the page.          |           | `str`          |
| `buttons`       | A list of buttons on the page. |           | `List[Button]` |
| `dials`         | A list of dials on the page.   |           | `List[Dial]`   |

<!-- OUTPUT:END -->

### :white_square_button: Button YAML configuration

Each button can take the following configuration

<!-- CODE:START -->
<!-- from home_assistant_streamdeck_yaml import Button -->
<!-- print(Button.to_markdown_table()) -->
<!-- CODE:END -->
<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->
| Variable name           | Allow template   | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Default   | Type                                                                                                            |
|:------------------------|:-----------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------|:----------------------------------------------------------------------------------------------------------------|
| `entity_id`             | ✅                | The `entity_id` that this button controls. This entity will be passed to the `service` when the button is pressed. The button is re-rendered whenever the state of this entity changes.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |           | `Optional[str]`                                                                                                 |
| `linked_entity`         | ✅                | A secondary entity_id that is used for updating images and states                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |           | `Optional[str]`                                                                                                 |
| `service`               | ✅                | The `service` that will be called when the button is pressed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |           | `Optional[str]`                                                                                                 |
| `service_data`          | ✅                | The `service_data` that will be passed to the `service` when the button is pressed. If empty, the `entity_id` will be passed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |           | `Optional[Mapping[str, Any]]`                                                                                   |
| `target`                | ✅                | The `target` that will be passed to the `service` when the button is pressed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |           | `Optional[Mapping[str, Any]]`                                                                                   |
| `text`                  | ✅                | The text to display on the button. If empty, no text is displayed. You might want to add `\n` characters to spread the text over several lines, or use the `\|` character in YAML to create a multi-line string.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |           | `str`                                                                                                           |
| `text_color`            | ✅                | Color of the text. If empty, the color is `white`, unless an `entity_id` is specified, in which case the color is `amber` when the state is `on`, and `white` when it is `off`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |           | `Optional[str]`                                                                                                 |
| `text_size`             | ❌                | Integer size of the text.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | `12`      | `int`                                                                                                           |
| `text_offset`           | ❌                | The text's position can be moved up or down from the center of the button, and this movement is measured in pixels. The value can be positive (for upward movement) or negative (for downward movement).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |           | `int`                                                                                                           |
| `icon`                  | ✅                | The icon filename to display on the button. Make the path absolute (e.g., `/config/streamdeck/my_icon.png`) or relative to the `assets` directory (e.g., `my_icon.png`). If empty, a icon with `icon_background_color` and `text` is displayed. The icon can be a URL to an image, like `'url:https://www.nijho.lt/authors/admin/avatar.jpg'`, or a `spotify:` icon, like `'spotify:album/6gnYcXVaffdG0vwVM34cr8'`. If the icon is a `spotify:` icon, the icon will be downloaded and cached. The icon can also display a partially complete ring, like a progress bar, or sensor value, like `ring:25` for a 25% complete ring.                                                                        |           | `Optional[str]`                                                                                                 |
| `icon_mdi`              | ✅                | The Material Design Icon to display on the button. If empty, no icon is displayed. See https://mdi.bessarabov.com/ for a list of icons. The SVG icon will be downloaded and cached.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |           | `Optional[str]`                                                                                                 |
| `icon_background_color` | ✅                | A color (in hex format, e.g., '#FF0000') for the background of the icon (if no `icon` is specified).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `#000000` | `str`                                                                                                           |
| `icon_mdi_color`        | ✅                | The color of the Material Design Icon (in hex format, e.g., '#FF0000'). If empty, the color is derived from `text_color` but is less saturated (gray is mixed in).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |           | `Optional[str]`                                                                                                 |
| `icon_gray_when_off`    | ❌                | When specifying `icon` and `entity_id`, if the state is `off`, the icon will be converted to grayscale.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |           | `bool`                                                                                                          |
| `delay`                 | ✅                | The delay (in seconds) before the `service` is called. This is useful if you want to wait before calling the `service`. Counts down from the time the button is pressed. If while counting the button is pressed again, the timer is cancelled. Should be a float or template string that evaluates to a float.                                                                                                                                                                                                                                                                                                                                                                                         |           | `Union[float, str]`                                                                                             |
| `special_type`          | ❌                | Special type of button. If no specified, the button is a normal button. If `next-page`, the button will go to the next page. If `previous-page`, the button will go to the previous page. If `turn-off`, the button will turn off the SteamDeck until any button is pressed. If `empty`, the button will be empty. If `go-to-page`, the button will go to the page specified by `special_type_data` (either an `int` or `str` (name of the page)). If `light-control`, the button will control a light, and the `special_type_data` can be a dictionary, see its description. If `reload`, the button will reload the configuration file when pressed.                                                  |           | `Optional[Literal['next-page', 'previous-page', 'empty', 'go-to-page', 'turn-off', 'light-control', 'reload']]` |
| `special_type_data`     | ✅                | Data for the special type of button. If `go-to-page`, the data should be an `int` or `str` (name of the page). If `light-control`, the data should optionally be a dictionary. The dictionary can contain the following keys: The `colors` key and a value a list of max (`n_keys_on_streamdeck - 5`) hex colors. The `color_temp_kelvin` key and a value a list of max (`n_keys_on_streamdeck - 5`) color temperatures in Kelvin. The `colormap` key and a value a colormap (https://matplotlib.org/stable/tutorials/colors/colormaps.html) can be used. This requires the `matplotlib` package to be installed. If no list of `colors` or `colormap` is specified, 10 equally spaced colors are used. |           | `Optional[Any]`                                                                                                 |

<!-- OUTPUT:END -->

# :bulb: More than 30 Button Configurations ideas

Here are >30 interesting uses for the Stream Deck with Home Assistant (click on text to expand):

<!-- CODE:START -->
<!-- import os, sys -->
<!-- sys.path.append(os.path.abspath(".")) -->
<!-- from tests.test_examples import generate_readme_entry -->
<!-- print(generate_readme_entry()) -->
<!-- CODE:END -->
<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->


<details>
<summary>1. 🎭 Activate a scene:</summary>

```yaml
- service: scene.turn_on
  service_data:
    entity_id: scene.movie_night
  icon_mdi: movie
  text: Movie Night
```

</details>

<details>
<summary>2. 🚪 Toggle a cover (e.g., blinds or garage door):</summary>

```yaml
- entity_id: cover.garage_door
  service: cover.toggle
  icon_mdi: "{{ 'garage-open' if is_state('cover.garage_door', 'open') else 'garage-lock' }}"
  text: "{{ 'Open' if is_state('cover.garage_door', 'open') else 'Close' }}"
```

</details>

<details>
<summary>3. 🤖 Start or stop the vacuum robot:</summary>

```yaml
- entity_id: vacuum.cleaning_robot
  service: >-
    {% if is_state('vacuum.cleaning_robot', 'docked') %}
    vacuum.start
    {% else %}
    vacuum.return_to_base
    {% endif %}
  icon_mdi: robot-vacuum
  text: >-
    {% if is_state('vacuum.cleaning_robot', 'docked') %}
    Start
    {% else %}
    Stop
    {% endif %}
```

</details>

<details>
<summary>4. 🔇 Mute/unmute a media player:</summary>

```yaml
- entity_id: media_player.living_room_speaker
  service: media_player.volume_mute
  service_data:
    entity_id: media_player.living_room_speaker
    is_volume_muted: >-
      {% if is_state_attr('media_player.living_room_speaker', 'is_volume_muted', true) %}
      false
      {% else %}
      true
      {% endif %}
  icon_mdi: >-
    {% if is_state_attr('media_player.living_room_speaker', 'is_volume_muted', true) %}
    volume-off
    {% else %}
    volume-high
    {% endif %}
  text: >-
    {% if is_state_attr('media_player.living_room_speaker', 'is_volume_muted', true) %}
    Unmute
    {% else %}
    Mute
    {% endif %}
```

</details>

<details>
<summary>5. 🌟 Control the brightness of a light (+10% on press):</summary>

```yaml
- entity_id: light.living_room_lights
  service: light.turn_on
  service_data:
    entity_id: light.living_room_lights
    brightness: >-
      {% set current_brightness = state_attr('light.living_room_lights', 'brightness') %}
      {% set next_brightness = (current_brightness + 25.5) % 255 %}
      {{ next_brightness | min(255) | int }}
  text: >-
    {% set current_brightness = state_attr('light.living_room_lights', 'brightness') %}
    {% set brightness_pct = (current_brightness / 255) * 100 %}
    {{ brightness_pct | round }}%
```

</details>

<details>
<summary>6. 🌀 Toggle a fan:</summary>

```yaml
- entity_id: fan.bedroom_fan
  service: fan.toggle
  icon_mdi: "{{ 'fan' if is_state('fan.bedroom_fan', 'on') else 'fan-off' }}"
  text: |
    Bedroom
    {{ 'On' if is_state('fan.bedroom_fan', 'on') else 'Off' }}
```

</details>

<details>
<summary>7. 🔒 Lock/unlock a door after 30 seconds:</summary>

```yaml
- entity_id: lock.front_door
  service: lock.toggle
  delay: "{{ 30 if is_state('lock.front_door', 'unlocked') else 0 }}"
  icon_mdi: "{{ 'door-open' if is_state('lock.front_door', 'unlocked') else 'door-closed' }}"
  text: |
    Front Door
    {{ 'Unlocked' if is_state('lock.front_door', 'unlocked') else 'Locked' }}
  text_size: 10
  text_color: "{{ 'green' if is_state('lock.front_door', 'unlocked') else 'red' }}"
```

</details>

<details>
<summary>8. ⚠️ Arm/disarm an alarm system after 30 seconds:</summary>

```yaml
- entity_id: alarm_control_panel.home_alarm
  delay: "{{ 0 if is_state('alarm_control_panel.home_alarm', 'armed_away') else 30 }}"
  service: "{{ 'alarm_control_panel.alarm_disarm' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'alarm_control_panel.alarm_arm_away' }}"
  icon_mdi: "{{ 'shield-check' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'shield-off' }}"
  text: |
    {{ 'Disarm' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'Arm' }}
    Alarm
  text_color: "{{ 'red' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'green' }}"
```

Arm the alarm system in 30 seconds if it's disarmed, disarm it immediately if it's armed.

</details>

<details>
<summary>9. ⏰ Set an alarm time for the next day:</summary>

```yaml
- service: input_datetime.set_datetime
  service_data:
    entity_id: input_datetime.alarm_time
    time: "{{ '07:00:00' if states('input_datetime.alarm_time') != '07:00:00' else '08:00:00' }}"
  icon_mdi: "alarm"
  text: |
    Set Alarm
    {{ '7AM' if states('input_datetime.alarm_time') != '07:00:00' else '8AM' }}
```

</details>

<details>
<summary>10. ⏯️ Control a media player (play/pause):</summary>

```yaml
- entity_id: media_player.living_room_speaker
  service: media_player.media_play_pause
  icon_mdi: "{{ 'pause' if is_state('media_player.living_room_speaker', 'playing') else 'play' }}"
  text: "{{ 'Pause' if is_state('media_player.living_room_speaker', 'playing') else 'Play' }}"
```

</details>

<details>
<summary>11. 🎵 Control a media player (skip tracks):</summary>

```yaml
- entity_id: media_player.living_room_speaker
  service: media_player.media_next_track
  icon_mdi: skip-next
  text: Next Track
```

</details>

<details>
<summary>12. 🌈 Set a specific color for a light:</summary>

```yaml
- entity_id: light.living_room_light
  service: light.toggle
  service_data:
    color_name: blue
  icon_mdi: "{{ 'lightbulb-on' if is_state('light.living_room_light', 'on') else 'lightbulb-off' }}"
  text: Blue Light
```

</details>

<details>
<summary>13. 🌡️ Adjust the thermostat between two specific temperatures:</summary>

```yaml
- entity_id: climate.living_room
  service: climate.set_temperature
  service_data:
    temperature: "{{ 17 if state_attr('climate.living_room', 'temperature') >= 22 else 22 }}"
  icon_mdi: thermostat
  text: |
    Set
    {{ '17°C' if state_attr('climate.living_room', 'temperature') >= 22 else '22°C' }}
    ({{ state_attr('climate.living_room', 'current_temperature') }}°C now)
```

</details>

<details>
<summary>14. 📲 Trigger a script to send a notification to your mobile device:</summary>

```yaml
- service: script.send_mobile_notification
  icon_mdi: bell
  text: Send Notification
```


Which uses this script (which needs to be defined in Home Assistant):

```yaml
send_mobile_notification:
  alias: "Send Mobile Notification"
  sequence:
    - service: notify.mobile_app_<your_device_name>
      data:
        message: "Your custom notification message."
```


</details>

<details>
<summary>15. 🌆 Toggle a day/night mode (using an input_boolean):</summary>

```yaml
- entity_id: input_boolean.day_night_mode
  service: input_boolean.toggle
  icon_mdi: "{{ 'weather-night' if is_state('input_boolean.day_night_mode', 'on') else 'weather-sunny' }}"
  text: |
    {{ 'Night' if is_state('input_boolean.day_night_mode', 'on') else 'Day' }}
    Mode
```

</details>

<details>
<summary>16. 📺 Control a TV (e.g., turn on/off or change input source):</summary>

```yaml
- entity_id: media_player.living_room_tv
  service: media_player.select_source
  service_data:
    source: HDMI 1
  text: HDMI 1
```

</details>

<details>
<summary>17. 🔦 Control a group of lights (e.g., turn on/off or change color):</summary>

```yaml
- entity_id: group.living_room_lights
  service: light.turn_on
  service_data:
    color_name: red
  icon_mdi: "{{ 'lightbulb-group' if is_state('group.living_room_lights', 'on') else 'lightbulb-group-off' }}"
  text: Red Group Lights
```

</details>

<details>
<summary>18. 🔔 Trigger a script to announce the doorbell:</summary>

```yaml
- service: script.trigger_doorbell_announcement
  text: Doorbell Announcement
```


Which uses this script (which needs to be defined in Home Assistant):

```yaml
trigger_doorbell_announcement:
  alias: "Trigger Doorbell Announcement"
  sequence:
    - service: tts.google_translate_say
      data:
        entity_id: media_player.<your_media_player>
        message: "Someone is at the door."
```


</details>

<details>
<summary>19. ⏰ Enable/disable a sleep timer (using an input_boolean):</summary>

```yaml
- entity_id: input_boolean.sleep_timer
  service: input_boolean.toggle
  icon_mdi: "{{ 'timer' if is_state('input_boolean.sleep_timer', 'on') else 'timer-off' }}"
  text: |
    {{ 'Cancel' if is_state('input_boolean.sleep_timer', 'on') else 'Set' }}
    Sleep Timer
```

</details>

<details>
<summary>20. 🌡️ Display current temperature:</summary>

```yaml
- entity_id: sensor.weather_temperature
  text: '{{ states("sensor.weather_temperature") }}°C'
  text_size: 16
  icon_mdi: weather-cloudy
```

</details>

<details>
<summary>21. 📶 Toggle Wi-Fi on/off (using a switch):</summary>

```yaml
- entity_id: switch.wifi_switch
          service: switch.toggle
          icon_mdi: "{{ 'wifi' if is_state('switch.wifi_switch', 'on') else 'wifi-off' }}"
          text: |
            {{ 'Disable' if is_state('switch.wifi_switch', 'on') else 'Enable' }}
            Wi-Fi
```

</details>

<details>
<summary>22. 🗣️ Activate voice assistant:</summary>

```yaml
- service: script.activate_voice_assistant
  icon_mdi: microphone
  text: Voice Assistant
```


Which uses this script (which needs to be defined in Home Assistant):

```yaml
activate_voice_assistant:
  alias: "Activate Voice Assistant"
  sequence:
    - service: media_player.play_media
      target:
        entity_id: media_player.<your_media_player>
      data:
        media_content_id: "http://<your_url>/<filename>.mp3"
        media_content_type: "music"
```


</details>

<details>
<summary>23. 🌿 Start/Stop air purifier:</summary>

```yaml
- entity_id: switch.air_purifier
  service: switch.toggle
  icon_mdi: "{{ 'air-purifier' if is_state('switch.air_purifier', 'on') else 'air-purifier-off' }}"
  text: |
    {{ 'Stop' if is_state('switch.air_purifier', 'on') else 'Start' }}
    Air Purifier
```

</details>

<details>
<summary>24. 📼 Start/stop a security camera recording:</summary>

```yaml
- service: script.toggle_security_camera_recording
  icon_mdi: cctv
  text: Toggle Camera Recording
```


Which uses this script (which needs to be defined in Home Assistant):

```yaml
toggle_security_camera_recording:
  alias: "Toggle Security Camera Recording"
  sequence:
    - service: camera.record
      target:
        entity_id: camera.<your_camera>
      data:
        duration: 10
        lookback: 2
        filename: "/config/www/recordings/camera_{{ now().strftime('%Y%m%d_%H%M%S') }}.mp4"
```


</details>

<details>
<summary>25. 🌙 Enable/disable a nightlight after 30 min:</summary>

```yaml
- entity_id: light.nightlight
  service: light.toggle
  delay: 1800
  icon_mdi: "{{ 'lightbulb-on' if is_state('light.nightlight', 'on') else 'lightbulb-off' }}"
  text: "{{ 'Disable' if is_state('light.nightlight', 'on') else 'Enable' }} Nightlight"
  text_color: "{{ 'red' if is_state('light.nightlight', 'on') else 'green' }}"
```

</details>

<details>
<summary>26. 🔥 Control a smart fireplace:</summary>

```yaml
- entity_id: switch.smart_fireplace
  service: switch.toggle
  icon_mdi: "{{ 'fire' if is_state('switch.smart_fireplace', 'on') else 'fire-off' }}"
  text: |
    {{ 'Turn Off' if is_state('switch.smart_fireplace', 'on') else 'Turn On' }}
    Fireplace
```

</details>

<details>
<summary>27. 🔌 Toggle a smart plug:</summary>

```yaml
- entity_id: switch.smart_plug
  service: switch.toggle
  icon_mdi: "{{ 'power-plug' if is_state('switch.smart_plug', 'on') else 'power-plug-off' }}"
  text: |
    {{ 'Turn Off' if is_state('switch.smart_plug', 'on') else 'Turn On' }}
    Smart Plug
```

</details>

<details>
<summary>28. 💦 Toggle irrigation system:</summary>

```yaml
- entity_id: switch.irrigation_system
  service: switch.toggle
  icon_mdi: "{{ 'water' if is_state('switch.irrigation_system', 'on') else 'water-off' }}"
  text: |
    {{ 'Turn Off' if is_state('switch.irrigation_system', 'on') else 'Turn On' }}
    Irrigation
```

</details>

<details>
<summary>29. 🌤️ Change the position of a cover (e.g., blinds or curtains):</summary>

```yaml
- entity_id: cover.living_room_blinds
  service: cover.set_cover_position
  service_data:
    position: "{{ 0 if state_attr('cover.living_room_blinds', 'position') >= 50 else 100 }}"
  icon_mdi: window-shutter
  text: |
    {{ 'Close' if state_attr('cover.living_room_blinds', 'position') >= 50 else 'Open' }}
    Blinds
```

</details>

<details>
<summary>30. 📺 Toggle a media player (e.g., TV) and show different images:</summary>

```yaml
- entity_id: media_player.tv
  service: media_player.toggle
  icon: >
    {% if is_state('media_player.tv', 'on') %}
    url:https://raw.githubusercontent.com/basnijholt/home-assistant-streamdeck-yaml/main/assets/fireplace.png
    {% else %}
    url:https://raw.githubusercontent.com/basnijholt/home-assistant-streamdeck-yaml/main/assets/hogwarts.png
    {% endif %}
  text: >
    Turn {{ 'Off' if is_state('media_player.tv', 'on') else 'On' }}
```

</details>

<details>
<summary>31. ⏰ Turn off all lights in 60s:</summary>

```yaml
- entity_id: light.all_lights
  service: light.turn_off
  text: |
    Turn off
    in 60s
  delay: 60
```

</details>

<details>
<summary>32. 🌡️ Display outside temperature with a ring indicator:</summary>

```yaml
- entity_id: sensor.temperature_sensor_outside_temperature
  icon: >
    {%- set temp = states('sensor.temperature_sensor_outside_temperature') -%}
    {%- set min_temp = -10 -%}
    {%- set max_temp = 40 -%}
    {%- set pct = ((temp - min_temp) / (max_temp - min_temp)) * 100 -%}
    ring:{{ pct | round }}
  text: |
    {%- set temp = states('sensor.temperature_sensor_outside_temperature') -%}
    Outside
    {{ temp | round(1) }}°C
```

This sets 0% to -10°C and 100% to 40°C.

</details>

<details>
<summary>33. 🔄 Reload the `configuration.yaml` file:</summary>

```yaml
- special_type: reload
```

When pressed, the `configuration.yaml` is reloaded.

</details>


<!-- OUTPUT:END -->

## Additional documentation

### Support for Streamdeck Plus :plus:

#### Configuration.yaml

The `configuration.yaml` for the Streamdeck plus is very similar to the configuration for the regular streamdeck, you only have to add the dials for each page if you want to use them, you can of course also leave it if you don't want to use dials for a specific page.
An example of a `configuration.yaml` with dials would look like this.

```yaml
brightness: 100
auto_reload: true
state_entity_id: input_boolean.streamdeck
pages:
  - name: home
    buttons: !include includes/home.yaml
  - name: room_1
    dials: !include includes/room_1_dials.yaml
    buttons: !include includes/room_1.yaml
```

#### Configuring the Dials

The dials also work very similarly to the buttons, you only have to specify an event type such as push if you would like to push the button or turn if you would like to make a turn event.
Here is an example for a turn event dial that controls a light.
And shows a ring indicator and the numerical value of the brightness.

```yaml
- entity_id: light.testing
  service: light.turn_on
  service_data:
    brightness: '{{ dial_value | int}}'
  icon: >
    {%- set state = dial_value() -%}
    {%- set min = dial_attr("min") -%}
    {%- set max = dial_attr("max") -%}
    {%- set pct = ((state - min) / (max - min)) * 100 -%}
    ring:{{ pct | round }}
  text: >
    {%- set state = dial_value()  -%}
    {%- set ha_state = states('light.testing') -%}
    {%- if ha_state == "off" and dial_value() == 0 -%}
        {{"off"}}
    {%- else -%}
        {{state | int}}
    {%- endif -%}
  state_attribute: brightness
  allow_touchscreen_events: true
  delay: 0.5
  dial_event_type: TURN
  attributes:
    min: 0
    max: 100
    step: 1
```

#### Types of Dial specific attributes

The attributes until `delay` are the same as for the buttons, but there are some additional attributes that are specific to the dials.

<!-- CODE:START -->
<!-- from home_assistant_streamdeck_yaml import Dial -->
<!-- print(Dial.to_markdown_table()) -->
<!-- CODE:END -->
<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->
| Variable name              | Allow template   | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Default   | Type                            |
|:---------------------------|:-----------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------|:--------------------------------|
| `entity_id`                | ✅                | The `entity_id` that this dial controls. This entity will be passed to the `service` when the dial is rotated. The dial is re-rendered whenever the state of this entity changes.                                                                                                                                                                                                                                                                                                                                                                                                                                                 |           | `Optional[str]`                 |
| `linked_entity`            | ✅                | A secondary entity_id that is used for updating images and states                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |           | `Optional[str]`                 |
| `service`                  | ✅                | The `service` that will be called when the dial is rotated.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |           | `Optional[str]`                 |
| `service_data`             | ✅                | The `service_data` that will be passed to the `service` when the dial is rotated. If empty, the `entity_id` will be passed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |           | `Optional[Mapping[str, Any]]`   |
| `target`                   | ✅                | The `target` that will be passed to the `service` when the dial is rotated.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |           | `Optional[Mapping[str, Any]]`   |
| `text`                     | ✅                | The text to display above the dial. If empty, no text is displayed. You might want to add `\n` characters to spread the text over several lines, or use the `\|` character in YAML to create a multi-line string.                                                                                                                                                                                                                                                                                                                                                                                                                 |           | `str`                           |
| `text_color`               | ✅                | Color of the text. If empty, the color is `white`, unless an `entity_id` is specified, in which case the color is `amber` when the state is `on`, and `white` when it is `off`.                                                                                                                                                                                                                                                                                                                                                                                                                                                   |           | `Optional[str]`                 |
| `text_size`                | ❌                | Integer size of the text.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | `12`      | `int`                           |
| `text_offset`              | ❌                | The text's position can be moved up or down from the center of the dial, and this movement is measured in pixels. The value can be positive (for upward movement) or negative (for downward movement).                                                                                                                                                                                                                                                                                                                                                                                                                            |           | `int`                           |
| `icon`                     | ✅                | The icon filename to display above the dial. Make the path absolute (e.g., `/config/streamdeck/my_icon.png`) or relative to the `assets` directory (e.g., `my_icon.png`). If empty, a icon with `icon_background_color` and `text` is displayed. The icon can be a URL to an image, like `'url:https://www.nijho.lt/authors/admin/avatar.jpg'`, or a `spotify:` icon, like `'spotify:album/6gnYcXVaffdG0vwVM34cr8'`. If the icon is a `spotify:` icon, the icon will be downloaded and cached. The icon can also display a partially complete ring, like a progress bar, or sensor value, like `ring:25` for a 25% complete ring. |           | `Optional[str]`                 |
| `icon_mdi`                 | ✅                | The Material Design Icon to display above the dial. If empty, no icon is displayed. See https://mdi.bessarabov.com/ for a list of icons. The SVG icon will be downloaded and cached.                                                                                                                                                                                                                                                                                                                                                                                                                                              |           | `Optional[str]`                 |
| `icon_background_color`    | ✅                | A color (in hex format, e.g., '#FF0000') for the background of the icon (if no `icon` is specified).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | `#000000` | `str`                           |
| `icon_mdi_color`           | ✅                | The color of the Material Design Icon (in hex format, e.g., '#FF0000'). If empty, the color is derived from `text_color` but is less saturated (gray is mixed in).                                                                                                                                                                                                                                                                                                                                                                                                                                                                |           | `Optional[str]`                 |
| `icon_gray_when_off`       | ❌                | When specifying `icon` and `entity_id`, if the state is `off`, the icon will be converted to grayscale.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |           | `bool`                          |
| `delay`                    | ✅                | The delay (in seconds) before the `service` is called. This counts down from the specified time and collects the called turn events and sends the bundled value to Home Assistant after the dial hasn't been turned for the specified time in delay.                                                                                                                                                                                                                                                                                                                                                                              |           | `Union[float, str]`             |
| `dial_event_type`          | ✅                | The event type of the dial that will trigger the service. Either `DialEventType.TURN` or `DialEventType.PUSH`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |           | `Optional[str]`                 |
| `state_attribute`          | ✅                | The attribute of the entity which gets used for the dial state.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |           | `Optional[str]`                 |
| `attributes`               | ✅                | Sets the attributes of the dial. `min`: The minimal value of the dial. `max`: The maximal value of the dial. `step`: the step size by which the value of the dial is increased by on an event.                                                                                                                                                                                                                                                                                                                                                                                                                                    |           | `Optional[Mapping[str, float]]` |
| `allow_touchscreen_events` | ✅                | Whether events from the touchscreen are allowed, for example set the minimal value on `SHORT` and set maximal value on `LONG`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |           | `bool`                          |

<!-- OUTPUT:END -->



### Jinja variables

- `dial_value`: The current local value of the dial (might be different from the states value if a delay is set)
- `dial_attr`: A function that takes a string as an argument and returns the value of the attribute with that name
- `states`: The current state of the entity in home assistant

### Touchscreen events

- If your streamdeck has a touchscreen you can switch pages by swiping left or right on the screen.
- If you set the `allow_touchscreen_events` attribute you can also use the touchscreen to set the value of a dial to the max or min value of that dial by tapping or holding the area of the dial.

### Include variables

>[!NOTE]
> Include variables work independent from the Streamdeck plus feature and can be used in every supported streamdeck version.

You can also pass variables with the include tag to the included file.
This can be useful for creating templates and reusing them for multiple entities.
Here is an example of how you can use include variables in your configuration:

#### page.yaml

```yaml
- !include {file: includes/button.yaml, vars: {entity_id: light.living_room, icon_mdi:lightbulb, text: Living Room Lights}}
- !include {file: includes/button.yaml, vars: {entity_id: light.bed, icon_mdi:lightbulb, text: Bed Room Lights}}
# Other files you might want to include...
```

Anything that is within the vars dictionary and in the `${variable_name}` format will be replaced upon loading the YAML file when starting the application.
Other text in the same format but not in the vars dictionary will not be replaced.

#### includes/button.yaml

```yaml
- entity_id: ${entity_id}
  service: light.toggle
  icon_mdi: ${icon_mdi}
  text: ${text}
```

In this case `${entity_id}`, `${icon_mdi}`, and `${text}` will be replaced with the values given in the `!include` tag.<F11>
