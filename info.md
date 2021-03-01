## CUSTOM HEADER

This will assist you in getting started with [HASP-lvgl](https://fvanroie.github.io/hasp-docs/#) and Home Assistant.

### [Docs eventually](https://github.com/dgomes/hasp-lvgl)

### Features

Still a long way to go...

```yaml
hasp_lvgl:
  plate_123456:
    topic: "hasp/plate_123456"
    pages:
      prev_obj: "p0b1"
      home_obj: "p0b2"
      next_obj: "p0b3"
    objects:
      - obj: "p1b2"
        track: "sensor.power"
      - obj: "p1b6"
        event:
          down:
            service: light.turn_on
            target:
              entity_id: "light.hasp_plate_123456_moodlight"
          long:
            service: light.turn_off
            target:
              entity_id: "light.hasp_plate_123456_moodlight"
      - obj: "p1b8"
        track: "light.dining_light_light"
```


This is a work in progress custom_component, We break all the time :)

