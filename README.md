# HASP - Open SwitchPlate Custom Component

This custom component simplifies synchronization of a [HASP - Open SwitchPlate](https://fvanroie.github.io/hasp-docs/#) objects with Home Assistant entities.

## Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `hasp-lvgl`.
4. Download _all_ the files from the `custom_components/hasp-lvgl/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Edit your `configuration.yaml` file add an entry similar to the example.
7. Restart Home Assistant

Using your HA configuration directory (folder) as a starting point you should now also have this:

```text
custom_components/hasp-lvgl/__init__.py
custom_components/hasp-lvgl/const.py
custom_components/hasp-lvgl/manifest.json
```

## Example Configuration 

```yaml
hasp_lvgl:
  plate_dev:
    topic: "hasp/plate35"
    pages:
      prev_obj: "p0b1"
      home_obj: "p0b2"
      next_obj: "p0b3"
    objects:
      - obj: "p1b2"
        properties:
          "val": "{{ states('sensor.power') }}"
      - obj: "p1b8"
        properties:
          "val": "{{ 1 if states('input_boolean.teste1') == 'on' else 0 }}"
        event:
          "on":
            service: homeassistant.turn_on
            target:
              entity_id: "input_boolean.teste1"
          "off":
            service: homeassistant.turn_off
            target:
              entity_id: "input_boolean.teste1"
      - obj: "p2b2"
        event:
          "changed":
            service: persistent_notification.create
            data:
              message: Hello {{ text }}
```

In the event service call any variable coming from the MQTT message can be used between curly brackets. 

## Examples

You can find further configuration examples in [Wiki](https://github.com/dgomes/hasp-lvgl-custom-component/wiki).

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)


## TODO

- Auto-discovery [ ]
