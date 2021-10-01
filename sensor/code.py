import board
import busio
import json
import microcontroller
import rtc
import time

from adafruit_dht import DHT22
from analogio import AnalogIn
from neopixel import NeoPixel
from simpleio import DigitalOut

class Device:
    def __init__(self, battery_pin, sonar_pin, dht22_pin, led_pin, max_attempts=3):
        self.battery = AnalogIn(battery_pin)
        self.sonar = AnalogIn(sonar_pin)
        self.dht22 = DHT22(dht22_pin)
        self.led = NeoPixel(led_pin, 1, brightness=0.05)
        self.max_attempts = max_attempts

    def set_time(self, time):
        rtc.RTC().datetime = time

    def led_on(self, r, g, b):
        self.led.fill((r, g, b))

    def led_off(self):
        self.led.fill((0, 0, 0))

    def battery_voltage(self):
        return self.battery.value

    def sonar_voltage(self):
        return self.sonar.value

    def cpu_temperature(self):
        return round(microcontroller.cpu.temperature * 10) / 10

    def case_temperature(self, attempt=1):
        return self.__retry(self.dht22, "temperature") or 0.0

    def case_humidity(self):
        return self.__retry(self.dht22, "humidity") or 0.0

    def __retry(self, obj, method, attempt=1):
        if attempt > self.max_attempts:
            return None

        value = getattr(obj, method)
        print("[attempt %d] value=%s" % (attempt, value))

        if value == 0.0:
            time.sleep(1)
            return self.__retry(obj, method, attempt + 1)
        else:
            return value

class Radio:
    def __init__(self, tx_pin, rx_pin, reset_pin):
        self.sleeping = False
        self.uart = busio.UART(tx_pin, rx_pin, baudrate=115200, bits=8, parity=None, stop=1, timeout=10)
        self.lora_reset = DigitalOut(reset_pin)
        self.startup()

    def startup(self):
        self.reset()
        self.send_command("AT+FACTORY", "FACTORY")
        self.send_command("AT+NETWORKID=3")
        self.send_command("AT+ADDRESS=1")
        self.send_event("startup")

    def reset(self):
        print("Resetting radio...\n")
        self.lora_reset.value = False # active LOW
        time.sleep(1) # must stay set for at least 100ms
        self.lora_reset.value = True
        while True:
            response = self.get_response()

            if self.get_response() is None:
                print("Reset successful.\n")
                self.send_event("reset")
                return

    def sleep(self):
        self.sleeping = True

    def wake(self):
        self.sleeping = False

    def send_command(self, command, valid_responses=None):
        if valid_responses is None:
            valid_responses = ["+OK"]

        print("> {}".format(command))
        command_bytes = bytes(command + "\r\n", "ascii")
        self.uart.write(command_bytes)
        response = self.get_response()

        if response is None or not any(response.find(r) != -1 for r in valid_responses):
            print("[ERROR] received unexpected response: %s" % repr(response))
            self.reset()
            time.sleep(10)
            self.send_command(command)

    def get_response(self):
        data = self.uart.readline()

        if data is None:
            return None
        else:
            response = "".join([chr(b) for b in data])
            print("< {}".format(response))
            return response

    def send_data(self, data):
        if self.sleeping:
            self.send_command("AT+MODE=0", ["+OK", "+MODE=0", "+READY"]) # transmit and receive mode
            self.get_response()

        payload = json.dumps(data)
        self.send_command("AT+SEND=0,%s,%s" % (len(payload), payload), ["+OK", "+SEND"])

        if self.sleeping:
            self.send_command("AT+MODE=1", ["+OK", "+MODE=1", "+READY"]) # sleep mode

    def send_event(self, name, data=None):
        if data is None:
            data = {}

        data["event"] = name
        self.send_data(data)

    def send_telemetry(self, device):
        self.send_data({
            "event": "telemetry",
            "timestamp": time.time(),
            "battery_voltage": device.battery_voltage(),
            "sonar_voltage": device.sonar_voltage(),
            "cpu_temperature": device.cpu_temperature(),
            "case_temperature": device.case_temperature(),
            "case_humidity": device.case_humidity(),
        })

    def get_time(self):
        while True:
            self.send_data({"jsonrpc": "2.0", "method": "get_time"})
            response = self.get_response()
            if response is not None:
                break;
        [_from, _length, rest] = response.split(",", 2)
        [payload, _rssi, _snr] = rest.rsplit(",", 2)
        data = json.loads(payload)
        [year, month, day, hour, minute, second, day_of_week] = list(map(lambda value: int(value), data["result"].split("-")))
        return time.struct_time((year, month, day, hour, minute, second, day_of_week, -1, -1))

# ENTRYPOINT

counter = 0
triggered = False
triggered_for = 0

device = Device(battery_pin=board.A0, sonar_pin=board.A1, dht22_pin=board.D4, led_pin=board.NEOPIXEL)
device.led_on(0, 255, 0)

radio = Radio(board.TX, board.RX, board.D10)
device.set_time(radio.get_time())

radio.sleep()

while True:
    device.led_off()

    if triggered:
        if triggered_for > 60:
            triggered = False
            triggered_for = 0
        else:
            triggered_for += 1
    else:
        sonar_voltage = device.sonar_voltage()
        if (sonar_voltage / 1962) < 3.0:
            device.led_on(255, 0, 0)
            radio.send_event("triggered", {"sonar_voltage": sonar_voltage})
            triggered = True

    if counter >= 60 * 10:
        device.led_on(0, 0, 255)
        radio.send_telemetry(device)
        counter = 0
    else:
        counter += 1

    time.sleep(1)
