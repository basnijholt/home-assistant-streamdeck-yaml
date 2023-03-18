<img src="https://user-images.githubusercontent.com/6897215/225175629-28f80bfb-3b0a-44ac-8b52-b719953958d7.png" align="right" style="width: 300px;" />

# Home Assistant on Stream Deck: configured via YAML (with templates) and running on Linux, MacOS, and Windows


This is a simple Python script that allows you to control your Home Assistant instance via a Stream Deck.

It is configured via a YAML file and runs on Linux, so you can use it on the same machine as Home Assistant or on a separate machine (a Raspberry Pi or any other machine).

More information coming soon.

See the [configuration.yaml](configuration.yaml) file for an example configuration (or my current configuration).

## Why?
Even though [github.com/cgiesche/streamdeck-homeassistant](https://github.com/cgiesche/streamdeck-homeassistant) exists, I wanted to have a solution that is more flexible and allows me to connect a Stream Deck to the same Linux machine where Home Assistant is running.
Unfortunately, the native Stream Deck software does not support Linux, so here we are using [github.com/abcminiuser/python-elgato-streamdeck](https://github.com/abcminiuser/python-elgato-streamdeck) to control the Stream Deck.

## Installation
Just run `pip install -e .` in the repo folder to install the required dependencies.

## Usage

1. Create a `configuration.yaml` file in the same directory as the `home-assistant-streamdeck-yaml.py` file.

### (Option 1) With environment variables

2. Edit the `.env.example` file and rename it to `.env`. Then you can run the script without any arguments. The script will automatically load the environment variables from the `.env` file.

```bash
python home-assistant-streamdeck-yaml.py
```

### (Option 2) With commandline arguments

2. Run `python home-assistant-streamdeck-yaml.py -h` to see the available options.

Example invocation:
```bash
python home-assistant-streamdeck-yaml.py --host "klasdhkjashdhaksdl.ui.nabu.casa" --token "SOME_TOKEN_FROM_YOUR_PROFILE"
```
