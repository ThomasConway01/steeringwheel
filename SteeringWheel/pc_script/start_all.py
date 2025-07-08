import subprocess
import time
import os

# Paths and process names
FORZA_EXECUTABLE = "ForzaHorizon5.exe"  # Adjust if needed based on your system
FORZA_PATH = "\"C:\\Program Files\\WindowsApps\\Microsoft.624F8B84B80_3.414.967.0_x64__8wekyb3d8bbwe\\ForzaHorizon5.exe\""  # Path for Microsoft Store installation, adjust if needed
FORZA_URI = "forza://launch"  # URI protocol to launch Forza Horizon 5 if direct path fails
SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pc_script.py")

def is_process_running(process_name):
    """Check if a process is running."""
    try:
        output = subprocess.check_output(['tasklist'], shell=True).decode()
        return process_name in output
    except Exception as e:
        print(f"Error checking process: {e}")
        return False

def start_process(executable_path, process_name, uri=None):
    """Start a process if it's not already running."""
    if not is_process_running(process_name):
        try:
            # Check if the executable path exists
            if not os.path.exists(executable_path.strip('"')):
                print(f"Error: The path to {process_name} does not exist: {executable_path}")
                print(f"Please update the FORZA_PATH in this script with the correct path to {process_name}.")
                if uri:
                    print(f"Attempting to launch via URI: {uri}")
                    subprocess.Popen(f"start {uri}", shell=True)
                    return True
                return False
            subprocess.Popen(executable_path, shell=True)
            print(f"Started {process_name}")
            return True
        except Exception as e:
            print(f"Error starting {process_name}: {e}")
            if uri:
                print(f"Attempting to launch via URI: {uri}")
                try:
                    subprocess.Popen(f"start {uri}", shell=True)
                    return True
                except Exception as uri_e:
                    print(f"Error launching via URI: {uri_e}")
                    return False
            return False
    else:
        print(f"{process_name} is already running")
        return True

def main():
    print("Starting all required components for SteeringWheel control...")
    
    # Start Forza Horizon 5
    if start_process(FORZA_PATH, FORZA_EXECUTABLE, FORZA_URI):
        print("Waiting for Forza Horizon 5 to fully launch...")
        time.sleep(10)  # Give time for Forza to start
    
    # Start the PC script for communication
    try:
        subprocess.Popen(["python", SCRIPT_PATH], shell=True)
        print("Started pc_script.py")
    except Exception as e:
        print(f"Error starting pc_script.py: {e}")
    
    print("All components started. Ensure your Android app is running and connected to the same network.")
    input("Press Enter to exit...")  # Keep the window open

if __name__ == "__main__":
    main()