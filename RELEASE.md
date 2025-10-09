# 0.7.7
* Fix for firmware version number has more than three digits. by @fvanroie

# 0.7.6
* Fix: MQTTt not being ready at startup. by @xNUTx in https://github.com/HASwitchPlate/openHASP-custom-component/pull/149

# 0.7.5
* Support for HA 2024.9 by @dgomes 
* fix: Reuse of the same image with different sized displays causes a random resize. by @xNUTx in https://github.com/HASwitchPlate/openHASP-custom-component/pull/143
* fix: Dynamic reloading broken on recently added displays. by @xNUTx in https://github.com/HASwitchPlate/openHASP-custom-component/pull/140
* feat: Added optional setting http_proxy to push_image by @xNUTx in https://github.com/HASwitchPlate/openHASP-custom-component/pull/144

# 0.7.4
* Fixes 'str' object has no attribute 'read' by @illuzn in https://github.com/HASwitchPlate/openHASP-custom-component/pull/132
* Replace deprecated async_forward_entry_setup call by @TNTLarsn in https://github.com/HASwitchPlate/openHASP-custom-component/pull/137
* fix: properly split jsonl upload at lineends by @akloeckner in https://github.com/HASwitchPlate/openHASP-custom-component/pull/138

# 0.7.3
-  Support for 2024.6.0
-  Fixed height & width were being transposed when fitscreen=true by @FreeBear-nc in https://github.com/HASwitchPlate/openHASP-custom-component/pull/121
-  Move file open() to executor job by @dgomes in https://github.com/HASwitchPlate/openHASP-custom-component/pull/123
-  feat: allow full script syntax in event section by @akloeckner in https://github.com/HASwitchPlate/openHASP-custom-component/pull/112

# 0.7.2
- Support discovery through mDNS (0.7.0-rc11 or higher)
- Support for HA 2024.1
- Replace version popup for legacy 0.6.x plates with log warning

# 0.7.1
- Fix error as `ANTIALIAS` was removed in Pillow 10.0.0. Now using `LANCZOS` instead.
- Updated Manifest.json

# 0.7.0
- Better handling of discovery for 0.7.0-dev firmware

# 0.6.6
- Support for 2022.7.0
- Code improvements

# 0.6.5
- Support for 2022.4.0
- Adds page number entity
- Adds restart button
- Code improvements

# 0.6.4
- Support for 2021.12.0
- Change startup message from warning to info (@fvanroie)
- Adds configuration URL
- Antiburn configuration switch
- Minor bug fixes

# 0.6.3
- Accepts .json files which contain an array
- JSON files undergo schema validation
- JSONL batching improves performance

# 0.6.2
- Add new service that serves images directly to OpenHASP

# 0.6.1
- Fixes to work with HA 2021.8.1

# 0.6.0
- Improves UX
- Entity names have changed
- Configuration is now handled through the UI (Config-flow)
- Plates are discovered
- Component checks firmware version on discovery
- GPIO's are exposed as Light's and Switches as configured in the plate
- Sync with all the changes in firmware version 0.6.0
- Cleans all subscriptions and updates on device removal

It is recommended that you erase configuration from your yaml file (except for objects) and follow the instructions on the log file about the slug to be used in the yaml file.
