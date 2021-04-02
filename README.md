# openHASP - openHASP Custom Component

This custom component simplifies synchronization of objects on one or more openhasp [HASP - Open SwitchPlates](https://haswitchplate.github.io/openHASP-docs/) with Home Assistant entities. An Open SwitchPlate is basically a small touchscreen device which you can mount on the wall in place of a switch, and you can design your custom user interface for it using json. You can build your own hardware but you can also buy them ready-made.

## Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `openhasp`.
4. Download _all_ the files from the `custom_components/openhasp/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Edit your `configuration.yaml` file add an entry similar to the example below.
7. Restart Home Assistant

Using your HA configuration directory (folder) as a starting point you should now also have this:

```text
custom_components/openhasp/__init__.py
custom_components/openhasp/common.py
custom_components/openhasp/const.py
custom_components/openhasp/light.json
custom_components/openhasp/manifest.json
custom_components/openhasp/services.yaml
```

### Configuration

Make sure you have your plates connected to the network and each of them has a unique MQTT topic. Static DHCP or fixed IP are not needed as communication only happes through MQTT. 

To add a openhasp plate to your installation with a sample configuration, upload a `pages.jsonl` file with the folowing content to your plate first:

```
{"page":1,"id":1,"obj":"btn","x":0,"y":0,"w":240,"h":30,"text":"MY ROOM SWITCH","value_font":22,"bg_color":"#2C3E50","text_color":"#FFFFFF","radius":0,"border_side":0}
{"page":1,"id":2,"obj":"btn","x":10,"y":40,"w":105,"h":90,"toggle":true,"text":"Light","text_font":26,"mode":"break","align":1}

{"page":2,"id":1,"obj":"btn","x":0,"y":0,"w":240,"h":30,"text":"MY ROOM OPTION","value_font":22,"bg_color":"#2C3E50","text_color":"#FFFFFF","radius":0,"border_side":0}
{"page":2,"id":2,"obj":"dropdown","x":10,"y":40,"w":160,"h":30,"options":"Apple\nBanana\nOrange\nMelon"}

{"page":0,"id":1,"obj":"btn","page":0,"x":0,"y":285,"w":79,"h":35,"bg_color":"#2C3E50","text":"\uf060","text_color":"#FFFFFF","radius":0,"border_side":0,"text_font":28}
{"page":0,"id":2,"obj":"btn","page":0,"x":80,"y":285,"w":80,"h":35,"bg_color":"#2C3E50","text":"\uf015","text_color":"#FFFFFF","radius":0,"border_side":0,"text_font":28}
{"page":0,"id":3,"obj":"btn","page":0,"x":161,"y":285,"w":79,"h":35,"bg_color":"#2C3E50","text":"\uf061","text_color":"#FFFFFF","radius":0,"border_side":0,"text_font":28}
{"page":0,"id":4,"obj":"label","x":175,"y":5,"h":30,"w":62,"text":"00.0°C","align":2,"bg_color":"#2C3E50","text_color":"#FFFFFF"}
```

Assuming your plate's configured MQTT topic is `plate35`, add the following to your `configuration.yaml` file:

```yaml
openhasp:
  plate_my_room:
    topic: "hasp/plate35"
    path: "/config/openhasp/pages_my_room.jsonl"
    idle_brightness: 8
    pages:
      prev_obj: "p0b1"
      home_obj: "p0b2"
      next_obj: "p0b3"
    objects:
      - obj: "p0b4"
        properties:
          "text": "{{ states('sensor.my_room_temperature') }}°C"
      - obj: "p1b2"
        properties:
          "val": "{{ 1 if states('light.my_room') == 'on' else 0 }}"
        event:
          "on":
            service: light.turn_on
            target:
              entity_id: "light.my_room"
          "off":
            service: light.turn_off
            target:
              entity_id: "light.my_room"
      - obj: "p2b2"
        event:
          "changed":
            service: persistent_notification.create
            data:
              message: I like {{ text }}
```

### Configuration Variables

**openhasp:**\
  *(Required)* Your platform identifier. Can be replaced with `openhasp: !include zz_etc/hasp_lvgl.yaml` which will allow you to store all further options in a separate configuration file located at `zz_etc/hasp_lvgl.yaml`.

**plate_my_room:**\
  *(Required)* Your plate identifier. For each plate in your sytem, such an entry is required, has to be unique.

**topic:**\
  *(string)* *(Required)* The MQTT topic your plate is configured with.

**path:**\
  *(path)* *(Optional)* Path to a `pages.jsonl` file containing design for this plate, to be loaded on Home Assistant start and on plate availability (becoming online). _Note:_ Don't upload any `pages.jsonl` file to the plate's flash memory at all! This assumes your plate pages are empty at boot. See further down for requirements to use this.

**idle_brightness:**\
  *(int)* *(Optional)* The brightness of the screen when idle (before long idle). Numeric value between 0 and 100. Default 10. 

**pages:**\
  *(Optional)* Page navigation objects: `prev_obj`, `home_obj`, `next_obj` are the dedicated objects on the screen which will navigate the pages in previous, home and next directions, respectively. (_Note:_ objects on page `0`, have `p0` in their name, they appear on all pages).

**objects:**\
  *(Optional)* Definition of the objects reacting to changes in Home Assistant, or generating events for Home Assistant.

**obj:**\
   *(string)* *(Required)* The object identifier which we want to integrate with Home Assistant. Its name has the form `pXbY` where `X` represents the page where the object is located, and `Y` represents the `id` of the object on that page.

**properties:**\
  *(Optional)* List containing the properties of the object which we want to modify based on changes occurring in Home Assistant. In the example above `text` property gets updated whenever `sensor.my_room_temperature` changes. Various properties are available for the objects, full details in [openhasp documentation](https://haswitchplate.github.io/openHASP-docs/#objects/).
  
**event:**\
  *(Optional)* List containing the events generated by the object when touched on the screen. These are object-specific, and can be observed accurately with an MQTT client. In the example above, when object `p1b2` (which is a toggle button) generates the `on` event, `light.my_room` will be turned on by the service call `light.turn_on` as specified in the event config. And similarily when `off` event comes through MQTT, the light will be turned off by the corresponding service call.

_Note:_ Any variable coming from the MQTT message can be used between curly brackets, and passed to the service call. In the example above when object `p2b2` (which is a dropdown selector) generates the `changed` event, a persistent notification will appear in Home Assistant's Lovelace interface containing the selected text from the object, which was passed over from the MQTT message.

### Component-specific services

This component implements some specific services to make interactions with the plate even more comfortable.

**openhasp.wakeup**\
  Wakes up the display when an external event has occurred, like a presence or a PIR motion sensor.

**openhasp.next_page**\
  Changes plate to the next page.

**openhasp.prev_page**\
  Changes plate to the previous page.

**openhasp.change_page**\
  Changes plate directly to the specified page number.

**openhasp.clear_page**\
  Clears the contents of the specified page number. If not specified, clears all the pages.

**openhasp.load_pages**\
  Loads new design from pages.jsonl file from _full path_ (e.g. `/config/pages.jsonl` in case of hassio). The file must be located in an authorised location defined by [allowlist_external_dirs](https://www.home-assistant.io/docs/configuration/basic/#allowlist_external_dirs). _Important:_ the contents of the file are loaded line by line thus `"page":X` has to be defined for each object. Unless you clear the page first, the objects will be updated.


### Examples

You can find further configuration examples in [Wiki](https://github.com/HASwitchPlate/openHASP-custom-component/wiki).

### Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)


### TODO

- Auto-discovery [ ]
