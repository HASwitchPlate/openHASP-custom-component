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
