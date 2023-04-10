"""Test examples in the README."""

import textwrap
import warnings
from typing import Any

import pytest
from jinja2 import Environment

from home_assistant_streamdeck_yaml import Button, IconWarning

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
    "state": [{"scene.movie_night": {"state": "on"}}],
    "result": [
        Button(
            service="scene.turn_on",
            service_data={"entity_id": "scene.movie_night"},
            icon_mdi="movie",
            text="Movie Night",
        ),
    ],
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
    "state": [
        {"cover.garage_door": {"state": "open"}},
        {"cover.garage_door": {"state": "closed"}},
    ],
    "result": [
        Button(
            entity_id="cover.garage_door",
            service="cover.toggle",
            icon_mdi="garage-open",
            text="Open",
        ),
        Button(
            entity_id="cover.garage_door",
            service="cover.toggle",
            icon_mdi="garage-lock",
            text="Close",
        ),
    ],
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
    "state": [
        {"vacuum.cleaning_robot": {"state": "docked"}},
        {"vacuum.cleaning_robot": {"state": "cleaning"}},
    ],
    "result": [
        Button(
            entity_id="vacuum.cleaning_robot",
            service="vacuum.start",
            icon_mdi="robot-vacuum",
            text="Start",
        ),
        Button(
            entity_id="vacuum.cleaning_robot",
            service="vacuum.return_to_base",
            icon_mdi="robot-vacuum",
            text="Stop",
        ),
    ],
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
    "state": [
        {
            "media_player.living_room_speaker": {
                "state": "playing",
                "attributes": {"is_volume_muted": True},
            },
        },
        {
            "media_player.living_room_speaker": {
                "state": "on",
                "attributes": {"is_volume_muted": False},
            },
        },
    ],
    "result": [
        Button(
            entity_id="media_player.living_room_speaker",
            service="media_player.volume_mute",
            service_data={
                "entity_id": "media_player.living_room_speaker",
                "is_volume_muted": "false",
            },
            icon_mdi="volume-off",
            text="Unmute",
        ),
        Button(
            entity_id="media_player.living_room_speaker",
            service="media_player.volume_mute",
            service_data={
                "entity_id": "media_player.living_room_speaker",
                "is_volume_muted": "true",
            },
            icon_mdi="volume-high",
            text="Mute",
        ),
    ],
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
    "state": [
        {
            "light.living_room_lights": {
                "state": "on",
                "attributes": {"brightness": 100},
            },
        },
        {
            "light.living_room_lights": {
                "state": "on",
                "attributes": {"brightness": 200},
            },
        },
    ],
    "result": [
        Button(
            entity_id="light.living_room_lights",
            service="light.turn_on",
            service_data={
                "entity_id": "light.living_room_lights",
                "brightness": f"{int((100 + 25.5) % 255)}",
            },
            text="39.0%",
        ),
        Button(
            entity_id="light.living_room_lights",
            service="light.turn_on",
            service_data={
                "entity_id": "light.living_room_lights",
                "brightness": f"{int((200 + 25.5) % 255)}",
            },
            text="78.0%",
        ),
    ],
}

toggle_fan = {
    "description": "🌀 Toggle a fan",
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
    "state": [
        {"fan.bedroom_fan": {"state": "on"}},
        {"fan.bedroom_fan": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="fan.bedroom_fan",
            service="fan.toggle",
            icon_mdi="fan",
            text="Bedroom\nOn",
        ),
        Button(
            entity_id="fan.bedroom_fan",
            service="fan.toggle",
            icon_mdi="fan-off",
            text="Bedroom\nOff",
        ),
    ],
}

lock_unlock_door = {
    "description": "🔒 Lock/unlock a door after 30 seconds",
    "yaml": textwrap.dedent(
        """
        - entity_id: lock.front_door
          service: lock.toggle
          delay: "{{ 30 if is_state('lock.front_door', 'unlocked') else 0 }}"
          icon_mdi: "{{ 'door-open' if is_state('lock.front_door', 'unlocked') else 'door-closed' }}"
          text: |
            Front Door
            {{ 'Unlocked' if is_state('lock.front_door', 'unlocked') else 'Locked' }}
          text_size: 10
          text_color: "{{ 'green' if is_state('lock.front_door', 'unlocked') else 'red' }}"
        """,
    ),
    "state": [
        {"lock.front_door": {"state": "unlocked"}},
        {"lock.front_door": {"state": "locked"}},
    ],
    "result": [
        Button(
            entity_id="lock.front_door",
            service="lock.toggle",
            icon_mdi="door-open",
            text="Front Door\nUnlocked",
            text_size=10,
            delay=30.0,
            text_color="green",
        ),
        Button(
            entity_id="lock.front_door",
            service="lock.toggle",
            icon_mdi="door-closed",
            text="Front Door\nLocked",
            text_size=10,
            delay=0.0,
            text_color="red",
        ),
    ],
}

