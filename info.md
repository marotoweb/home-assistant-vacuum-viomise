# Hacky support for Viomi SE (V-RVCLM21A)
This hacky integration adds support for Viomi Robot Vacuum Cleaner SE (V-RVCLM21A).  
Repository is forked from KrzysztofHajdamowicz/home-assistant-vacuum-styj02ym

Due to my lack of knowledge in python some things may not make sense or there is a better way to do them, we just shouldn't be stuc


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
