# GC Monitoring Tool

The GC Monitoring Tool is a Python-based utility that allows you to monitor the status of the "GC" service on Android devices. It checks if the service is actively running or frozen and provides an interface to restart it if needed.

## Features

- Monitor the status of the GC service on multiple Android devices.
- Automatically restart the GC service on devices where it has frozen.
- User-friendly graphical interface
- Configurable check intervals and cycle delays.

## Requirements

- Python 3.x
- ADB (Android Debug Bridge) installed and accessible in your system's PATH.
- Pillow (in requirements)

## Getting Started

1. Clone this repository to your local machine:
```python
git clone https://github.com/veryraregaming/GC-Monitoring-Tool.git
```
2. Navigate to the project directory:
```python
cd GC-Monitoring-Tool
```
3. Install the required Python packages:
```python
pip install -r requirements.txt
```
4. Edit the `devices.config` file to specify the names and IP addresses of the Android devices you want to monitor.

5. Run the GC Monitoring Tool:
```python
python device_monitor.py
```
6. The graphical user interface will open, displaying the status of each device. You can click the "Restart GC" button to restart the GC service on a specific device if needed.

## Configuration

You can configure the monitoring intervals, log settings, and more in the `device_monitor.py` script. Refer to the script's comments for detailed information on available options.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- This tool utilizes the Android Debug Bridge (ADB) for device communication.
- Special thanks to the open-source community for valuable contributions and feedback.
