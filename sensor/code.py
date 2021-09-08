import board
import busio
import microcontroller
import neopixel
import time

from analogio import AnalogIn

led = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.05)
uart = busio.UART(board.TX, board.RX, baudrate=115200, bits=8, parity=None, stop=1, timeout=60)
a0 = AnalogIn(board.A0)
a1 = AnalogIn(board.A1)

def read_cpu_temp():
    return microcontroller.cpu.temperature

def read_voltage():
    return a0.value / 9773

def read_break_sensor():
    return a1.value < 32768

def led_on():
    led.fill((255, 0, 0))

def led_off():
    led.fill((0, 0, 0))

def read_response():
    while True:
        data = uart.readline()

        if data is not None:
            print(''.join([chr(b) for b in data]), end="")
            break

def setup_uart():
    uart.write(b'AT+FACTORY\r\n')
    time.sleep(0.1)
    read_response()

    uart.write(b'AT+NETWORKID=3\r\n')
    time.sleep(0.5)
    read_response()

    uart.write(b'AT+ADDRESS=1\r\n')
    time.sleep(0.5)
    read_response()

def send_data(message):
    print("AT+MODE=0")
    uart.write(b"AT+MODE=0\r\n")
    time.sleep(0.5)
    read_response()

    print("AT+SEND")
    uart.write(b"AT+SEND=0,%s,%s\r\n" % (len(message), message))
    time.sleep(0.5)
    read_response()

    print("AT+MODE=1")
    uart.write(b"AT+MODE=1\r\n")
    time.sleep(0.5)
    read_response()
    print("\n")

def send_telemetry():
    send_data("{}:{}:{}".format(time.time(), read_voltage(), read_cpu_temp()))

def send_break_message():
    send_data("{}:BREAK".format(time.time()))

def send_repair_message():
    send_data("{}:REPAIR".format(time.time()))

# setup
led_off()
setup_uart()
index = 0
break_message_sent = False
repair_message_sent = False

# loop
while True:
    if read_break_sensor():
        led_on()
        repair_message_sent = False
        if not break_message_sent:
            send_break_message()
            break_message_sent = True
    else:
        led_off()
        break_message_sent = False
        if not repair_message_sent:
            send_repair_message()
            repair_message_sent = True

    if index >= (30 * 10):
        send_telemetry()
        index = 0

    index += 1
    time.sleep(0.1)
