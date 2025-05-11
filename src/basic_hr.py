import time
from machine import Pin, ADC, I2C, UART, Timer, PWM
from ssd1306 import SSD1306_I2C
from fifo import Fifo
from led import Led
from piotimer import Piotimer

import micropython
micropython.alloc_emergency_exception_buf(200)

#from mainmenu import main_menu

class Basic_hr():
    def __init__(self, pin_num, sample_rate, btn_pin):
        self.pin_num = ADC(pin_num)
        self.samples = Fifo(500)
        self.sample_index = 0
        self.ppi = []

        self.prev_value = 0
        self.in_peak_area = False
        self.peak_found = False


        self.sample_rate = sample_rate
        self.tmr = Piotimer(mode = Piotimer.PERIODIC, freq = sample_rate, callback = self.sensor_handler)

        #Screen
        self.WIDTH, self.HEIGHT = 128, 64
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.oled = SSD1306_I2C(self.WIDTH, self.HEIGHT, self.i2c)

        self.x_pos = 0
        self.y_pos = self.HEIGHT // 2
        self.prev_y_pos = 0
        self.scaled_value = 0

        #Values used in process func
        self.max_value = 0
        self.min_value = 0
        self.h = 0
        self.th = 0

        self.current_hr = 0
        self.signal = 0
        self.seconds = 60000

        self.hr_values = []


        #Return button
        self.btn = Pin(btn_pin, mode = Pin.IN, pull = Pin.PULL_UP)
        self.prev_btn_state = 1
        

    #Handler - read signal
    def sensor_handler(self, tid):
        try:
            self.signal = self.pin_num.read_u16()
            #if 25000 < self.signal < 35000:
            self.samples.put(self.signal)
        except:
            pass

    def main_process(self):
        self.threshold()
        self.sample_index += 1


        if not self.in_peak_area:
            if self.signal > self.th:
                self.in_peak_area = True
        else:
            if self.prev_value > self.signal and not self.peak_found:
                ppi_in_samples = self.sample_index - 1
                ppi_in_ms = ppi_in_samples * 4

                # Hyväksytään vain jos PPI on tarpeeksi pitkä
                if ppi_in_ms > 500:
                    hr = int(self.seconds / ppi_in_ms)

                    # Tasoitus: keskiarvo 10 viimeisestä HR-arvosta
                    self.hr_values.append(hr)
                    if len(self.hr_values) > 10:
                        self.hr_values.pop(0)
                    self.current_hr = sum(self.hr_values) // len(self.hr_values)

                    self.peak_found = True

                    # Näytetään HR jos se on järkevällä alueella
                    if 30 <= self.current_hr <= 240:
                        self.ppi.append(ppi_in_ms)
                        print(f"Current HR: {self.current_hr}")
                        self.oled.fill_rect(0, 0, 80, 10, 0)
                        self.oled.text(str(f"BPM: {self.current_hr}"), 0, 0)

                    self.sample_index = 0

            if self.signal < self.th:
                self.in_peak_area = False
                self.peak_found = False

        self.prev_value = self.signal

        if self.sample_index % 10 == 0:
            self.screen(self.signal)

    def threshold(self):
        self.min_value = min(self.samples.data)
        self.max_value = max(self.samples.data)
        self.h = self.max_value - self.min_value
        self.th = int(self.min_value + 0.85 * self.h)


    #Draw on the display
    def screen(self, signal):
        self.scaled_value = int((self.signal - self.min_value) / (self.max_value - self.min_value) * 64)
        inverted_y_pos = self.HEIGHT - self.scaled_value

        if self.x_pos >= self.WIDTH:
            self.oled.fill(0)
            self.x_pos = 0

        self.oled.line(self.x_pos-1, self.prev_y_pos, self.x_pos, inverted_y_pos, 1)
        self.prev_y_pos = inverted_y_pos
        self.x_pos += 1
        self.oled.show()

    def run(self):
        while True:
            if not self.samples.empty():
                self.signal = self.samples.get()
                self.main_process(self.signal)

            #Return to menu
            current_state = self.btn.value()
            if self.prev_btn_state == 1 and current_state == 0:
                time.sleep_ms(100)
                if self.btn.value() == 0:
                    print("Returning to menu")
                    return

def main_basic_hr():
    pin_num = 27
    sample_rate = 250
    btn_pin_num = 12
    program = Basic_hr(pin_num, sample_rate, btn_pin_num)
    program.run()

#main_basic_hr()


