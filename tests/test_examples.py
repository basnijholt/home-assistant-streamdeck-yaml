"""Test examples in the README."""

import textwrap
from typing import Any

import pytest
from jinja2 import Environment

from home_assistant_streamdeck_yaml import Button

activate_a_scene = {
    "description": "🎭 Activate a scene",
    "yaml": textwrap.dedent(
        """
        - service: scene.turn_on
          service_data:
            entity_id: scene.movie_night
          icon_mdi: movie
          text: Movie Night
        """,
    ),
    "state": {"scene.movie_night": {"state": "on"}},
    "result": Button(
        service="scene.turn_on",
        service_data={"entity_id": "scene.movie_night"},
        icon_mdi="movie",
        text="Movie Night",
    ),
}

toggle_a_cover = {
    "description": "🚪 Toggle a cover (e.g., blinds or garage door)",
    "yaml": textwrap.dedent(
        """
        - entity_id: cover.garage_door
          service: cover.toggle
          icon_mdi: "{{ 'garage-open' if is_state('cover.garage_door', 'open') else 'garage-lock' }}"
          text: "{{ 'Open' if is_state('cover.garage_door', 'open') else 'Close' }}"
        """,
    ),
    "state": {"cover.garage_door": {"state": "open"}},
    "result": Button(
        entity_id="cover.garage_door",
        service="cover.toggle",
        icon_mdi="garage-open",
        text="Open",
    ),
}

start_or_stop_vacuum = {
    "description": "🤖 Start or stop the vacuum robot",
    "yaml": textwrap.dedent(
        """
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
        """,
    ),
    "state": {"vacuum.cleaning_robot": {"state": "docked"}},
    "result": Button(
        entity_id="vacuum.cleaning_robot",
        service="vacuum.start",
        icon_mdi="robot-vacuum",
        text="Start",
    ),
}

mute_unmute_media_player = {
    "description": "🔇 Mute/unmute a media player",
    "yaml": textwrap.dedent(
        """
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
        """,
    ),
    "state": {
        "media_player.living_room_speaker": {"attributes": {"is_volume_muted": True}},
    },
    "result": Button(
        entity_id="media_player.living_room_speaker",
        service="media_player.volume_mute",
        service_data={
            "entity_id": "media_player.living_room_speaker",
            "is_volume_muted": "false",
        },
        icon_mdi="volume-off",
        text="Unmute",
    ),
}

control_brightness_of_light = {
    "description": "🌟 Control the brightness of a light (+10% on press)",
    "yaml": textwrap.dedent(
        """
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
        """,
    ),
    "state": {"light.living_room_lights": {"attributes": {"brightness": 100}}},
    "result": Button(
        entity_id="light.living_room_lights",
        service="light.turn_on",
        service_data={
            "entity_id": "light.living_room_lights",
            "brightness": f"{int((100 + 25.5) % 255)}",
        },
        text="39.0%",
    ),
}

toggle_fan = {
    "description": "💨 Toggle a fan",
    "yaml": textwrap.dedent(
        """
        - entity_id: fan.bedroom_fan
          service: fan.toggle
          icon_mdi: "{{ 'fan' if is_state('fan.bedroom_fan', 'on') else 'fan-off' }}"
          text: |
            Bedroom
            {{ 'On' if is_state('fan.bedroom_fan', 'on') else 'Off' }}
        """,
    ),
    "state": {"fan.bedroom_fan": {"state": "on"}},
    "result": Button(
        entity_id="fan.bedroom_fan",
        service="fan.toggle",
        icon_mdi="fan",
        text="Bedroom\nOn",
    ),
}

lock_unlock_door = {
    "description": "🔒 Lock/unlock a door",
    "yaml": textwrap.dedent(
        """
        - entity_id: lock.front_door
          service: lock.toggle
          icon_mdi: "{{ 'door-open' if is_state('lock.front_door', 'unlocked') else 'door-closed' }}"
          text: |
            Front Door
            {{ 'Unlocked' if is_state('lock.front_door', 'unlocked') else 'Locked' }}
          text_size: 10
        """,
    ),
    "state": {"lock.front_door": {"state": "unlocked"}},
    "result": Button(
        entity_id="lock.front_door",
        service="lock.toggle",
        icon_mdi="door-open",
        text="Front Door\nUnlocked",
        text_size=10,
    ),
}