arm_disarm_alarm_system = {
    "description": "⚠️ Arm/disarm an alarm system after 30 seconds",
    "extra": "Arm the alarm system in 30 seconds if it's disarmed, disarm it immediately if it's armed.",
    "yaml": textwrap.dedent(
        """
        - entity_id: alarm_control_panel.home_alarm
          delay: "{{ 0 if is_state('alarm_control_panel.home_alarm', 'armed_away') else 30 }}"
          service: "{{ 'alarm_control_panel.alarm_disarm' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'alarm_control_panel.alarm_arm_away' }}"
          icon_mdi: "{{ 'shield-check' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'shield-off' }}"
          text: |
            {{ 'Disarm' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'Arm' }}
            Alarm
          text_color: "{{ 'red' if is_state('alarm_control_panel.home_alarm', 'armed_away') else 'green' }}"
        """,
    ),
    "state": [
        {"alarm_control_panel.home_alarm": {"state": "armed_away"}},
        {"alarm_control_panel.home_alarm": {"state": "disarmed"}},
    ],
    "result": [
        Button(
            entity_id="alarm_control_panel.home_alarm",
            service="alarm_control_panel.alarm_disarm",
            icon_mdi="shield-check",
            text="Disarm\nAlarm",
            text_color="red",
            delay=0.0,
        ),
        Button(
            entity_id="alarm_control_panel.home_alarm",
            service="alarm_control_panel.alarm_arm_away",
            icon_mdi="shield-off",
            text="Arm\nAlarm",
            text_color="green",
            delay=30.0,
        ),
    ],
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
    "state": [
        {"input_datetime.alarm_time": {"state": "07:00:00"}},
        {"input_datetime.alarm_time": {"state": "08:00:00"}},
    ],
    "result": [
        Button(
            service="input_datetime.set_datetime",
            service_data={
                "entity_id": "input_datetime.alarm_time",
                "time": "08:00:00",
            },
            icon_mdi="alarm",
            text="Set Alarm\n8AM",
        ),
        Button(
            service="input_datetime.set_datetime",
            service_data={
                "entity_id": "input_datetime.alarm_time",
                "time": "07:00:00",
            },
            icon_mdi="alarm",
            text="Set Alarm\n7AM",
        ),
    ],
}

media_play_pause = {
    "description": "⏯️ Control a media player (play/pause)",
    "yaml": textwrap.dedent(
        """
        - entity_id: media_player.living_room_speaker
          service: media_player.media_play_pause
          icon_mdi: "{{ 'pause' if is_state('media_player.living_room_speaker', 'playing') else 'play' }}"
          text: "{{ 'Pause' if is_state('media_player.living_room_speaker', 'playing') else 'Play' }}"
        """,
    ),
    "state": [
        {"media_player.living_room_speaker": {"state": "playing"}},
        {"media_player.living_room_speaker": {"state": "paused"}},
    ],
    "result": [
        Button(
            entity_id="media_player.living_room_speaker",
            service="media_player.media_play_pause",
            icon_mdi="pause",
            text="Pause",
        ),
        Button(
            entity_id="media_player.living_room_speaker",
            service="media_player.media_play_pause",
            icon_mdi="play",
            text="Play",
        ),
    ],
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
    "state": [{}],
    "result": [
        Button(
            entity_id="media_player.living_room_speaker",
            service="media_player.media_next_track",
            icon_mdi="skip-next",
            text="Next Track",
        ),
    ],
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
    "state": [
        {"light.living_room_light": {"state": "on"}},
        {"light.living_room_light": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="light.living_room_light",
            service="light.toggle",
            service_data={"color_name": "blue"},
            icon_mdi="lightbulb-on",
            text="Blue Light",
        ),
        Button(
            entity_id="light.living_room_light",
            service="light.toggle",
            service_data={"color_name": "blue"},
            icon_mdi="lightbulb-off",
            text="Blue Light",
        ),
    ],
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
    "state": [
        {
            "climate.living_room": {
                "state": "heat",
                "attributes": {"temperature": 22, "current_temperature": 21},
            },
        },
        {
            "climate.living_room": {
                "state": "cool",
                "attributes": {"temperature": 17, "current_temperature": 21},
            },
        },
    ],
    "result": [
        Button(
            entity_id="climate.living_room",
            service="climate.set_temperature",
            service_data={"temperature": "17"},
            icon_mdi="thermostat",
            text="Set\n17°C\n(21°C now)",
        ),
        Button(
            entity_id="climate.living_room",
            service="climate.set_temperature",
            service_data={"temperature": "22"},
            icon_mdi="thermostat",
            text="Set\n22°C\n(21°C now)",
        ),
    ],
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
    "state": [{}],
    "result": [
        Button(
            service="script.send_mobile_notification",
            icon_mdi="bell",
            text="Send Notification",
        ),
    ],
    "extra": textwrap.dedent(
        """
        Which uses this script (which needs to be defined in Home Assistant):

        ```yaml
        send_mobile_notification:
          alias: "Send Mobile Notification"
          sequence:
            - service: notify.mobile_app_<your_device_name>
              data:
                message: "Your custom notification message."
        ```
        """,
    ),
}

