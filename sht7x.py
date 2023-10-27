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

    def in_use(self, only):
        return [self.data_pin[i] for i in only] if only else self.data_pin
    
    def in_use_len(self, only):
        return len(only) if only else len(self.data_pin)

    def sck(self, v):
        gpio.output(self.sck_pin, v)

    def sckPulse(self):
        self.sck(1)
        self.dly()
        self.sck(0)
        self.dly()

    def data(self, v, only):
        gpio.output(self.in_use(only), v)

    def switch_data(self, direction, only):
        gpio.cleanup(self.in_use(only))
        gpio.setup(self.in_use(only), direction)

    def r_data(self, only):
        bits = []
        for pin in self.in_use(only):
            bits.append(gpio.input(pin))

        return bits

    def data_ack(self, only, comm_end = False):
        self.switch_data(gpio.OUT, only)
        self.data(1, only) if comm_end else self.data(0, only)
        self.dly(0.5)
        self.sckPulse()
        self.switch_data(gpio.IN, only)

    def dly(self, mul = 1):
        sleep(self.delay * mul)

    def comm_reset(self, only = None):
        self.data(1, only)
        for i in range(9):
            self.sckPulse()

    def read_byte(self, only, comm_end = False):
        v = [0] * self.in_use_len(only)
        for i in range(8):
            for j, bit in enumerate(self.r_data(only)):
                v[j] = 2*v[j] + bit
            self.sckPulse()
            self.dly(0.5)

        self.dly()
        self.data_ack(only, comm_end)
        return v


    def start(self, only):
        self.switch_data(gpio.OUT, only)
        self.data(1, only)

        self.sck(1)
        self.dly()
        self.data(0, only)
        self.dly()

        self.sck(0)
        self.dly()
        self.sck(1)
        self.dly()
        self.data(1, only)
        self.dly()
        self.sck(0)

    def send_byte(self, byte, only):
        mask = 128
        for i in range(8):
            self.data(byte & mask, only)
            self.dly(0.5)
            self.sckPulse()
            mask = mask >> 1

        self.switch_data(gpio.IN, only)
        self.sck(1)
        self.dly(0.5)
        ack = self.r_data(only)
        self.sck(0)

        if not (ack == [0] * self.in_use_len(only)):
            raise Warning("Data send ACK error in one device: {}".format(ack))

    def send_cmd(self, cmd, only):
        self.start(only)
        self.dly(2)
        self.send_byte(cmd, only)

    def read_response(self, only):
        self.sck(0)

        msb = self.read_byte(only)
        lsb = self.read_byte(only)

        value = [0] * self.in_use_len(only)
        for i, m in enumerate(msb):
            value[i] = (m << 8) + lsb[i]

        crc = self.read_byte(only, comm_end = True)
        self.sck(0)
        return value, crc

    def wait_for_measurement(self, only):
        self.switch_data(gpio.IN, only)

        for i in range(320):
            sleep(1e-3) # wait one ms
            if self.r_data(only) == [0] * self.in_use_len(only):
                return

        raise Exception("Measurement timeout")


    def read_status_register(self, only = None):
        self.send_cmd(7, only) # cmd 000 00111
        self.dly()
        # TODO: perform CRC check
        register, crc = self.read_byte(only), self.read_byte(only, comm_end = True)
        self.sck(0)
        return register, crc

    def write_status_register(self, bits, only = None):
        self.send_cmd(6, only) # cmd 000 00110
        self.dly(2)
        self.switch_data(gpio.OUT, only)
        self.send_byte(bits, only)

    def set_flags_on(self, flags, only = None):
        self.write_status_register(flags, only)
        if flags & 1 == 1:
            if only:
                for i in only:
                    self.lower_res[i] = True
            else:
                self.lower_res = [True]*len(self.data_pin)

    def measure(self, cmd, temp_correction = False, only = None):
        self.send_cmd(cmd, only)
        self.wait_for_measurement(only)
        raw, crc = self.read_response(only)

        result_len = self.in_use_len(only)
        result = [0] * result_len
        if cmd == TEMP:
            for i, r in enumerate(raw):
                result[i] = (0.04 if self.lower_res[i] else 0.01)*r + self.d1 # WARNING: NOT CORRECT! self.lower_res[i]

        if cmd == HUM:
            rh_lin = [0] * result_len
            for i, r in enumerate(raw):
                rh_lin[i] = -2.0468 + (0.5872 if self.lower_res else 0.0367)*r + (-4.0845e-4 if self.lower_res else -1.5955e-6)*(r**2)
            
            result = rh_lin
            if temp_correction:
                self.dly(3)
                result = (self.read_measurement(TEMP, self.lower_res, only = only) - 25)*(0.01 + (0.00128 if self.lower_res else 0.00008)*raw) + rh_lin

        return result


if __name__ == "__main__":
    gpio.setmode(gpio.BCM)
    sht = SHT7x(17, [27, 22])
    print(sht.measure(TEMP))

    gpio.cleanup()
