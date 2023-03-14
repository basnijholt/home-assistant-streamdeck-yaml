# Home Assistant on Stream Deck: configured via YAML (with templates) and running on Linux, MacOS, and Windows

This is a simple Python script that allows you to control your Home Assistant instance via a Stream Deck.

It is configured via a YAML file and runs on Linux, so you can use it on the same machine as Home Assistant or on a separate machine (a Raspberry Pi or any other machine).

More information coming soon.

See the [streamdeck-config.yaml](streamdeck-config.yaml) file for an example configuration (or my current configuration).

## Why?
Even though [github.com/cgiesche/streamdeck-homeassistant](https://github.com/cgiesche/streamdeck-homeassistant) exists, I wanted to have a solution that is more flexible and allows me to connect a Stream Deck to the same Linux machine where Home Assistant is running.
Unfortunately, the native Stream Deck software does not support Linux, so here we are using [github.com/abcminiuser/python-elgato-streamdeck](https://github.com/abcminiuser/python-elgato-streamdeck) to control the Stream Deck.

## Installation
Just run `pip install -r requirements.txt` to install the required dependencies.

## Usage
1. Create a `streamdeck-config.yaml` file in the same directory as the `home-assistant-streamdeck-yaml.py` file.
2. Run `python home-assistant-streamdeck-yaml.py -h` to see the available options.

Example:
```bash
python home-assistant-streamdeck-yaml.py --host "klasdhkjashdhaksdl.ui.nabu.casa" --token "SOME_TOKEN_FROM_YOUR_PROFILE"
```

Or edit the `.env.example` file and rename it to `.env`. Then you can run the script without any arguments.
