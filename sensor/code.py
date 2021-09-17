import board
import busio
import json
import microcontroller
import neopixel
import rtc
import time

from analogio import AnalogIn
from simpleio import DigitalOut

led = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.05)
uart = busio.UART(board.TX, board.RX, baudrate=115200, bits=8, parity=None, stop=1, timeout=10)
battery = AnalogIn(board.A0)
sonar = AnalogIn(board.A1)
lora_reset = DigitalOut(board.D10)

def cpu_temp():
    return round(microcontroller.cpu.temperature * 10) / 10

def battery_voltage():
    return battery.value

def sonar_voltage():
    return sonar.value

def led_on():
    led.fill((255, 0, 0))

def led_off():
    led.fill((0, 0, 0))

def reset_lora():
    print("Resetting LoRa...\n")
    lora_reset.value = False # active LOW
    time.sleep(1) # must stay set for at least 100ms
    lora_reset.value = True
    while True:
        response = get_response()
        print("reset response: %s" % repr(response))

        if get_response() is None:
            print("reset successful.")
            send_data({"event": "reset"})
            return

def send_command(command, expected_response="OK"):
    print("> {}".format(command))
    command_bytes = bytes(command + "\r\n", "ascii")
    uart.write(command_bytes)
    response = get_response()

    print("< {}".format(response))

    if not response.endswith("+{}\r\n".format(expected_response)):
        print("[ERROR] received unexpected response: %s" % repr(response))
        reset_lora()
        time.sleep(10)
        send_command(command)

def get_response():
    data = uart.readline()

    if data is None:
        return None
    else:
        return "".join([chr(b) for b in data])

def send_data(data):
    payload = json.dumps(data)
#    send_command("AT+MODE=0") # transmit and receive mode
    send_command("AT+SEND=0,%s,%s" % (len(payload), payload))
#    send_command("AT+MODE=1") # sleep mode

def send_telemetry():
    send_data({
        "event": "telemetry",
        "timestamp": time.time(),
        "battery_voltage": battery_voltage(),
        "sonar_voltage": sonar_voltage(),
        "cpu_temperature": cpu_temp()
    })

def setup_uart():
    reset_lora()
    send_command("AT+FACTORY", "FACTORY")
    send_command("AT+NETWORKID=3")
    send_command("AT+ADDRESS=1")
    send_data({"event": "startup"})
    set_clock()

def set_clock():
    while True:
        send_data({"jsonrpc": "2.0", "method": "get_time"})
        response = get_response()
        if response is not None:
            break;
    [_from, _length, rest] = response.split(",", 2)
    [payload, _rssi, _snr] = rest.rsplit(",", 2)
    data = json.loads(payload)
    [year, month, day, hour, minute, second, day_of_week] = list(map(lambda value: int(value), data["result"].split("-")))
    rtc.RTC().datetime = time.struct_time((year, month, day, hour, minute, second, day_of_week, -1, -1))

# ENTRYPOINT

setup_uart()
while True:
    led_on()
    send_telemetry()
    led_off()
    time.sleep(10)
