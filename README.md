# Hacky Home assistant support for Viomi SE (V-RVCLM21A)

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

## This is for Viomi Robot Vacuum Cleaner SE (apparently EU version) with 4.0.9_0012 firmware and tested in 4.0.9_0017

<img src="https://github.com/home-assistant/brands/raw/master/custom_integrations/viomise/logo.png" width=48%> 

## Installation

### Using [HACS](https://hacs.xyz/) (recommended)

- Open HACS
- Go to "Integrations" section
- Click button with "+" icon
- Search for "Viomi Robot Vacuum Cleaner SE"
- Install repository in HACS

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
wget https://raw.githubusercontent.com/marotoweb/home-assistant-vacuum-viomise/master/custom_components/viomise/README.md
wget https://raw.githubusercontent.com/marotoweb/home-assistant-vacuum-viomise/master/custom_components/viomise/__init__.py
wget https://raw.githubusercontent.com/marotoweb/home-assistant-vacuum-viomise/master/custom_components/viomise/vacuum.py
wget https://raw.githubusercontent.com/marotoweb/home-assistant-vacuum-viomise/master/custom_components/viomise/manifest.json
```

or you can download [*latest release package*](https://github.com/marotoweb/home-assistant-vacuum-viomise/releases/latest/download/viomi_se.zip)

```bash
mkdir -p custom_components/viomise
cd custom_components/viomise
wget https://github.com/marotoweb/home-assistant-vacuum-viomise/releases/latest/download/viomi_se.zip
unzip viomi_se.zip
```

## Configuration

Add the configuration to `configuration.yaml` file, like the example below:

```yaml
vacuum:
  - platform: viomise
    host: 192.168.68.105
    token: !secret vacuum
    name: Viomi SE
    # do not flood the vacuum with requests with scan_interval
    scan_interval: 30
```
Note: Vacuum token can be extracted by following [this guide](https://www.home-assistant.io/integrations/xiaomi_miio/#retrieving-the-access-token).
I recommend using the python script method to extract the token as it is simpler, and only requires you to enter your Xiaomi Cloud username and password.
These are the credentials used for the Xiaomi Home app (_not ones from Viomi Robot app_).

## Recommended lovelace card with user-friendly way to fully control Viomi that works with this integration
* [*Lovelace Vacuum Map card*](https://github.com/PiotrMachowski/lovelace-xiaomi-vacuum-map-card)
* [*Add new?...*](https://github.com/marotoweb/home-assistant-vacuum-viomise/issues/new)
