import socket
import struct
import time
import pymem
import keyboard
import json
import logging
import threading
import ctypes
from typing import Optional, Tuple
from ctypes import wintypes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('emulator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration class
class Config:
    def __init__(self):
        self.host: str = '0.0.0.0'
        self.port: int = 65433
        self.process_name: str = 'ForzaHorizon5.exe'
        self.speed_offset: int = 305419896  # Updated from config
        self.steering_deadzone: float = 0.2
        self.steering_sensitivity: float = 2.0
        self.reconnect_timeout: float = 5.0
        self.max_reconnect_attempts: int = 3

    @classmethod
    def from_file(cls, filename: str = 'config.json') -> 'Config':
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                config = cls()
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                return config
        except FileNotFoundError:
            logger.warning(f"Config file {filename} not found, using defaults")
            return cls()
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {filename}, using defaults")
            return cls()

def check_dependencies() -> list[str]:
    """Check if required modules are installed."""
    required_modules = ['socket', 'struct', 'time', 'pymem', 'keyboard', 'json']
    missing = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    return missing

def initialize_game_process(process_name: str) -> Optional[pymem.Pymem]:
    """Initialize pymem and return game process handle."""
    try:
        pm = pymem.Pymem(process_name)
        logger.info("pymem initialized successfully")
        try:
            module = pymem.process.module_from_name(pm.process_handle, process_name).lpBaseOfDll
            logger.info("Game module accessed successfully")
            return pm
        except Exception as e:
            logger.error(f"Error accessing game module: {e}")
            return None
    except pymem.exception.ProcessNotFound:
        logger.error(f"{process_name} not found. Make sure the game is running")
        return None
    except Exception as e:
        logger.error(f"Error initializing pymem: {e}")
        return None

def create_socket(config: Config) -> Optional[socket.socket]:
    """Create and configure socket."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((config.host, config.port))
        s.listen()
        logger.info(f"Socket bound to {config.host}:{config.port} and listening")
        return s
    except Exception as e:
        logger.error(f"Error creating/binding socket: {e}")
        return None

# XInput structures for controller emulation
class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ('buttons', wintypes.WORD),
        ('left_trigger', wintypes.BYTE),
        ('right_trigger', wintypes.BYTE),
        ('l_thumb_x', wintypes.SHORT),
        ('l_thumb_y', wintypes.SHORT),
        ('r_thumb_x', wintypes.SHORT),
        ('r_thumb_y', wintypes.SHORT)
    ]

class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ('packet_number', wintypes.DWORD),
        ('gamepad', XINPUT_GAMEPAD)
    ]

xinput = ctypes.windll.xinput1_4

def handle_steering(rotation_x: float, config: Config, pm: pymem.Pymem) -> None:
    """Handle steering input with XInput emulation and memory writing."""
    steering_amount = rotation_x * config.steering_sensitivity
    
    # XInput emulation for steering
    try:
        state = XINPUT_STATE()
        state.gamepad.l_thumb_x = int(steering_amount * 32767)
        xinput.XInputSetState(0, ctypes.byref(state))
    except Exception as e:
        logger.error(f"XInput error: {e}")

    # XInput emulation
    state = XINPUT_STATE()
    state.gamepad.l_thumb_x = int(steering_amount * 32767)
    xinput.XInputSetState(0, ctypes.byref(state))
    logger.debug(f"XInput steering: {steering_amount}")

def process_data(data: bytes, config: Config, pm: pymem.Pymem) -> None:
    """Process received data and handle controller inputs."""
    try:
        # Debug log raw received bytes
        logger.debug(f"Raw received data: {data.hex(' ')}")
        
        if len(data) < 1:
            logger.warning("Received empty data")
            return

        if len(data) < 9:  # Need at least 1 byte command + 8 bytes steering data
            logger.warning(f"Received incomplete data, length={len(data)}")
            logger.debug(f"Partial data: {data.hex(' ')}")
            return

        # Handle acceleration/brake commands
        command = data[0]
        if command == ord('s'):
            logger.info("Received BRAKE command")
            keyboard.press('s')
            keyboard.release('w')
        elif command == ord('w'):
            logger.info("Received ACCELERATE command")
            keyboard.press('w')
            keyboard.release('s')
        elif command == ord('n'):
            logger.info("Received NEUTRAL command")
            keyboard.release('w')
            keyboard.release('s')

        # Process steering data (always present after command)
        rotation_x, rotation_y = struct.unpack('ff', data[1:9])
        logger.debug(f"Received steering data: rotation_x={rotation_x}, rotation_y={rotation_y}")
        handle_steering(rotation_x, config, pm)

    except struct.error as e:
        logger.error(f"Error unpacking data: {e}, data length={len(data)}")
    except Exception as e:
        logger.error(f"Error processing data: {e}")

def main():
    """Main function to run the controller emulator."""
    config = Config.from_file()
    logger.info("Starting Xbox 360 controller emulator")

    missing_modules = check_dependencies()
    if missing_modules:
        logger.error(f"Missing required modules: {', '.join(missing_modules)}")
        logger.error("Please install them using 'pip install <module>'")
        return

    pm = initialize_game_process(config.process_name)
    if not pm:
        return

    while True:
        s = create_socket(config)
        if not s:
            return

        reconnect_attempts = 0
        while reconnect_attempts < config.max_reconnect_attempts:
            try:
                conn, addr = s.accept()
                with conn:
                    logger.info(f"Connected by {addr}")
                    while True:
                        try:
                            data = conn.recv(1024)
                            if not data:
                                logger.info("Connection closed by client")
                                break
                            process_data(data, config, pm)
                            time.sleep(0.01)  # Prevent CPU overload
                        except socket.error as e:
                            logger.error(f"Socket error: {e}")
                            break
            except socket.error as e:
                logger.error(f"Error accepting connection: {e}")
                reconnect_attempts += 1
                if reconnect_attempts < config.max_reconnect_attempts:
                    logger.info(f"Reconnecting attempt {reconnect_attempts + 1}/{config.max_reconnect_attempts}")
                    time.sleep(config.reconnect_timeout)
                else:
                    logger.error("Max reconnection attempts reached")
                    break
        s.close()
        if reconnect_attempts >= config.max_reconnect_attempts:
            break

if __name__ == "__main__":
    try:
        # Release all keys on startup
        for key in ['w', 's', 'a', 'd']:
            keyboard.release(key)
        main()
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.error(f"Critical error: {e}")
    finally:
        # Clean up
        for key in ['w', 's', 'a', 'd']:
            keyboard.release(key)
        logger.info("Script terminated, all keys released")