arm_disarm_alarm_system = {
    "description": "⚠️ Arm/disarm an alarm system",
    "yaml": textwrap.dedent(
        """
        - entity_id: alarm_control_panel.home_alarm
          service: "{{ 'alarm_control_panel.alarm_disarm' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'alarm_control_panel.alarm_arm_away' }}"
          icon_mdi: "{{ 'shield-check' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'shield-off' }}"
          text: |
            {{ 'Disarm' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'Arm' }}
            Alarm
        """,
    ),
    "state": {"alarm_control_panel.home_alarm": {"state": "armed_away"}},
    "result": Button(
        entity_id="alarm_control_panel.home_alarm",
        service="alarm_control_panel.alarm_disarm",
        icon_mdi="shield-check",
        text="Disarm\nAlarm",
    ),
}

set_alarm_time_for_next_day = {
    "description": "⏰ Set an alarm time for the next day",
    "yaml": textwrap.dedent(
        """
        - service: input_datetime.set_datetime
          service_data:
            entity_id: input_datetime.alarm_time
            time: "{{ '07:00:00' if states('input_datetime.alarm_time') != '07:00:00' else '08:00:00' }}"
          icon_mdi: "alarm"
          text: |
            Set Alarm
            {{ '7AM' if states('input_datetime.alarm_time') != '07:00:00' else '8AM' }}
        """,
    ),
    "state": {"input_datetime.alarm_time": {"state": "07:00:00"}},
    "result": Button(
        service="input_datetime.set_datetime",
        service_data={
            "entity_id": "input_datetime.alarm_time",
            "time": "08:00:00",
        },
        icon_mdi="alarm",
        text="Set Alarm\n8AM",
    ),
}


media_play_pause = {
    "description": "🎵 Control a media player (play/pause)",
    "yaml": textwrap.dedent(
        """
        - entity_id: media_player.living_room_speaker
          service: media_player.media_play_pause
          icon_mdi: "{{ 'pause' if is_state('media_player.living_room_speaker', 'playing') else 'play' }}"
          text: "{{ 'Pause' if is_state('media_player.living_room_speaker', 'playing') else 'Play' }}"
        """,
    ),
    "state": {"media_player.living_room_speaker": {"state": "playing"}},
    "result": Button(
        entity_id="media_player.living_room_speaker",
        service="media_player.media_play_pause",
        icon_mdi="pause",
        text="Pause",
    ),
}

media_next_track = {
    "description": "🎵 Control a media player (skip tracks)",
    "yaml": textwrap.dedent(
        """
        - entity_id: media_player.living_room_speaker
          service: media_player.media_next_track
          icon_mdi: skip-next
          text: Next Track
        """,
    ),
    "state": {},
    "result": Button(
        entity_id="media_player.living_room_speaker",
        service="media_player.media_next_track",
        icon_mdi="skip-next",
        text="Next Track",
    ),
}

set_blue_light = {
    "description": "🌈 Set a specific color for a light",
    "yaml": textwrap.dedent(
        """
        - entity_id: light.living_room_light
          service: light.toggle
          service_data:
            color_name: blue
          icon_mdi: "{{ 'lightbulb-on' if is_state('light.living_room_light', 'on') else 'lightbulb-off' }}"
          text: Blue Light
        """,
    ),
    "state": {"light.living_room_light": {"state": "on"}},
    "result": Button(
        entity_id="light.living_room_light",
        service="light.toggle",
        service_data={"color_name": "blue"},
        icon_mdi="lightbulb-on",
        text="Blue Light",
    ),
}


set_temperature = {
    "description": "🌡️ Adjust the thermostat between two specific temperatures",
    "yaml": textwrap.dedent(
        """
        - entity_id: climate.living_room
          service: climate.set_temperature
          service_data:
            temperature: "{{ 17 if state_attr('climate.living_room', 'temperature') >= 22 else 22 }}"
          icon_mdi: thermostat
          text: |
            Set
            {{ '17°C' if state_attr('climate.living_room', 'temperature') >= 22 else '22°C' }}
            ({{ state_attr('climate.living_room', 'current_temperature') }}°C now)
        """,
    ),
    "state": {
        "climate.living_room": {
            "attributes": {"temperature": 22, "current_temperature": 21},
        },
    },
    "result": Button(
        entity_id="climate.living_room",
        service="climate.set_temperature",
        service_data={"temperature": "17"},
        icon_mdi="thermostat",
        text="Set\n17°C\n(21°C now)",
    ),
}

