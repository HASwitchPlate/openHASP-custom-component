# HASP - Open SwitchPlate Custom Component

This custom component simplifies syncronization of a [HASP - Open SwitchPlate](https://fvanroie.github.io/hasp-docs/#) objects with Home Assistant entities.

## Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `hasp-lvgl`.
4. Download _all_ the files from the `custom_components/hasp-lvgl/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Blueprint"

Using your HA configuration directory (folder) as a starting point you should now also have this:

```text
custom_components/hasp-lvgl/__init__.py
custom_components/hasp-lvgl/const.py
custom_components/hasp-lvgl/manifest.json
```

## Example Configuration 

```yaml
hasp-lvgl:
  lanbon_l8:
    topic: "hasp/plate_6fe4fc"
    objects:
      - obj: "p1b2"
        entity: "sensor.power"
      - obj: "p1b4"
        entity: "sensor.heatpump"
      - obj: "p1b7"
        entity: "switch.blitzwolf_socket_0_switch"
```


## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)


