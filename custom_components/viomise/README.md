# Hacky Home assistant support for Viomi Robot Vacuum Cleaner SE (V-RVCLM21A)

## This is for Viomi Robot Vacuum Cleaner SE (apparently EU version) with 4.0.9_0012 firmware

### Install:
- install it with HACS
- Add the configuration to configuration.yaml, example:

```yaml
vacuum:
  - platform: viomise
    host: 192.168.68.105
    token: !secret vacuum
    name: Mi hihi
```
