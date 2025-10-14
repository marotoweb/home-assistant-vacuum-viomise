# Viomi SE (V-RVCLM21A) Vacuum Integration for Home Assistant

## This is for Viomi Robot Vacuum Cleaner SE (apparently EU version) with 4.0.9_0012 firmware and tested in 4.0.9_0017

<img src="https://github.com/home-assistant/brands/raw/master/custom_integrations/viomise/logo.png" width=48%> 

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg )](https://github.com/hacs/integration )

This is a custom component for [Home Assistant](https://www.home-assistant.io/ ) to integrate the **Viomi SE Vacuum Cleaner** (`viomi.vacuum.v19`).

It provides a vacuum entity that allows you to control your vacuum cleaner and monitor its status directly from Home Assistant.

This integration communicates with the device locally, so it does not require a cloud connection.

## Features

*   Start, stop, and pause cleaning.
*   Return to the charging dock.
*   Locate the vacuum (makes it play a sound).
*   Adjust fan speed (Silent, Standard, Medium, Turbo).
*   Monitor status (cleaning, docked, charging, etc.).
*   Check battery level.
*   View error states.

## Prerequisites

1.  **Your Viomi SE vacuum must be connected to your local network.**
2.  You need to know the **IP Address** of your vacuum. You can usually find this in your router's DHCP client list. It's recommended to assign a static IP address to your vacuum.
3.  You need the **Device Token**. This is a 32-character string required to communicate with the device.

### How to get the device token?

The easiest way to get the token is by using the [Xiaomi Miio](https://github.com/jgh/python-miio ) command-line tool.

```bash
# Install the tool
pip install python-miio

# Discover devices on your network
miio discover
```

The output will show you the IP address, device model, and the token for all Xiaomi devices on your network. Find your Viomi SE vacuum in the list and copy the token.

## Installation

The recommended way to install this integration is through the [Home Assistant Community Store (HACS)](https://hacs.xyz/ ).

1.  **Add Custom Repository:**
    *   Go to HACS > Integrations.
    *   Click the three dots in the top right corner and select "Custom repositories".
    *   In the "Repository" field, paste this GitHub URL: `https://github.com/marotoweb/home-assistant-vacuum-viomise`
    *   In the "Category" dropdown, select "Integration".
    *   Click "Add".

2.  **Install the Integration:**
    *   The "Viomi SE Vacuum" integration will now appear in your HACS integrations list.
    *   Click "Install" and follow the prompts.

3.  **Restart Home Assistant:**
    *   After installation, you must restart Home Assistant for the integration to be loaded.

## Configuration

Configuration is now done entirely through the Home Assistant user interface.

1.  Navigate to **Settings > Devices & Services**.
2.  Click the **+ ADD INTEGRATION** button in the bottom right corner.
3.  Search for **"Viomi SE Vacuum"** and click on it.
4.  A configuration dialog will appear. Enter the following information:
    *   **IP Address (Host ):** The local IP address of your vacuum cleaner.
    *   **Token:** The 32-character device token you obtained earlier.
5.  Click **Submit**.

The integration will test the connection. If successful, your vacuum will be added to Home Assistant and you will see a new device and entity.

## Lovelace Card

You can use the standard `vacuum-card` or other custom cards to control your vacuum from your Lovelace dashboard. Here is a basic example:

```yaml
type: entity
entity: vacuum.viomi_se
name: Aspirador da Sala
```

## Contributions

Contributions are welcome! If you find a bug or have a suggestion for a new feature, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.





