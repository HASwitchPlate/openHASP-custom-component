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

### Example 1: cover control with state feedback
![kép](https://user-images.githubusercontent.com/1550668/112142921-77daf580-8bd7-11eb-9626-ebfb3423629d.png)
<br>UI theme set to `Hasp Light` in plate's web interface.

**hasp-lvgl config:**
```text
{"page":1,"comment":"---------- Page 1 ----------"}
{"obj":"btn","id":4,"x":5,"y":140,"w":73,"h":60,"toggle":false,"text":"\uF077","text_font":28}
{"obj":"btn","id":5,"x":83,"y":140,"w":73,"h":60,"toggle":false,"value_str":"\uF04D","text_font":12,"text_color":"Teal","value_font":28,"value_color":"#FFFFFF"}
{"obj":"btn","id":6,"x":161,"y":140,"w":73,"h":60,"toggle":false,"text":"\uF078","text_font":28}
{"obj":"btn","id":7,"x":5,"y":210,"w":73,"h":60,"toggle":false,"text":"\uF077","text_font":28}
{"obj":"btn","id":8,"x":83,"y":210,"w":73,"h":60,"toggle":false,"value_str":"\uF04D","text_font":12,"text_color":"teal","value_font":28,"value_color":"#FFFFFF"}
{"obj":"btn","id":9,"x":161,"y":210,"w":73,"h":60,"toggle":false,"text":"\uF078","text_font":28}
```
**hasp-lvgl-custom-component config:**
```yaml
      - obj: "p1b4"
        properties:
          "text_color": "{{ '#FFFF00' if states('cover.cover_1') == 'opening' else '#FFFFFF' }}"
          "text_opa": "{{ '80' if state_attr('cover.cover_1','current_position') == 100 else '255' }}"
        event:
          "down":
            service: cover.open_cover
            target:
              entity_id: "cover.cover_1"
      - obj: "p1b5"
        properties:
          "text": "{{ state_attr('cover.cover_1','current_position') }}" 
        event:
          "down":
            service: cover.stop_cover
            target:
              entity_id: "cover.cover_1"
      - obj: "p1b6"
        properties:
          "text_color": "{{ '#FFFF00' if states('cover.cover_1') == 'closing' else '#FFFFFF' }}"
          "text_opa": "{{ '80' if state_attr('cover.cover_1','current_position') == 0 else '255' }}"
        event:
          "down":
            service: cover.close_cover
            target:
              entity_id: "cover.cover_1"

      - obj: "p1b7"
        properties:
          "text_color": "{{ '#FFFF00' if states('cover.cover_2') == 'opening' else '#FFFFFF' }}"
          "text_opa": "{{ '80' if state_attr('cover.cover_2','current_position') == 100 else '255' }}"
        event:
          "down":
            service: cover.open_cover
            target:
              entity_id: "cover.cover_2"
      - obj: "p1b8"
        properties:
          "text": "{{ state_attr('cover.haloszoba_kozep','current_position') }}" 
        event:
          "down":
            service: cover.stop_cover
            target:
              entity_id: "cover.cover_2"
      - obj: "p1b9"
        properties:
          "text_color": "{{ '#FFFF00' if states('cover.cover_2') == 'closing' else '#FFFFFF' }}"
          "text_opa": "{{ '80' if state_attr('cover.cover_2','current_position') == 0 else '255' }}"
        event:
          "down":
            service: cover.close_cover
            target:
              entity_id: "cover.cover_2"
```

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)


## TODO

- Auto-discovery [ ]