day_night_mode = {
    "description": "🌆 Toggle a day/night mode (using an input_boolean)",
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
    "state": [
        {"input_boolean.day_night_mode": {"state": "on"}},
        {"input_boolean.day_night_mode": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="input_boolean.day_night_mode",
            service="input_boolean.toggle",
            icon_mdi="weather-night",
            text="Night\nMode",
        ),
        Button(
            entity_id="input_boolean.day_night_mode",
            service="input_boolean.toggle",
            icon_mdi="weather-sunny",
            text="Day\nMode",
        ),
    ],
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
    "state": [{}],
    "result": [
        Button(
            entity_id="media_player.living_room_tv",
            service="media_player.select_source",
            service_data={"source": "HDMI 1"},
            text="HDMI 1",
        ),
    ],
}

control_group_lights = {
    "description": "🔦 Control a group of lights (e.g., turn on/off or change color)",
    "yaml": textwrap.dedent(
        """
        - entity_id: group.living_room_lights
          service: light.turn_on
          service_data:
            color_name: red
          icon_mdi: "{{ 'lightbulb-group' if is_state('group.living_room_lights', 'on') else 'lightbulb-group-off' }}"
          text: Red Group Lights
        """,
    ),
    "state": [
        {"group.living_room_lights": {"state": "on"}},
        {"group.living_room_lights": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="group.living_room_lights",
            service="light.turn_on",
            service_data={"color_name": "red"},
            icon_mdi="lightbulb-group",
            text="Red Group Lights",
        ),
        Button(
            entity_id="group.living_room_lights",
            service="light.turn_on",
            service_data={"color_name": "red"},
            icon_mdi="lightbulb-group-off",
            text="Red Group Lights",
        ),
    ],
}

trigger_doorbell_announcement = {
    "description": "🔔 Trigger a script to announce the doorbell",
    "yaml": textwrap.dedent(
        """
        - service: script.trigger_doorbell_announcement
          text: Doorbell Announcement
        """,
    ),
    "state": [{}],
    "result": [
        Button(
            service="script.trigger_doorbell_announcement",
            text="Doorbell Announcement",
        ),
    ],
    "extra": textwrap.dedent(
        """
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
        """,
    ),
}

sleep_timer = {
    "description": "⏰ Enable/disable a sleep timer (using an input_boolean)",
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
    "state": [
        {"input_boolean.sleep_timer": {"state": "on"}},
        {"input_boolean.sleep_timer": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="input_boolean.sleep_timer",
            service="input_boolean.toggle",
            icon_mdi="timer",
            text="Cancel\nSleep Timer",
        ),
        Button(
            entity_id="input_boolean.sleep_timer",
            service="input_boolean.toggle",
            icon_mdi="timer-off",
            text="Set\nSleep Timer",
        ),
    ],
}

