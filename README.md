# Viomi SE Vacuum Integration for Home Assistant (v2)

## This is a custom component for [Home Assistant](https://www.home-assistant.io/ ) to integrate the Viomi SE Vacuum Cleaner (`viomi.vacuum.v19`) - apparently EU version - with 4.0.9_0012 firmware and tested in 4.0.9_0017
This version (v2) has been completely refactored to use modern Home Assistant practices, including UI-based configuration (`Config Flow`), device-specific sensors, and configurable options.

<img src="https://github.com/home-assistant/brands/raw/master/custom_integrations/viomise/logo.png" width=48%> 

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg )](https://github.com/hacs/integration )

## <a name="table-of-contents"></a>Table of Contents
*   [Features](#features)
*   [Prerequisites](#prerequisites)
*   [Installation](#installation)
    *   [HACS (Recommended)](#hacs-installation)
    *   [Manual Installation](#manual-installation)
*   [Configuration](#configuration)
*   [Options](#options)
*   [Entities Provided](#entities)
    *   [Vacuum](#vacuum-entity)
    *   [Sensors](#sensor-entities)
*   [Custom Services](#services)
*   [Contributions](#contributions)
*   [License](#license)*   [Troubleshooting](#troubleshooting)


---

## <a name="features"></a>✨ Features

*   **UI Configuration**: No more `configuration.yaml`! Set up and configure the vacuum entirely through the Home Assistant user interface.
*   **Standard Vacuum Controls**: `start`, `pause`, `stop`, `return_to_base`, `locate`.
*   **Fan Speed Control**: Adjust fan speeds (`Silent`, `Standard`, `Medium`, `Turbo`).
*   **Consumable Sensors**: Dedicated sensors for the life percentage of:
    *   Main Brush
    *   Side Brush
    *   Filter
    *   Mop
*   **Battery Sensor**: A dedicated sensor for the battery level.
*   **Configurable Timings**: Adjust the **Command Cooldown** and **Update Interval** via the integration's options to fine-tune performance for your network.
*   **Custom Services**: Advanced cleaning commands for zones, segments (rooms), and specific points.
*   **Multi-language Support**: UI is translated into English and Portuguese.

---

## <a name="prerequisites"></a>📋 Prerequisites

You need to obtain the **IP Address** and the **32-character Token** of your Viomi SE vacuum.

The easiest way to get the token is by using the [Xiaomi Miot Auto](https://github.com/al-one/hass-xiaomi-miot ) integration, which can automatically discover tokens for devices on your network. Alternatively, you can use the [python-miio](https://python-miio.readthedocs.io/en/latest/discovery.html#obtaining-the-token ) tool.

---

## <a name="installation"></a>🚀 Installation

This integration is now part of the default HACS repository!

1.  Go to your HACS page in Home Assistant.
2.  Click on **"Integrations"**.
3.  Click the **"Explore & Download Repositories"** button in the bottom right corner.
4.  Search for **"Viomi SE Vacuum"**.
5.  Click on the integration and then click **"Download"**.
6.  Restart Home Assistant when prompted.

### <a name="manual-installation"></a>Manual Installation

1.  Download the latest release from the [Releases](https://github.com/marotoweb/home-assistant-vacuum-viomise/releases ) page.
2.  Unzip the downloaded file.
3.  Copy the entire `viomise` folder (which contains all the necessary files like `__init__.py`, `vacuum.py`, `sensor.py`, etc.) into your Home Assistant's `custom_components` directory. The final path should look like `<config_directory>/custom_components/viomise`.
4.  Restart Home Assistant.

---

## <a name="configuration"></a>⚙️ Configuration

Once the integration is installed and Home Assistant is restarted, you can add your vacuum via the UI.

1.  Go to **Settings** > **Devices & Services**.
2.  Click the **+ ADD INTEGRATION** button in the bottom right corner.
3.  Search for **"Viomi SE"** and click on it.
4.  A configuration dialog will appear. Enter the following:
    *   **Device Name**: A friendly name for your vacuum (e.g., "Viomi SE").
    *   **IP Address**: The local IP address of your vacuum.
    *   **Token**: The 32-character token you obtained earlier.
5.  Click **"Submit"**.

If the details are correct, the integration will be added, and a new device with its entities will appear.

---

## <a name="options"></a>🔧 Options

After adding the integration, you can fine-tune its behavior.

1.  Go to **Settings** > **Devices & Services**.
2.  Find the Viomi SE integration and click on **"Configure"**.
3.  You can adjust the following options:
    *   **Command Cooldown (seconds)**: The minimum time to wait between sending commands to the vacuum. This prevents flooding the device with requests. (Default: `2.5`)
    *   **Update Interval (seconds)**: How often to fetch status updates from the vacuum. (Default: `30`)

---

## <a name="entities"></a>📦 Entities Provided

### <a name="vacuum-entity"></a>Vacuum (`vacuum.viomi_se`)

This is the main entity for controlling the vacuum. It provides standard controls and attributes showing the vacuum's status, such as `run_state`, `mode`, `cleaned_area`, etc.

### <a name="sensor-entities"></a>Sensors (`sensor.*`)

The integration creates the following diagnostic sensors, which you can add to your dashboards:

*   `sensor.viomi_se_battery`
*   `sensor.viomi_se_main_brush_life`
*   `sensor.viomi_se_side_brush_life`
*   `sensor.viomi_se_filter_life`
*   `sensor.viomise_mop_life`

*Note: The exact entity ID may vary slightly based on your Home Assistant naming conventions.*

---

## <a name="services"></a>🛠️ Custom Services

In addition to the standard vacuum services, this integration provides custom services for advanced cleaning modes. You can call these from scripts or automations.

| Service                       | Description                               | Parameters                                     |
| ----------------------------- | ----------------------------------------- | ---------------------------------------------- |
| `vacuum.vacuum_clean_segment` | Cleans one or more specific rooms/segments. | `segments`: A list of room IDs (e.g., `[1, 3]`). |
| `vacuum.vacuum_clean_zone`    | Cleans a rectangular zone.                | `zone`: `[x1, y1, x2, y2]`, `repeats`: `1-3`.    |
| `vacuum.vacuum_goto`          | Sends the vacuum to a specific coordinate.  | `x_coord`: X coordinate, `y_coord`: Y coordinate.  |
| `vacuum.xiaomi_clean_point`   | Cleans around a specific point.           | `point`: `[x, y]`.                             |

**Example Service Call (in YAML):**
```yaml
service: vacuum.vacuum_clean_segment
target:
  entity_id: vacuum.viomi_se
data:
  segments: [16, 17]
```

## <a name="troubleshooting"></a>❓ Troubleshooting

*   **"Failed to connect" error**: Double-check that the IP address is correct and that the vacuum is on the same network. The token might be incorrect or may have changed if you reset the vacuum's Wi-Fi.
*   **Device is "Unavailable"**: This usually means Home Assistant cannot reach the vacuum at its IP address. Check your network and ensure the vacuum is online in the Mi Home app.
*   **Logs**: To get more information, you can enable debug logging for the integration by adding the following to your `configuration.yaml`:
    ```yaml
    logger:
      default: info
      logs:
        custom_components.viomise: debug
        miio: debug
    ```

---

## <a name="contributions"></a>🤝 Contributions

Contributions are welcome! If you find a bug or have a suggestion for a new feature, please [open an issue](https://github.com/marotoweb/home-assistant-vacuum-viomise/issues ) or submit a [pull request](https://github.com/marotoweb/home-assistant-vacuum-viomise/pulls ).

---

## <a name="license"></a>📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

