import tkinter as tk
from PIL import Image, ImageTk
from tkinter import PhotoImage, scrolledtext
import threading
import subprocess
import time
import logging
from logging.handlers import RotatingFileHandler
import os
import queue

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(SCRIPT_DIR, "logo.png")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "devices.config")
LOGO_SIZE = (200, 200)
CHECK_INTERVAL = 5  # seconds between each device
CYCLE_DELAY = 30  # seconds, delay between monitoring cycles
LOG_FILE = "device_monitor.log"

# Configure logging
logging.basicConfig(handlers=[RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=2)],
                    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DeviceMonitorApp:
    logo_row = 1

    def __init__(self, root):
        self.root = root
        self.root.title("Rare's Device Monitor")
        self.devices, self.log_config = self.load_config(CONFIG_FILE)
        self.configure_logging()
        self.status_labels = {}
        self.setup_ui()
        self.monitoring_thread = threading.Thread(target=self.monitor_devices, args=(queue.Queue(),), daemon=True)
        self.monitoring_thread.start()

    def load_config(self, file_name):
        devices = {}
        log_config = {'LOG_PATH': 'logs/device_monitor.log',
                      'LOG_LEVEL': 'INFO',
                      'LOG_MAX_SIZE': 5 * 1024 * 1024,  # Default: 5 MB in bytes
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
            return devices, log_config
        except FileNotFoundError:
            self.log(f"Error: Configuration file '{file_name}' not found.")
            return {}, log_config

    def configure_logging(self):
        log_level = getattr(logging, self.log_config['LOG_LEVEL'].upper(), logging.INFO)

        log_dir = os.path.dirname(self.log_config['LOG_PATH'])
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        logging.basicConfig(handlers=[RotatingFileHandler(
            self.log_config['LOG_PATH'],
            maxBytes=int(self.log_config['LOG_MAX_SIZE']),
            backupCount=int(self.log_config['LOG_BACKUP_COUNT']))],
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s')

    def reset_adb_server(self):
        self.log("Resetting ADB server...")
        self.run_adb_command("adb kill-server")
        self.run_adb_command("adb start-server")

        for _, ip in self.devices.items():
            connect_cmd = f"adb connect {ip}"
            connect_result = self.run_adb_command(connect_cmd)
            self.log(f"Connected to {ip}: {connect_result}")

    def setup_ui(self):
        self.root.configure(bg="#333333")
        self.add_logo(LOGO_PATH, LOGO_SIZE)
        title_label = tk.Label(self.root, text="Rare's Device Monitor", font=("Helvetica", 16), fg="white", bg="#333333")
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
        # Force close Pokemon Go and restart GC
        command1 = f"adb -s {device_ip} shell am force-stop com.nianticlabs.pokemongo"
        command2 = f"adb -s {device_ip} shell am start -n com.gocheats.launcher/com.gocheats.launcher.MainActivity"

        self.run_adb_command(command1)
        time.sleep(5)  # Add a delay to ensure processes are terminated before starting GC
        self.run_adb_command(command2)

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

    def run_adb_command(self, command):
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return result.stdout.strip()
        except subprocess.SubprocessError as e:
            self.log(f"Error running command '{command}': {e}")
            return None

    def check_package_status(self, device_ip, package_name):
        command = f"adb -s {device_ip} shell pm list packages {package_name}"
        result = self.run_adb_command(command)
        return result == f"package:{package_name}"

    def check_gc_service_status(self, device_ip, timeout=10):
        # Check if the GC service is actively updating by examining the logcat output
        logcat_command = f"adb -s {device_ip} logcat -d -s Exeggcute"
        
        try:
            # Run the logcat command and capture the output
            result = subprocess.run(logcat_command, shell=True, capture_output=True, text=True, timeout=timeout)
            logcat_output = result.stdout.strip()
            
            # Check if the logcat output contains any new lines, indicating activity
            if logcat_output:
                return True  # Service is actively updating
            else:
                return False  # Service appears frozen
        except subprocess.TimeoutExpired:
            # If the logcat command times out, consider it as service frozen
            return False

    def monitor_devices(self, device_queue):
        while True:
            self.reset_adb_server()  # Reset ADB server before each cycle

            total_devices = len(self.devices)
            current_device_index = 0

            for device_name, device_ip in self.devices.items():
                current_device_index += 1
                self.log(f"Device {current_device_index}/{total_devices}: Checking {device_name} - {device_ip}")

                # Perform the device status check here
                pokemon_go_status = self.check_package_status(device_ip, "com.nianticlabs.pokemongo")
                gocheats_status = self.check_package_status(device_ip, "com.gocheats.launcher")

                # Check GC service status
                gc_status = self.check_gc_service_status(device_ip, timeout=10)  # Adjust timeout as needed

                # Provide appropriate verbose log messages based on the status check
                if pokemon_go_status or gocheats_status:
                    self.log(f"Pokemon Go & GC Service Running on {device_name}")
                else:
                    if gc_status:
                        self.log(f"Pokemon Go & GC Service Appears Frozen on {device_name}, Restarting Services...")
                    else:
                        self.log(f"Pokemon Go & GC Service Not Running on {device_name}, Restarting Services...")
                    self.auto_restart_services(device_ip)

                # Update the status of the device in the UI
                self.update_device_status(device_name, pokemon_go_status, gc_status)

                time.sleep(CHECK_INTERVAL)

                # Add a delay at the end of each device check
                if current_device_index < total_devices:
                    time.sleep(CHECK_INTERVAL)

            # Add a delay between monitoring cycles
            self.log(f"Waiting for {CYCLE_DELAY} seconds before starting the next cycle...")
            time.sleep(CYCLE_DELAY)

if __name__ == "__main__":
    root = tk.Tk()
    app = DeviceMonitorApp(root)
    root.mainloop()
