import RPi.GPIO as gpio
from time import sleep

# constants
TEMP = 3          # 000 00011
HUM = 5           # 000 00101

FLG_HEATER = 4    # 00000100
FLG_NO_OTP = 2    # 00000010
FLG_LOWER_RES = 1 # 00000001

# class
class SHT7x:
    def __init__(self, sck, data, delay_us = 210, voltage = 3.5, d1 = None):
        self.sck_pin = sck
        self.data_pin = data
        self.delay = delay_us / 1e6
        self.lower_res = False
        self.crc_reg = 0

        if d1 is None:
            match voltage:
                case 5:
                    self.d1 = -40.1
                case 4:
                    self.d1 = -39.8
                case 3.5:
                    self.d1 = -39.7
                case 3:
                    self.d1 = -39.6
                case 2.5:
                    self.d1 = -38.9
                case _:
                    raise Exception("Only supported voltages are 5V, 4V, 3.5V, 3V, 2.5V (see the datasheet). Consider passing d1 directly instead.")
        else:
            self.d1 = d1

        gpio.setup(sck, gpio.OUT)
        gpio.setup(data, gpio.OUT)

        self.sck(0)
        self.data(1)


    def sck(self, v):
        gpio.output(self.sck_pin, v)

    def sckPulse(self):
        self.sck(1)
        self.dly()
        self.sck(0)
        self.dly()

    def data(self, v):
        gpio.output(self.data_pin, v)

    def switch_data(self, direction):
        gpio.cleanup(self.data_pin)
        gpio.setup(self.data_pin, direction)

    def r_data(self):
        return gpio.input(self.data_pin)

    def data_ack(self, comm_end = False):
        self.switch_data(gpio.OUT)
        self.data(1) if comm_end else self.data(0)
        self.dly(0.5)
        self.sckPulse()
        self.switch_data(gpio.IN)

    def dly(self, mul = 1):
        sleep(self.delay * mul)

    def comm_reset(self):
        self.data(1)
        for i in range(9):
            self.sckPulse()

    def read_byte(self, comm_end = False):
        v = 0
        for i in range(8):
            v = 2*v + self.r_data()
            self.sckPulse()
            self.dly(0.5)

        self.dly()
        self.data_ack(comm_end)
        return v


    def start(self):
        self.switch_data(gpio.OUT)
        self.data(1)

        self.sck(1)
        self.dly()
        self.data(0)
        self.dly()

        self.sck(0)
        self.dly()
        self.sck(1)
        self.dly()
        self.data(1)
        self.dly()
        self.sck(0)

    def send_byte(self, byte):
        mask = 128
        for i in range(8):
            self.data(byte & mask)
            self.dly(0.5)
            self.sckPulse()
            mask = mask >> 1

        self.switch_data(gpio.IN)
        self.sck(1)
        self.dly(0.5)
        ack = self.r_data()
        self.sck(0)

        if not (ack == 0):
            raise Exception("Data send ACK error")

    def send_cmd(self, cmd):
        self.start()
        self.dly(2)
        self.send_byte(cmd)

    def read_response(self):
        self.sck(0)

        msb = self.read_byte()
        lsb = self.read_byte()

        value = (msb << 8) + lsb

        crc = self.read_byte(comm_end = True)
        self.sck(0)
        return value, crc

    def wait_for_measurement(self):
        self.switch_data(gpio.IN)

        for i in range(320):
            sleep(1e-3) # wait one ms
            if self.r_data() == 0:
                return

        raise Exception("Measurement timeout")


    def read_status_register(self):
        self.sendcmd(7) # cmd 000 00111
        self.dly()
        # TODO: perform CRC check
        register, crc = self.read_byte(), self.read_byte(comm_end = True)
        self.sck(0)
        return register, crc

    def write_status_register(self, bits):
        self.send_cmd(6) # cmd 000 00110
        self.dly(2)
        self.switch_data(gpio.OUT)
        self.send_byte(bits)

    def set_flags_on(self, flags):
        self.write_status_register(flags)
        self.lower_res = (flags & 1 == 1)

    def measure(self, cmd, temp_correction = False):
        self.send_cmd(cmd)
        self.wait_for_measurement()
        raw, crc = self.read_response()
        if cmd == TEMP:
            return (0.04 if self.lower_res else 0.01)*raw + self.d1

        if cmd == HUM:
            rh_lin = -2.0468 + (0.5872 if self.lower_res else 0.0367)*raw + (-4.0845e-4 if self.lower_res else -1.5955e-6)*(raw**2)

            if temp_correction:
                self.dly(3)
                return (self.read_measurement(TEMP, self.lower_res) - 25)*(0.01 + (0.00128 if self.lower_res else 0.00008)*raw) + rh_lin

            return rh_lin



gpio.setmode(gpio.BCM)

sht = SHT7x(17, 27)
while True:
    print(sht.measure(HUM))
    sleep(1)

gpio.cleanup()
