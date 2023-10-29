# rpi-sht7x
Raspberry Pi python "driver" for SHT7x temperature and humidity sensors. 

## This library is under heavy development!

## Implemented features
 - Read temperature
 - Read humidity
 - Write to the status register:
    * Turn on/off the on-chip heater
    * Turn on/off the reload from OTP
    * Switch between higher and lower resolution
 - The CRC is an optional feature according to the datasheet, but this library always checks the CRC checksum

## Requirements
 - Python 3.10+
 - RPi.GPIO library

## Usage
```python
# First, import the RPi.GPIO library and rpi-sht7x
import RPI.GPIO as gpio
from sht7x import *

# Setup RPi.GPIO
gpio.setmode(gpio.BCM)

# Create SHT7x object
# in this example, the SCK pin is 17, and SDA is 27
# these pins are physically close together on the RPi board
# creating the object like this assumes that the sensor is 
# powered by 3.5V (see datasheet)
sht = SHT7x(17, 27)

# Measure
temp = sht.measure(TEMP)
hum = sht.measure(HUM)

print("Temperature: {} °C".format(temp))
print("Relative Humidity: {} %".format(hum))

# Measure humidity with temperature correction
c_hum = sht.measure(HUM, temp_correction = True)
print("Relative Humidity (corrected): {} %".format(c_hum))

# Switch to the lower resolution
sht.set_flags_on(FLG_LOWER_RES)

# Switch back to higher resolution and turn on the heater
sht.set_flags_on(FLG_HEATER)

# Switch to lower resolution and turn on the heating at 
# the same time
sht.set_flags_on(FLG_LOWER_RES | FLG_HEATER)

# Check the actual value of the status register
sr = sht.read_status_register()
print("Status register:", bin(sr)) # expected output: 0b101

# This line decodes from the status register if the lower 
# resolution is used
lr = sr & FLG_LOWER_RES == FLG_LOWER_RES
print("Using lower resolution: ", lr) # True

# This line decodes from the status register if the heater # is turned on
heater = sr & FLG_HEATER == FLG_HEATER
print("Heater on:", heater) # True

# Reset the flags to the default state
sht.set_flags_on(0)

# DO NOT FORGET TO CLEAN AFTER YOURSELF :D
gpio.cleanup()
```

## Reference
This section describes all the important functions, classes and constants. The backbone of the library is the `SHT7x` class. It contains a lot of functions, but only the ones that are meant to be used by you, the user, are listed here. 

#### Constants
- `TEMP`
    * Value: `3 (0b000'00011)`
    * This is the command byte that tells the sensor 
    to measure temperature. You should only use it 
    as an argument to the `measure` function 
    described below.
- `HUM`
    * Value: `5 (0b000'00101)`
    * This is the command byte that tells the sensor 
    to measure relative humidity. You should only 
    use it as an argument to the `measure` function 
    described below.

 - `FLG_HEATER`
    * Value: `4 (0b00000100)`
    * Flag to turn the heater on. You should only 
    use it with the `set_flags_on` function 
    described below.

 - `FLG_NO_OTP`
    * Value: `2 (0b00000010)`
    * Flag to turn off the loading from OTP (see 
    datasheet). You should only 
    use it with the `set_flags_on` function 
    described below.

 - `FLG_LOWER_RES`
    * Value: `1 (0b00000001)`
    * Flag to switch to lower resolution. You should 
    only use it with the `set_flags_on` function 
    described below.

#### Classes
 - `SHT7x(sck, data, voltage = 3.5, d1 = None)`
    * **Backbone class used to communicate with 
    SHT7x sensor.**
    * `sck`: Pin number used for clock
    * `data`: Pin number used for data
    * `voltage`: The value of the supply voltage 
    used. The value is used to specify the value of 
    the `d1` constant (see the datasheet).
    * `d1`: Alternatively, the value of the `d1` 
    constant can be specified directly in the case 
    you are using different supply voltage and know 
    better value for the constant.

#### Functions
 - `measure(cmd, temp_correction = False)`
    * **Perform the measurement and return the 
    measured value**
    * `cmd`: What should be measured. Use `TEMP` or 
    `HUM` constants
    * `temp_correction`: Specify if the measured 
    relativity should be temperature-corrected. If 
    so, an additional temperature measurement is 
    performed right after the humidity measurement.

- `set_flags_on(flags)`
    * **Set the flags of the status register**
    * `flags`: Flags that should be modified. Use 
    the defined `FLG_*` constants.

- `read_status_register()`
    * **Read and return the value of the status 
    register as integer**

- `comm_reset()`
    * **Resets the communication**
    * Call this function when you encounter 
    CRC error.
    * See the datasheet for more information