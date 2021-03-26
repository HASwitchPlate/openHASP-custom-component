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
![picture](https://user-images.githubusercontent.com/1550668/112142921-77daf580-8bd7-11eb-9626-ebfb3423629d.png)
<br>UI theme set to `Hasp Light` in plate's web interface. Two cover entities, each controlled by an up, stop and down button. The icon on the up and down buttons change color when covers move and set opacity when reached to limit. The stop button also shows the current percentage of the position.

**hasp-lvgl config:** (screen size 240x320) 
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
          "text": "{{ state_attr('cover.cover_2','current_position') }}" 
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

### Example 2: generic thermostat control
![picture](https://user-images.githubusercontent.com/1550668/112160012-09536300-8bea-11eb-867d-53c64894c324.png)
<br>Arc can be dragged by the handle, precise set possible from the buttons. Note that the `min`, `max` and `val` values of the arc are multiplied and divided by 10 when set and read, because [LVGL only suppports integers](https://github.com/fvanroie/hasp-lvgl/issues/81) for object values. By multiplying and dividing by 10, it becomes possible to set decimal values for climate temperature.

**hasp-lvgl config:** (screen size 240x320) 
```text
{"page":2,"comment":"---------- Page 2 ----------"}
{"obj":"arc","id":3,"x":20,"y":75,"w":200,"h":200,"min":180,"max":250,"border_side":0,"type":0,"rotation":0,"start_angle":135,"end_angle":45,"start_angle1":135,"end_angle1":45,"value_font":28,"value_color":"#2C3E50","adjustable":"true"}
{"obj":"dropdown","id":4,"x":75,"y":235,"w":90,"h":30,"options":""}
{"obj":"btn","id":5,"x":68,"y":162,"w":25,"h":25,"toggle":false,"text":"-","text_font":28,"align":1}
{"obj":"btn","id":6,"x":147,"y":162,"w":25,"h":25,"toggle":false,"text":"+","text_font":28,"align":1}
{"obj":"label","id":7,"x":60,"y":120,"w":120,"h":30,"text":"Status","align":1,"padh":50}
```
**hasp-lvgl-custom-component config:**
```yaml
      - obj: "p2b3"
        properties:
          "val": "{{ state_attr('climate.thermostat_1','temperature') * 10 | int }}"
          "value_str": "{{ state_attr('climate.thermostat_1','temperature') }}"
          "min": "{{ state_attr('climate.thermostat_1','min_temp') * 10 | int }}"
          "max": "{{ state_attr('climate.thermostat_1','max_temp') * 10 | int }}"
        event:
          "up":
            service: climate.set_temperature
            data:
              entity_id: climate.thermostat_1
              temperature: "{{ val | int / 10 }}"
      - obj: "p2b4"
        properties:
          "options": >
            {%for mode in state_attr('climate.thermostat_1','hvac_modes')%}{{mode+"\n"|e}}{%-if not loop.last%}{%-endif%}{%-endfor%}
        event:
          "changed":
            service: climate.set_hvac_mode
            data:
              entity_id: climate.thermostat_1
              hvac_mode: "{{ text }}"
      - obj: "p2b5"
        event:
          "down":
            service: climate.set_temperature
            data:
              entity_id: climate.thermostat_1
              temperature: "{{ state_attr('climate.thermostat_1','temperature') - state_attr('climate.thermostat_1','target_temp_step') | float}}" 
      - obj: "p2b6"
        event:
          "down":
            service: climate.set_temperature
            data:
              entity_id: climate.thermostat_1
              temperature: "{{ state_attr('climate.thermostat_1','temperature') + state_attr('climate.thermostat_1','target_temp_step') | float}}" 
      - obj: "p2b7"
        properties:
          "text": "{{ state_attr('climate.thermostat_1','hvac_action') }}"
```



## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)


## TODO

- Auto-discovery [ ]
