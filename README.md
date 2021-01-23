# Hacky Home assistant support for Viomi SE (V-RVCLM21A)

## This is for Viomi Robot Vacuum Cleaner SE (apparently EU version) with 4.0.9_0012 firmware

## Installation

### Using [HACS](https://hacs.xyz/) (recommended)

This integration can be added to HACS as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories):
* URL: `https://github.com/marotoweb/home-assistant-vacuum-viomise`
* Category: `Integration`

After adding a custom repository you can use HACS to install this integration using user interface.

### Manual

To install this integration manually you have to download following files:

* [*README.md*](https://raw.githubusercontent.com/marotoweb/home-assistant-vacuum-viomise/master/custom_components/viomise/README.md)
* [*__init__.py*](https://raw.githubusercontent.com/marotoweb/home-assistant-vacuum-viomise/master/custom_components/viomise/__init__.py)
* [*vacuum.py*](https://raw.githubusercontent.com/marotoweb/home-assistant-vacuum-viomise/master/custom_components/viomise/vacuum.py)
* [*manifest.json*](https://raw.githubusercontent.com/marotoweb/home-assistant-vacuum-viomise/master/custom_components/viomise/manifest.json)

to `config/custom_components/viomise` directory:

```bash
mkdir -p custom_components/viomise
cd custom_components/viomise
wget https://raw.githubusercontent.com/marotoweb/home-assistant-vacuum-viomise/master/custom_components/viomise/vacuum.py
wget https://raw.githubusercontent.com/marotoweb/home-assistant-vacuum-viomise/master/custom_components/viomise/__init__.py
wget https://raw.githubusercontent.com/marotoweb/home-assistant-vacuum-viomise/master/custom_components/viomise/manifest.json
```

## Configuration

Add the configuration to `configuration.yaml` file, example:
Vacuum token can be extracted by following [this guide](https://www.home-assistant.io/integrations/xiaomi_miio/#retrieving-the-access-token).
You also need to enter your Xiaomi Cloud username and password.
These are the credentials used for the Xiaomi Home app (_not ones from Viomi Robot app_).

```yaml
vacuum:
  - platform: viomise
    host: 192.168.68.105
    token: !secret vacuum
    name: Mi hihi
```
