<img src="https://user-images.githubusercontent.com/6897215/225175629-28f80bfb-3b0a-44ac-8b52-b719953958d7.png" align="right" style="width: 300px;" />

# Home Assistant on Stream Deck: configured via YAML (with templates) and running on Linux, MacOS, and Windows

Introducing: Home Assistant on Stream Deck!

Do you use Home Assistant and wish to control it more easily?
Look no further!
With this simple Python script, you can control your Home Assistant instance via a Stream Deck.
That's right, with just a few clicks, you can control your smart home devices and scenes right from your Stream Deck.

Not only is it easy to use, but it's also highly customizable.
You can configure it via a YAML file, making it incredibly flexible.
Plus, it runs on Linux, MacOS, and Windows, so you can use it on the same machine as Home Assistant or on a separate machine like a Raspberry Pi or any other computer.

"But wait," you say, "I've seen similar projects on Github before. [[†](https://github.com/cgiesche/streamdeck-homeassistant)]" Yes, you're right.
But our solution is more versatile and allows you to connect a Stream Deck to the same Linux machine where Home Assistant is running.
Unfortunately, the native Stream Deck software doesn't support Linux, but we've got you covered with the help of the [`python-elgato-streamdeck`](https://github.com/abcminiuser/python-elgato-streamdeck) library.

Are you ready to give it a try? Great!

https://user-images.githubusercontent.com/6897215/226788119-6c198ea6-2950-4f95-95dc-346c9e5b5cee.mp4

## Installation

Just run `pip install -e .` in the repo folder to install the required dependencies.

## Configuration

Then, create a `configuration.yaml` file in the same directory.

Now, for the fun part! You have two options for usage:

Option 1: With environment variables.
Edit the [`.env.example`](.env.example) file and rename it to `.env`.
Then, run the program without any arguments (just `home-assistant-streamdeck-yaml`), and the script will automatically load the environment variables from the `.env` file.

Option 2: With command-line arguments.
Run `home-assistant-streamdeck-yaml -h` to see the available options.
For example, you can use

```bash
home-assistant-streamdeck-yaml --host "klasdhkjashdhaksdl.ui.nabu.casa" --token "SOME_TOKEN_FROM_YOUR_PROFILE" --config "my_configuration.yml"
```
to customize your setup even further.

That's it! With just a little bit of setup, you can enjoy controlling your smart home devices with ease.
Check out the [configuration.yaml](configuration.yaml) file for an example configuration, or feel free to share your own with the community.

Happy controlling!

## `configuration.yaml`

Example `configuration.yaml`:
```yaml
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
          volume_level: '{{ max(state_attr("media_player.kef_ls50", "volume_level") - 0.05, 0) }}'
          entity_id: media_player.kef_ls50
        text: '{{ (100 * state_attr("media_player.kef_ls50", "volume_level")) | int }}%'
        text_size: 16
        icon_mdi: "volume-minus"
      - special_type: go-to-page
        special_type_data: 0
```

Each button can take the following configuration:

<!-- START_CODE -->
<!-- from home_assistant_streamdeck_yaml import Button -->
<!-- print(Button.to_markdown_table()) -->
<!-- END_CODE -->
<!-- START_OUTPUT -->
<!-- THIS CONTENT IS AUTOMATICALLY GENERATED -->
| Variable name           | Type                                                                                      | Default   | Allow template   | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
|:------------------------|:------------------------------------------------------------------------------------------|:----------|:-----------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `entity_id`             | `Optional[str]`                                                                           |           | `True`           | The `entity_id` that this button controls.This entitity will be passed to the `service` when the button is pressed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `service`               | `Optional[str]`                                                                           |           | `True`           | The `service` that will be called when the button is pressed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `service_data`          | `Optional[Mapping[str, Any]]`                                                             |           | `True`           | The `service_data` that will be passed to the `service` when the button is pressed. If empty, the `entity_id` will be passed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `text`                  | `str`                                                                                     |           | `True`           | The text to display on the button. If empty, no text is displayed. You might want to add `\n` characters to spread the text over several lines, or use the `\|` character in YAML to create a multi-line string.                                                                                                                                                                                                                                                                                                                                                                                   |
| `text_color`            | `Optional[str]`                                                                           |           | `True`           | Color of the text. If empty, the color is `white`, unless an `entity_id` is specified, in which case the color is `amber` when the state is `on`, and `white` when it is `off`.                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `text_size`             | `int`                                                                                     | `12`      | `False`          | Integer size of the text.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `icon`                  | `Optional[str]`                                                                           |           | `True`           | The icon filename to display on the button. If empty, a icon with `icon_background_color` and `text` is displayed. The icon can be a URL to an image, like `'url:https://www.nijho.lt/authors/admin/avatar.jpg'`, or a `spotify:` icon, like `'spotify:album/6gnYcXVaffdG0vwVM34cr8'`. If the icon is a `spotify:` icon, the icon will be downloaded and cached.                                                                                                                                                                                                                                   |
| `icon_mdi`              | `Optional[str]`                                                                           |           | `True`           | The Material Design Icon to display on the button. If empty, no icon is displayed. See https://mdi.bessarabov.com/ for a list of icons. The SVG icon will be downloaded and cached.                                                                                                                                                                                                                                                                                                                                                                                                                |
| `icon_background_color` | `str`                                                                                     | `#000000` | `True`           | A color (in hex format, e.g., '#FF0000') for the background of the icon (if no `icon` is specified).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `icon_mdi_color`        | `Optional[str]`                                                                           |           | `True`           | The color of the Material Design Icon (in hex format, e.g., '#FF0000'). If empty, the color is derived from `text_color` but is less saturated (gray is mixed in).                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `icon_gray_when_off`    | `bool`                                                                                    |           | `False`          | When specifying `icon` and `entity_id`, if the state is `off`, the icon will be converted to grayscale.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `special_type`          | `Optional[Literal['next-page', 'previous-page', 'empty', 'go-to-page', 'light-control']]` |           | `False`          | Special type of button. If no specified, the button is a normal button. If `next-page`, the button will go to the next page. If `previous-page`, the button will go to the previous page. If `empty`, the button will be empty. If `go-to-page`, the button will go to the page specified by `special_type_data` (either an `int` or `str` (name of the page)). If `light-control`, the button will control a light, and the `special_type_data` should optionally be a dictionary with the 'colormap' key and a value a colormap (https://matplotlib.org/stable/tutorials/colors/colormaps.html). |
| `special_type_data`     | `Optional[Any]`                                                                           |           | `True`           | Data for the special type of button. If `go-to-page`, the data should be an `int` or `str` (name of the page). If `light-control`, the data should optionally be a dictionary with the 'colormap' key and a value a colormap (https://matplotlib.org/stable/tutorials/colors/colormaps.html).                                                                                                                                                                                                                                                                                                      |

<!-- END_OUTPUT -->