send_mobile_notification = {
    "description": "📲 Trigger a script to send a notification to your mobile device",
    "yaml": textwrap.dedent(
        """
        - service: script.send_mobile_notification
          icon_mdi: bell
          text: Send Notification
        """,
    ),
    "state": {},
    "result": Button(
        service="script.send_mobile_notification",
        icon_mdi="bell",
        text="Send Notification",
    ),
}

day_night_mode = {
    "description": "🌆 Toggle a day/night mode (using an input\\_boolean)",
    "yaml": textwrap.dedent(
        """
        - entity_id: input_boolean.day_night_mode
          service: input_boolean.toggle
          icon_mdi: "{{ 'weather-night' if is_state('input_boolean.day_night_mode', 'on') else 'weather-sunny' }}"
          text: |
            {{ 'Night' if is_state('input_boolean.day_night_mode', 'on') else 'Day' }}
            Mode
        """,
    ),
    "state": {"input_boolean.day_night_mode": {"state": "on"}},
    "result": Button(
        entity_id="input_boolean.day_night_mode",
        service="input_boolean.toggle",
        icon_mdi="weather-night",
        text="Night\nMode",
    ),
}

select_tv_source = {
    "description": "📺 Control a TV (e.g., turn on/off or change input source)",
    "yaml": textwrap.dedent(
        """
        - entity_id: media_player.living_room_tv
          service: media_player.select_source
          service_data:
            source: HDMI 1
          text: HDMI 1
        """,
    ),
    "state": {},
    "result": Button(
        entity_id="media_player.living_room_tv",
        service="media_player.select_source",
        service_data={"source": "HDMI 1"},
        text="HDMI 1",
    ),
}


control_group_lights = {
    "description": "🔦 Control a group of lights (e.g., turn on/off or change color)",
    "yaml": textwrap.dedent(
        """
        - entity_id: group.living_room_lights
          service: light.turn_on
          service_data:
            color_name: red
          icon_mdi: "{{ 'lightbulb-group-on' if is_state('group.living_room_lights', 'on') else 'lightbulb-group-off' }}"
          text: Red Group Lights
        """,
    ),
    "state": {"group.living_room_lights": {"state": "on"}},
    "result": Button(
        entity_id="group.living_room_lights",
        service="light.turn_on",
        service_data={"color_name": "red"},
        icon_mdi="lightbulb-group-on",
        text="Red Group Lights",
    ),
}

trigger_doorbell_announcement = {
    "description": "🔔 Trigger a script to announce the doorbell",
    "yaml": textwrap.dedent(
        """
        - service: script.trigger_doorbell_announcement
          text: Doorbell Announcement
        """,
    ),
    "state": {},
    "result": Button(
        service="script.trigger_doorbell_announcement",
        text="Doorbell Announcement",
    ),
}

sleep_timer = {
    "description": "⏰ Enable/disable a sleep timer (using an input\\_boolean)",
    "yaml": textwrap.dedent(
        """
        - entity_id: input_boolean.sleep_timer
          service: input_boolean.toggle
          icon_mdi: "{{ 'timer' if is_state('input_boolean.sleep_timer', 'on') else 'timer-off' }}"
          text: |
            {{ 'Cancel' if is_state('input_boolean.sleep_timer', 'on') else 'Set' }}
            Sleep Timer
        """,
    ),
    "state": {"input_boolean.sleep_timer": {"state": "on"}},
    "result": Button(
        entity_id="input_boolean.sleep_timer",
        service="input_boolean.toggle",
        icon_mdi="timer",
        text="Cancel\nSleep Timer",
    ),
}


weather_temperature = {
    "description": "🌡️ Display the current temperature",
    "yaml": (
        """
        - entity_id: sensor.weather_temperature
          text: '{{ states("sensor.weather_temperature") }}°C'
          text_size: 16
          icon_mdi: weather-cloudy
        """
    ),
    "state": {"sensor.weather_temperature": {"state": "15"}},
    "result": Button(
        entity_id="sensor.weather_temperature",
        text="15°C",
        text_size=16,
        icon_mdi="weather-cloudy",
    ),
}

