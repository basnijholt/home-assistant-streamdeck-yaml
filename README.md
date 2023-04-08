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

[[ToC](#books-table-of-contents)]

**Why choose our solution over others?**

You might have seen a similar project ([`cgiesche/streamdeck-homeassistant`](https://github.com/cgiesche/streamdeck-homeassistant)) on Github before [[†](https://github.com/cgiesche/streamdeck-homeassistant)].
However, our solution is more versatile and allows you to connect a Stream Deck to the same Linux machine where Home Assistant is running.
The native Stream Deck software doesn't support Linux, but we've got you covered with the help of the [`python-elgato-streamdeck`](https://github.com/abcminiuser/python-elgato-streamdeck) library.
If you are looking for some inspiration, check out the [>20 Button Configurations ideas](#bulb-more-than-20-button-configurations-ideas) section below.

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
    - [:white_square_button: Button YAML configuration](#white_square_button-button-yaml-configuration)
- [:bulb: More than 20 Button Configurations ideas](#bulb-more-than-20-button-configurations-ideas)

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
2. Click the menu icon (three vertical dots) in the top right corner and select **Repositories**.
3. Add the following repository URL: `https://github.com/basnijholt/home-assistant-streamdeck-yaml-addon`.
4. The add-on should now appear in the **Add-on Store**. Click on "Home Assistant Stream Deck YAML" and then click "Install".
5. After the installation is complete, configure the add-on using either the `.env` file or the individual configuration options (see the [add-on configuration documentation](https://github.com/basnijholt/home-assistant-streamdeck-yaml-addon#add-on-configuration-gear) for more information).
6. Start the add-on and check the logs for any errors.

</details>

### :whale: Installation with Docker

<details>
<summary>Click to expand.</summary>

1. Edit the [`.env.example`](.env.example) file and rename it to `.env`.
2. Setup a [`configuration.yaml` file (see below)](#configuration).
3. Install Docker, see [this](https://docs.docker.com/get-docker/) page for instructions
4. Use the [`basnijholt/home-assistant-streamdeck-yaml:latest`](https://hub.docker.com/r/basnijholt/home-assistant-streamdeck-yaml) Docker image with:

```bash
docker run --rm -it --privileged --env-file=$(pwd)/.env -v $(pwd)/configuration.yaml:/app/configuration.yaml basnijholt/home-assistant-streamdeck-yaml:latest
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
2. Edit the [`.env.example`](.env.example) file and rename it to `.env`.
3. Setup a [`configuration.yaml` file (see below)](#configuration).
4. Follow the platform-specific steps for [Linux](#linux), [MacOS](#macos), or [Windows](#windows).

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
2. Choose one of the two usage options:
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

### :white_square_button: Button YAML configuration

Each button can take the following configuration

<!-- CODE:START -->
<!-- from home_assistant_streamdeck_yaml import Button -->
<!-- print(Button.to_markdown_table()) -->
<!-- CODE:END -->
<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->
| Variable name           | Allow template   | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | Default   | Type                                                                                                  |
|:------------------------|:-----------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------|:------------------------------------------------------------------------------------------------------|
| `entity_id`             | ✅                | The `entity_id` that this button controls. This entitity will be passed to the `service` when the button is pressed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |           | `Optional[str]`                                                                                       |
| `service`               | ✅                | The `service` that will be called when the button is pressed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |           | `Optional[str]`                                                                                       |
| `service_data`          | ✅                | The `service_data` that will be passed to the `service` when the button is pressed. If empty, the `entity_id` will be passed.                                                                                                                                                                                                                                                                                                                                                                                                                                                          |           | `Optional[Mapping[str, Any]]`                                                                         |
| `target`                | ✅                | The `target` that will be passed to the `service` when the button is pressed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |           | `Optional[Mapping[str, Any]]`                                                                         |
| `text`                  | ✅                | The text to display on the button. If empty, no text is displayed. You might want to add `\n` characters to spread the text over several lines, or use the `\|` character in YAML to create a multi-line string.                                                                                                                                                                                                                                                                                                                                                                       |           | `str`                                                                                                 |
| `text_color`            | ✅                | Color of the text. If empty, the color is `white`, unless an `entity_id` is specified, in which case the color is `amber` when the state is `on`, and `white` when it is `off`.                                                                                                                                                                                                                                                                                                                                                                                                        |           | `Optional[str]`                                                                                       |
| `text_size`             | ❌                | Integer size of the text.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | `12`      | `int`                                                                                                 |
| `icon`                  | ✅                | The icon filename to display on the button. Make the path absolute (e.g., `/config/streamdeck/my_icon.png`) or relative to the `assets` directory (e.g., `my_icon.png`). If empty, a icon with `icon_background_color` and `text` is displayed. The icon can be a URL to an image, like `'url:https://www.nijho.lt/authors/admin/avatar.jpg'`, or a `spotify:` icon, like `'spotify:album/6gnYcXVaffdG0vwVM34cr8'`. If the icon is a `spotify:` icon, the icon will be downloaded and cached.                                                                                          |           | `Optional[str]`                                                                                       |
| `icon_mdi`              | ✅                | The Material Design Icon to display on the button. If empty, no icon is displayed. See https://mdi.bessarabov.com/ for a list of icons. The SVG icon will be downloaded and cached.                                                                                                                                                                                                                                                                                                                                                                                                    |           | `Optional[str]`                                                                                       |
| `icon_background_color` | ✅                | A color (in hex format, e.g., '#FF0000') for the background of the icon (if no `icon` is specified).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | `#000000` | `str`                                                                                                 |
| `icon_mdi_color`        | ✅                | The color of the Material Design Icon (in hex format, e.g., '#FF0000'). If empty, the color is derived from `text_color` but is less saturated (gray is mixed in).                                                                                                                                                                                                                                                                                                                                                                                                                     |           | `Optional[str]`                                                                                       |
| `icon_gray_when_off`    | ❌                | When specifying `icon` and `entity_id`, if the state is `off`, the icon will be converted to grayscale.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |           | `bool`                                                                                                |
| `special_type`          | ❌                | Special type of button. If no specified, the button is a normal button. If `next-page`, the button will go to the next page. If `previous-page`, the button will go to the previous page. If `turn-off`, the button will turn off the SteamDeck until any button is pressed. If `empty`, the button will be empty. If `go-to-page`, the button will go to the page specified by `special_type_data` (either an `int` or `str` (name of the page)). If `light-control`, the button will control a light, and the `special_type_data` can be a dictionary, see its description.          |           | `Optional[Literal['next-page', 'previous-page', 'empty', 'go-to-page', 'turn-off', 'light-control']]` |
| `special_type_data`     | ✅                | Data for the special type of button. If `go-to-page`, the data should be an `int` or `str` (name of the page). If `light-control`, the data should optionally be a dictionary. The dictionary can contain the following keys: The `colors` key and a value a list of max (`n_keys_on_streamdeck - 5`) hex colors. The `colormap` key and a value a colormap (https://matplotlib.org/stable/tutorials/colors/colormaps.html) can be used. This requires the `matplotlib` package to be installed. If no list of `colors` or `colormap` is specified, 10 equally spaced colors are used. |           | `Optional[Any]`                                                                                       |

<!-- OUTPUT:END -->

# :bulb: More than 20 Button Configurations ideas

Here are >20 interesting uses for the Stream Deck with Home Assistant:

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
<summary>7. 🔒 Lock/unlock a door:</summary>

```yaml
- entity_id: lock.front_door
  service: lock.toggle
  icon_mdi: "{{ 'door-open' if is_state('lock.front_door', 'unlocked') else 'door-closed' }}"
  text: |
    Front Door
    {{ 'Unlocked' if is_state('lock.front_door', 'unlocked') else 'Locked' }}
  text_size: 10
```

</details>

<details>
<summary>8. ⚠️ Arm/disarm an alarm system:</summary>

```yaml
- entity_id: alarm_control_panel.home_alarm
  service: "{{ 'alarm_control_panel.alarm_disarm' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'alarm_control_panel.alarm_arm_away' }}"
  icon_mdi: "{{ 'shield-check' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'shield-off' }}"
  text: |
    {{ 'Disarm' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'Arm' }}
    Alarm
```

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
<summary>25. 🌙 Enable/disable a nightlight:</summary>

```yaml
- entity_id: light.nightlight
  service: light.toggle
  icon_mdi: "{{ 'lightbulb-on' if is_state('light.nightlight', 'on') else 'lightbulb-off' }}"
  text: "{{ 'Disable' if is_state('light.nightlight', 'on') else 'Enable' }} Nightlight"
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


<!-- OUTPUT:END -->