weather_temperature = {
    "description": "🌡️ Display current temperature",
    "yaml": textwrap.dedent(
        """
        - entity_id: sensor.weather_temperature
          text: '{{ states("sensor.weather_temperature") }}°C'
          text_size: 16
          icon_mdi: weather-cloudy
        """,
    ),
    "state": [
        {"sensor.weather_temperature": {"state": 20}},
        {"sensor.weather_temperature": {"state": 25}},
    ],
    "result": [
        Button(
            entity_id="sensor.weather_temperature",
            icon_mdi="weather-cloudy",
            text="20°C",
            text_size=16,
        ),
        Button(
            entity_id="sensor.weather_temperature",
            icon_mdi="weather-cloudy",
            text="25°C",
            text_size=16,
        ),
    ],
}

scene_morning = {
    "description": "🌅 Activate a morning scene",
    "yaml": textwrap.dedent(
        """
        - entity_id: scene.morning
          service: scene.turn_on
          icon_mdi: "weather-sunset-up"
          text: Morning Scene
        """,
    ),
    "state": [
        {"scene.morning": {"state": "on"}},
        {"scene.morning": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="scene.morning",
            service="scene.turn_on",
            icon_mdi="weather-sunset-up",
            text="Morning Scene",
        ),
        Button(
            entity_id="scene.morning",
            service="scene.turn_on",
            icon_mdi="weather-sunset-up",
            text="Morning Scene",
        ),
    ],
}

scene_night = {
    "description": "🌃 Activate a night scene",
    "yaml": textwrap.dedent(
        """
        - entity_id: scene.night
          service: scene.turn_on
          icon_mdi: "weather-night"
          text: Night Scene
        """,
    ),
    "state": [
        {"scene.night": {"state": "on"}},
        {"scene.night": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="scene.night",
            service="scene.turn_on",
            icon_mdi="weather-night",
            text="Night Scene",
        ),
        Button(
            entity_id="scene.night",
            service="scene.turn_on",
            icon_mdi="weather-night",
            text="Night Scene",
        ),
    ],
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
    "state": [
        {"switch.wifi_switch": {"state": "on"}},
        {"switch.wifi_switch": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="switch.wifi_switch",
            service="switch.toggle",
            icon_mdi="wifi",
            text="Disable\nWi-Fi",
        ),
        Button(
            entity_id="switch.wifi_switch",
            service="switch.toggle",
            icon_mdi="wifi-off",
            text="Enable\nWi-Fi",
        ),
    ],
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
    "state": [[{}]],
    "result": [
        Button(
            service="script.activate_voice_assistant",
            icon_mdi="microphone",
            text="Voice Assistant",
        ),
    ],
    "extra": textwrap.dedent(
        """
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
        """,
    ),
}

start_stop_air_purifier = {
    "description": "🌿 Start/Stop air purifier",
    "yaml": textwrap.dedent(
        """
        - entity_id: switch.air_purifier
          service: switch.toggle
          icon_mdi: "{{ 'air-purifier' if is_state('switch.air_purifier', 'on') else 'air-purifier-off' }}"
          text: |
            {{ 'Stop' if is_state('switch.air_purifier', 'on') else 'Start' }}
            Air Purifier
        """,
    ),
    "state": [
        {"switch.air_purifier": {"state": "on"}},
        {"switch.air_purifier": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="switch.air_purifier",
            service="switch.toggle",
            icon_mdi="air-purifier",
            text="Stop\nAir Purifier",
        ),
        Button(
            entity_id="switch.air_purifier",
            service="switch.toggle",
            icon_mdi="air-purifier-off",
            text="Start\nAir Purifier",
        ),
    ],
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
    "state": [{}],
    "result": [
        Button(
            service="script.toggle_security_camera_recording",
            icon_mdi="cctv",
            text="Toggle Camera Recording",
        ),
    ],
    "extra": textwrap.dedent(
        """
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
        """,
    ),
}

enable_disable_nightlight = {
    "description": "🌙 Enable/disable a nightlight after 30 min",
    "yaml": textwrap.dedent(
        """
        - entity_id: light.nightlight
          service: light.toggle
          delay: 1800
          icon_mdi: "{{ 'lightbulb-on' if is_state('light.nightlight', 'on') else 'lightbulb-off' }}"
          text: "{{ 'Disable' if is_state('light.nightlight', 'on') else 'Enable' }} Nightlight"
          text_color: "{{ 'red' if is_state('light.nightlight', 'on') else 'green' }}"
        """,
    ),
    "state": [
        {"light.nightlight": {"state": "on"}},
        {"light.nightlight": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="light.nightlight",
            service="light.toggle",
            icon_mdi="lightbulb-on",
            text="Disable Nightlight",
            text_color="red",
            delay=1800.0,
        ),
        Button(
            entity_id="light.nightlight",
            service="light.toggle",
            icon_mdi="lightbulb-off",
            text="Enable Nightlight",
            text_color="green",
            delay=1800.0,
        ),
    ],
}