toggle_wifi = {
    "description": "📶 Toggle Wi-Fi on/off (using a switch)",
    "yaml": (
        """
        - entity_id: switch.wifi_switch
          service: switch.toggle
          icon_mdi: "{{ 'wifi' if is_state('switch.wifi_switch', 'on') else 'wifi-off' }}"
          text: |
            {{ 'Disable' if is_state('switch.wifi_switch', 'on') else 'Enable' }}
            Wi-Fi
        """
    ),
    "state": {"switch.wifi_switch": {"state": "on"}},
    "result": Button(
        entity_id="switch.wifi_switch",
        service="switch.toggle",
        icon_mdi="wifi",
        text="Disable\nWi-Fi",
    ),
}


activate_voice_assistant = {
    "description": "🗣️ Activate voice assistant",
    "yaml": textwrap.dedent(
        """
        - service: script.activate_voice_assistant
          icon_mdi: microphone
          text: Voice Assistant
        """,
    ),
    "state": {},
    "result": Button(
        service="script.activate_voice_assistant",
        icon_mdi="microphone",
        text="Voice Assistant",
    ),
}


start_stop_air_purifier = {
    "description": "🌿 Start/stop air purifier",
    "yaml": textwrap.dedent(
        """
        - entity_id: switch.air_purifier
          service: switch.toggle
          icon_mdi: "{{ 'air-purifier' if is_state('switch.air_purifier', 'on') else 'air-purifier-off' }}"
          text: "{{ 'Stop' if is_state('switch.air_purifier', 'on') else 'Start' }} Air Purifier"
        """,
    ),
    "state": {"switch.air_purifier": {"state": "on"}},
    "result": Button(
        entity_id="switch.air_purifier",
        service="switch.toggle",
        icon_mdi="air-purifier",
        text="Stop Air Purifier",
    ),
}

start_stop_security_camera_recording = {
    "description": "📼 Start/stop a security camera recording",
    "yaml": textwrap.dedent(
        """
        - service: script.toggle_security_camera_recording
          icon_mdi: cctv
          text: Toggle Camera Recording
        """,
    ),
    "state": {},
    "result": Button(
        service="script.toggle_security_camera_recording",
        icon_mdi="cctv",
        text="Toggle Camera Recording",
    ),
}

enable_disable_nightlight = {
    "description": "🌙 Enable/disable a nightlight",
    "yaml": textwrap.dedent(
        """
        - entity_id: light.nightlight
          service: light.toggle
          icon_mdi: "{{ 'lightbulb-on' if is_state('light.nightlight', 'on') else 'lightbulb-off' }}"
          text: "{{ 'Disable' if is_state('light.nightlight', 'on') else 'Enable' }} Nightlight"
        """,
    ),
    "state": {"light.nightlight": {"state": "on"}},
    "result": Button(
        entity_id="light.nightlight",
        service="light.toggle",
        icon_mdi="lightbulb-on",
        text="Disable Nightlight",
    ),
}


BUTTONS = [
    activate_a_scene,
    toggle_a_cover,
    start_or_stop_vacuum,
    mute_unmute_media_player,
    control_brightness_of_light,
    toggle_fan,
    lock_unlock_door,
    arm_disarm_alarm_system,
    set_alarm_time_for_next_day,
    media_play_pause,
    media_next_track,
    set_blue_light,
    set_temperature,
    send_mobile_notification,
    day_night_mode,
    select_tv_source,
    control_group_lights,
    trigger_doorbell_announcement,
    sleep_timer,
    weather_temperature,
    toggle_wifi,
    activate_voice_assistant,
    start_stop_air_purifier,
    start_stop_security_camera_recording,
    enable_disable_nightlight,
]


@pytest.mark.parametrize("button_dct", BUTTONS)
def test_button(button_dct: dict[str, Any]) -> None:
    """Test all buttons."""
    button = Button.from_yaml(button_dct["yaml"])  # type: ignore[arg-type]
    button_template = button.rendered_template_button(button_dct["state"])  # type: ignore[arg-type]
    assert button_template == button_dct["result"], button_dct["description"]


def generate_readme_entry() -> None:
    """Generate the README entries."""
    template_string = textwrap.dedent(
        """
        {% for i, button in enumerate(buttons, 1) %}
        <details>
        <summary>{{ i }}. {{ button.description }}:</summary>

        ```yaml
        {{ button.yaml.strip() }}
        ```

        </details>

        {% endfor %}
        """,
    )
    env = Environment(autoescape=False)  # noqa: S701
    env.globals["enumerate"] = enumerate
    template = env.from_string(template_string)
    return template.render(buttons=BUTTONS)
