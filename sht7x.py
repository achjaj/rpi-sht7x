import RPi.GPIO as gpio
from time import sleep

# constants
TEMP = 3          # 000 00011
HUM = 5           # 000 00101

FLG_HEATER = 4    # 00000100
FLG_NO_OTP = 2    # 00000010
FLG_LOWER_RES = 1 # 00000001

CRC_TABLE = [
    0, 49, 98, 83, 196, 245, 166, 151, 185, 136, 219, 234, 125, 76, 31, 46 , 67,
    114, 33, 16, 135, 182, 229, 212, 250, 203, 152, 169, 62, 15, 92, 109 , 134,
    183, 228, 213, 66, 115, 32, 17, 63, 14, 93, 108, 251, 202, 153, 168 , 197,
    244, 167, 150, 1, 48, 99, 82, 124, 77, 30, 47, 184, 137, 218, 235 , 61, 12,
    95, 110, 249, 200, 155, 170, 132, 181, 230, 215, 64, 113, 34, 19 , 126, 79,
    28, 45, 186, 139, 216, 233, 199, 246, 165, 148, 3, 50, 97, 80 , 187, 138,
    217, 232, 127, 78, 29, 44, 2, 51, 96, 81, 198, 247, 164, 149 , 248, 201,
    154, 171, 60, 13, 94, 111, 65, 112, 35, 18, 133, 180, 231, 214 , 122, 75,
    24, 41, 190, 143, 220, 237, 195, 242, 161, 144, 7, 54, 101, 84 , 57, 8, 91,
    106, 253, 204, 159, 174, 128, 177, 226, 211, 68, 117, 38, 23 , 252, 205,
    158, 175, 56, 9, 90, 107, 69, 116, 39, 22, 129, 176, 227, 210 , 191, 142,
    221, 236, 123, 74, 25, 40, 6, 55, 100, 85, 194, 243, 160, 145 , 71, 118, 37,
    20, 131, 178, 225, 208, 254, 207, 156, 173, 58, 11, 88, 105 , 4, 53, 102,
    87, 192, 241, 162, 147, 189, 140, 223, 238, 121, 72, 27, 42 , 193, 240, 163,
    146, 5, 52, 103, 86, 120, 73, 26, 43, 188, 141, 222, 239 , 130, 179, 224,
    209, 70, 119, 36, 21, 59, 10, 89, 104, 255, 206, 157, 172]

# class
class SHT7x:
    def __init__(self, sck, data, delay_us = 210, voltage = 3.5, d1 = None):
        self.sck_pin = sck
        self.data_pin = data
        self.delay = delay_us / 1e6
        self.lower_res = False
        self.crc_reg = 0        # assumes that the status register of the sensor was not modified

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

    def update_crc_reg(self, byte):
        x = self.crc_reg ^ byte
        self.crc_reg = CRC_TABLE[x]

    def check_crc(self, received_crc):
        if self.reverse(self.crc_reg) != received_crc:
            raise Exception("CRC error: try comunication reset")

    def reverse(self, byte):
        return int('{:08b}'.format(byte)[::-1], 2)

    # TODO: cmd send?
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

        if ack != 0:
            raise Exception("Data send ACK error")
        
        self.update_crc_reg(byte)

    def send_cmd(self, cmd):
        self.start()
        self.dly(2)
        self.send_byte(cmd)

    def read_response(self):
        self.sck(0)

        msb = self.read_byte()
        self.update_crc_reg(msb)
        lsb = self.read_byte()
        self.update_crc_reg(lsb)

        value = (msb << 8) + lsb

        crc = self.read_byte(comm_end = True)
        self.sck(0)
        self.check_crc(crc)

        return value

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
        register, crc = self.read_byte(), self.read_byte(comm_end = True)
        self.sck(0)
        self.check_crc(crc)

        return register

    def write_status_register(self, bits):
        self.send_cmd(6) # cmd 000 00110
        self.dly(2)
        self.switch_data(gpio.OUT)
        self.send_byte(bits)

        self.crc_reg = (bits & 0b1111) << 4

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