control_smart_fireplace = {
    "description": "🔥 Control a smart fireplace",
    "yaml": textwrap.dedent(
        """
        - entity_id: switch.smart_fireplace
          service: switch.toggle
          icon_mdi: "{{ 'fire' if is_state('switch.smart_fireplace', 'on') else 'fire-off' }}"
          text: |
            {{ 'Turn Off' if is_state('switch.smart_fireplace', 'on') else 'Turn On' }}
            Fireplace
        """,
    ),
    "state": [
        {"switch.smart_fireplace": {"state": "on"}},
        {"switch.smart_fireplace": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="switch.smart_fireplace",
            service="switch.toggle",
            icon_mdi="fire",
            text="Turn Off\nFireplace",
        ),
        Button(
            entity_id="switch.smart_fireplace",
            service="switch.toggle",
            icon_mdi="fire-off",
            text="Turn On\nFireplace",
        ),
    ],
}

toggle_smart_plug = {
    "description": "🔌 Toggle a smart plug",
    "yaml": textwrap.dedent(
        """
        - entity_id: switch.smart_plug
          service: switch.toggle
          icon_mdi: "{{ 'power-plug' if is_state('switch.smart_plug', 'on') else 'power-plug-off' }}"
          text: |
            {{ 'Turn Off' if is_state('switch.smart_plug', 'on') else 'Turn On' }}
            Smart Plug
        """,
    ),
    "state": [
        {"switch.smart_plug": {"state": "on"}},
        {"switch.smart_plug": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="switch.smart_plug",
            service="switch.toggle",
            icon_mdi="power-plug",
            text="Turn Off\nSmart Plug",
        ),
        Button(
            entity_id="switch.smart_plug",
            service="switch.toggle",
            icon_mdi="power-plug-off",
            text="Turn On\nSmart Plug",
        ),
    ],
}

irrigation_toggle = {
    "description": "💦 Toggle irrigation system",
    "yaml": textwrap.dedent(
        """
        - entity_id: switch.irrigation_system
          service: switch.toggle
          icon_mdi: "{{ 'water' if is_state('switch.irrigation_system', 'on') else 'water-off' }}"
          text: |
            {{ 'Turn Off' if is_state('switch.irrigation_system', 'on') else 'Turn On' }}
            Irrigation
        """,
    ),
    "state": [
        {"switch.irrigation_system": {"state": "on"}},
        {"switch.irrigation_system": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="switch.irrigation_system",
            service="switch.toggle",
            icon_mdi="water",
            text="Turn Off\nIrrigation",
        ),
        Button(
            entity_id="switch.irrigation_system",
            service="switch.toggle",
            icon_mdi="water-off",
            text="Turn On\nIrrigation",
        ),
    ],
}


change_cover_position = {
    "description": "🌤️ Change the position of a cover (e.g., blinds or curtains)",
    "yaml": textwrap.dedent(
        """
        - entity_id: cover.living_room_blinds
          service: cover.set_cover_position
          service_data:
            position: "{{ 0 if state_attr('cover.living_room_blinds', 'position') >= 50 else 100 }}"
          icon_mdi: window-shutter
          text: |
            {{ 'Close' if state_attr('cover.living_room_blinds', 'position') >= 50 else 'Open' }}
            Blinds
        """,
    ),
    "state": [
        {
            "cover.living_room_blinds": {
                "state": "closed",
                "attributes": {"position": 0},
            },
        },
        {
            "cover.living_room_blinds": {
                "state": "open",
                "attributes": {"position": 100},
            },
        },
    ],
    "result": [
        Button(
            entity_id="cover.living_room_blinds",
            service="cover.set_cover_position",
            service_data={"position": "100"},
            icon_mdi="window-shutter",
            text="Open\nBlinds",
        ),
        Button(
            entity_id="cover.living_room_blinds",
            service="cover.set_cover_position",
            service_data={"position": "0"},
            icon_mdi="window-shutter",
            text="Close\nBlinds",
        ),
    ],
}

