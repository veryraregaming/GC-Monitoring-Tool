import tkinter as tk
from PIL import Image, ImageTk
from tkinter import scrolledtext
import threading
import subprocess
import datetime
import time
import logging
from logging.handlers import RotatingFileHandler
import os
import queue

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(SCRIPT_DIR, "logo.png")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "devices.config")
LOGO_SIZE = (200, 200)
CHECK_INTERVAL = 5  # seconds between each device check
CYCLE_DELAY = 30  # seconds, delay between monitoring cycles
LOG_FILE = "device_monitor.log"
ADB_RETRY_LIMIT = 3  # Number of retries for ADB commands

# Configure logging with a fallback mechanism
def configure_logging(log_config):
    log_level = getattr(logging, log_config['LOG_LEVEL'].upper(), logging.INFO)
    try:
        logging.basicConfig(handlers=[RotatingFileHandler(
            log_config['LOG_PATH'],
            maxBytes=int(log_config['LOG_MAX_SIZE']),
            backupCount=int(log_config['LOG_BACKUP_COUNT']))],
            level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
    except Exception as e:
        # Fallback to console logging in case of failure
        logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
        logging.error(f"Logging configuration failed: {e}")

class DeviceMonitorApp:
    logo_row = 1

    def __init__(self, root):
        self.root = root
        self.root.title("Rare's Device Monitor")
        self.devices, self.log_config = self.load_config(CONFIG_FILE)
        configure_logging(self.log_config)  # Use the new logging setup
        self.status_labels = {}
        self.setup_ui()
        self.monitoring_thread = threading.Thread(target=self.monitor_devices, args=(queue.Queue(),), daemon=True)
        self.monitoring_thread.start()

    # Updated load_config method with validation
    def load_config(self, file_name):
        devices = {}
        log_config = {'LOG_PATH': 'logs/device_monitor.log',
                      'LOG_LEVEL': 'INFO',
                      'LOG_MAX_SIZE': 5 * 1024 * 1024,
                      'LOG_BACKUP_COUNT': 2}
        try:
            with open(file_name, 'r') as file:
                for line in file:
                    if line.startswith("#") or not line.strip():
                        continue
                    key, value = line.strip().split(maxsplit=1)
                    if key.startswith('LOG_'):
                        log_config[key] = int(value) if key == 'LOG_MAX_SIZE' else value
                    else:
                        devices[key] = value
        except FileNotFoundError:
            self.log(f"Error: Configuration file '{file_name}' not found.")
            return {}, log_config
        except Exception as e:
            self.log(f"Error reading configuration file: {e}")
            return {}, log_config

        return devices, log_config

    def setup_ui(self):
        self.root.configure(bg="#333333")
        self.add_logo(LOGO_PATH, LOGO_SIZE)
        title_label = tk.Label(self.root, text="GC-Monitoring-Tool by Rare", font=("Helvetica", 16), fg="white", bg="#333333")
        title_label.grid(row=0, column=0, columnspan=4, pady=10)

        row = 2
        for name, ip in self.devices.items():
            device_frame = tk.Frame(self.root, bg="#333333")
            device_frame.grid(row=row, column=0, sticky="ew", padx=20, pady=5)
            tk.Label(device_frame, text=name, bg="#555555", fg="white").grid(row=0, column=0, padx=5)
            pokemon_label = tk.Label(device_frame, text="Pokemon Go: Unknown", bg="gray")
            pokemon_label.grid(row=0, column=1, padx=5)
            self.status_labels[name, 'pokemon'] = pokemon_label
            gc_label = tk.Label(device_frame, text="GC: Unknown", bg="gray")
            gc_label.grid(row=0, column=2, padx=5)
            self.status_labels[name, 'gc'] = gc_label
            restart_gc_button = tk.Button(device_frame, text="Restart GC", command=lambda d=ip: self.restart_gc_services(d))
            restart_gc_button.grid(row=0, column=3, padx=5)
            row += 1

        self.log_text = scrolledtext.ScrolledText(self.root, height=10, bg="#222222", fg="white")
        self.log_text.grid(row=row, column=0, columnspan=4, sticky="ew", padx=20, pady=10)

    def add_logo(self, path, size):
        try:
            image = Image.open(path)
            image = image.resize(size, Image.BILINEAR)
            photo = ImageTk.PhotoImage(image)
            logo_label = tk.Label(self.root, image=photo, bg="#333333")
            logo_label.image = photo
            logo_label.grid(row=self.logo_row, column=0, columnspan=4, pady=10)
        except Exception as e:
            error_message = f"Error loading image: {e}"
            self.log(error_message)

    def log(self, message):
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        log_message = f"[{current_time}] {message}"

        def update_log_text():
            self.log_text.insert(tk.END, log_message + "\n")
            self.log_text.see(tk.END)

        self.root.after(0, update_log_text)
        logging.info(log_message)

    def restart_gc_services(self, device_ip):
        command1 = f"adb -s {device_ip} shell am force-stop com.nianticlabs.pokemongo"
        command2 = f"adb -s {device_ip} shell am start -n com.gocheats.launcher/com.gocheats.launcher.MainActivity"

        self.run_adb_command(command1)
        time.sleep(5)  # Add a delay to ensure processes are terminated before starting GC
        self.run_adb_command(command2)

    def reset_adb_server(self):
        self.log("Resetting ADB server...")
        self.run_adb_command("adb kill-server")
        self.run_adb_command("adb start-server")

        for _, ip in self.devices.items():
            connect_cmd = f"adb connect {ip}"
            connect_result = self.run_adb_command(connect_cmd)
            self.log(f"Connected to {ip}: {connect_result}")

    def auto_restart_services(self, device_ip):
        self.log(f"Auto-restarting device {device_ip}")
        command = f"adb -s {device_ip} reboot"
        self.run_adb_command(command)

    def update_device_status(self, device_name, pokemon_go_status, gc_status):
        def _update():
            pokemon_label = self.status_labels[device_name, 'pokemon']
            gc_label = self.status_labels[device_name, 'gc']

            pokemon_label.config(text=f"Pokemon Go: {'Running' if pokemon_go_status else 'Not Running'}", bg="green" if pokemon_go_status else "red")
            gc_label.config(text=f"GC: {'Running' if gc_status else 'Not Running'}", bg="green" if gc_status else "red")
        self.root.after(0, _update)

    # Updated run_adb_command with retry mechanism
    def run_adb_command(self, command):
        attempt = 0
        while attempt < ADB_RETRY_LIMIT:
            try:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
                else:
                    self.log(f"ADB command failed, attempt {attempt + 1}: {result.stderr.strip()}")
            except subprocess.SubprocessError as e:
                self.log(f"Error running command '{command}': {e}")

            attempt += 1
            time.sleep(1)  # Wait a bit before retrying

        self.log(f"Failed to execute ADB command after {ADB_RETRY_LIMIT} attempts.")
        return None

    def check_package_status(self, device_ip, package_name):
        command = f"adb -s {device_ip} shell pm list packages {package_name}"
        result = self.run_adb_command(command)
        return result == f"package:{package_name}"

    def check_gc_service_status(self, device_ip, monitoring_duration=10):
        active_service_indicator = "Handled RPC request"  # Indicator of active service
        logcat_command = f"adb -s {device_ip} logcat -T 1 -s Exeggcute"  # Starts logcat from the most recent log entry

        try:
            process = subprocess.Popen(logcat_command, shell=True, stdout=subprocess.PIPE, text=True)

            start_time = datetime.datetime.now()
            while (datetime.datetime.now() - start_time).total_seconds() < monitoring_duration:
                line = process.stdout.readline().strip()
                if active_service_indicator in line:
                    process.kill()
                    return True  # Active indicator found within the window
            process.kill()
            return False  # No active indicators found within the duration
        except subprocess.SubprocessError as e:
            return False  # Error occurred, unable to verify status


    def monitor_devices(self, device_queue):
        while True:
            self.reset_adb_server()  # Reset ADB server before each cycle

            total_devices = len(self.devices)
            current_device_index = 0

            for device_name, device_ip in self.devices.items():
                current_device_index += 1
                self.log(f"Device {current_device_index}/{total_devices}: Checking {device_name} - {device_ip}")

                pokemon_go_status = self.check_package_status(device_ip, "com.nianticlabs.pokemongo")
                gocheats_status = self.check_package_status(device_ip, "com.gocheats.launcher")

                # Check if GC service is active using the new method
                gc_active = self.check_gc_service_status(device_ip, monitoring_duration=10)

                if gc_active:
                    self.log(f"GC Service Running on {device_name}")
                    self.update_device_status(device_name, pokemon_go_status, True)  # Update UI to show GC service is running
                else:
                    self.log(f"GC Service Not Running or Frozen on {device_name}, Restarting Services...")
                    self.update_device_status(device_name, pokemon_go_status, False)  # Update UI to show GC service is not running
                    self.restart_gc_services(device_ip)  # Restart GC service for this device

                time.sleep(CHECK_INTERVAL)

                if current_device_index < total_devices:
                    time.sleep(CHECK_INTERVAL)

            # Add a delay between monitoring cycles
            self.log(f"Waiting for {CYCLE_DELAY} seconds before starting the next cycle...")
            time.sleep(CYCLE_DELAY)

if __name__ == "__main__":
    root = tk.Tk()
    app = DeviceMonitorApp(root)
    root.mainloop()