control_media_player_tv = {
    "description": "📺 Toggle a media player (e.g., TV) and show different images",
    "yaml": textwrap.dedent(
        """
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
        """,
    ),
    "state": [
        {"media_player.tv": {"state": "on"}},
        {"media_player.tv": {"state": "off"}},
    ],
    "result": [
        Button(
            entity_id="media_player.tv",
            service="media_player.toggle",
            icon="url:https://raw.githubusercontent.com/basnijholt/home-assistant-streamdeck-yaml/main/assets/fireplace.png",
            text="Turn Off",
        ),
        Button(
            entity_id="media_player.tv",
            service="media_player.toggle",
            icon="url:https://raw.githubusercontent.com/basnijholt/home-assistant-streamdeck-yaml/main/assets/hogwarts.png",
            text="Turn On",
        ),
    ],
}

start_timer = {
    "description": "⏰ Turn off all lights in 60s",
    "yaml": textwrap.dedent(
        """
        - entity_id: light.all_lights
          service: light.turn_off
          text: |
            Turn off
            in 60s
          delay: 60
        """,
    ),
    "state": [{}],
    "result": [
        Button(
            entity_id="light.all_lights",
            service="light.turn_off",
            text="Turn off\nin 60s\n",
            delay=60.0,
        ),
    ],
}


outside_temperature_display = {
    "description": "🌡️ Display outside temperature with a ring indicator",
    "extra": "This sets 0% to -10°C and 100% to 40°C.",
    "yaml": textwrap.dedent(
        """
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
        """,
    ),
    "state": [
        {
            "sensor.temperature_sensor_outside_temperature": {
                "state": "20",
            },
        },
        {
            "sensor.temperature_sensor_outside_temperature": {
                "state": "10",
            },
        },
    ],
    "result": [
        Button(
            entity_id="sensor.temperature_sensor_outside_temperature",
            icon="ring:60.0",
            text="Outside\n20°C",
        ),
        Button(
            entity_id="sensor.temperature_sensor_outside_temperature",
            icon="ring:40.0",
            text="Outside\n10°C",
        ),
    ],
}

reload_configuration_yaml = {
    "description": "🔄 Reload the `configuration.yaml` file",
    "extra": "When pressed, the `configuration.yaml` is reloaded.",
    "yaml": textwrap.dedent(
        """
        - special_type: reload
        """,
    ),
    "state": [{}],
    "result": [Button(special_type="reload")],
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
    control_smart_fireplace,
    toggle_smart_plug,
    irrigation_toggle,
    change_cover_position,
    control_media_player_tv,
    start_timer,
    outside_temperature_display,
    reload_configuration_yaml,
]


@pytest.mark.parametrize("button_dct", BUTTONS)
def test_button(button_dct: dict[str, Any]) -> None:
    """Test all buttons."""
    button = Button.from_yaml(button_dct["yaml"])  # type: ignore[arg-type]
    for i, (state, result) in enumerate(
        zip(button_dct["state"], button_dct["result"], strict=True),
    ):
        # Test rendering the icon
        with warnings.catch_warnings():
            warnings.simplefilter("error", IconWarning)
            icon = button.render_icon(state)
        assert icon is not None
        button_template = button.rendered_template_button(state)  # type: ignore[arg-type]
        actual = button_template.dict()
        expected = result.dict()
        for key, expected_value in expected.items():
            actual_value = actual[key]
            assert (
                actual_value == expected_value
            ), f'{i=}, {button_dct["description"]}, {key=}, {actual_value=}, {expected_value=}'

        assert button_template == result, button_dct["description"]


def generate_readme_entry() -> str:
    """Generate the README entries."""
    template_string = textwrap.dedent(
        """
        {% for i, button in enumerate(buttons, 1) %}
        <details>
        <summary>{{ i }}. {{ button.description }}:</summary>

        ```yaml
        {{ button.yaml.strip() }}
        ```
        {% if button.get("extra") %}
        {{ button.extra }}
        {% endif %}
        </details>
        {% endfor %}
        """,
    )
    env = Environment(autoescape=False)  # noqa: S701
    env.globals["enumerate"] = enumerate
    template = env.from_string(template_string)
    return template.render(buttons=BUTTONS)


def test_generate_readme_entry() -> None:
    """Test the README entry generation."""
    readme_entry = generate_readme_entry()
    assert readme_entry is not None
