from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
from filefifo import Filefifo
from fifo import Fifo
import time
from piotimer import Piotimer

#1
#from sensor import main_sensor #option 1
from basic_hr import main_basic_hr #option 1

#2
#from basichrv import main_basichrv #option 2
from basichrv import main_basichrv #option 2

#3
#from kubios import main_kubios #option 3
from kubios import main_kubios #option 3


import micropython
micropython.alloc_emergency_exception_buf(200)

#screen
WIDTH, HEIGHT = 128, 64
i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
oled = SSD1306_I2C(WIDTH, HEIGHT, i2c)

class Encoder:
    def __init__(self, rot_a, rot_b, btn_pin):
        self.a = Pin(rot_a, mode = Pin.IN, pull = Pin.PULL_UP)
        self.b = Pin(rot_b, mode = Pin.IN, pull = Pin.PULL_UP)
        self.btn = Pin(btn_pin, mode = Pin.IN, pull = Pin.PULL_UP)
        self.fifo = Fifo(30, typecode = 'i')
        self.position = 0
        self.a.irq(handler = self.handler, trigger = Pin.IRQ_RISING, hard = True)
        self.last_button_state = 1
        

    #Handler uses fifo
    def handler(self, pin):
        try:
                #if self.b.value():
            if self.b.value():
                self.fifo.put(-1)
            else:
                self.fifo.put(1)
        except:
            pass

class Menu_Screen():
    def __init__(self, encoder):
        self.encoder = encoder    # Well get this from Encoder class when we define 
        #self.selected_option = 0
        #remove the "-" later on
        self.menu_options = [
            "-1. Measure HR",
            "-2. Basic HRV",
            "-3. Kubios",
            "-4. History",]
        
        self.main_menu_state = 0	# 0-3
        self.last_button_state = 1
        
        
        oled.fill(0)
        oled.show()
            
    def first_page(self):
        oled.fill(0) # clear
        for (index, value) in enumerate(self.menu_options):
            # > in front if chosen
            #if index == self.selected_option:
            if index == self.main_menu_state:
                oled.text(">" + value, 0, (10 + index * 10) + 2, 1) # the last 1 might actually be useless
            #- in front
            else:
                oled.text("-" + value, 0, (10 + index * 10) + 2, 1)
        
        oled.show()
        
        
    def choosing_option(self):
        self.first_page()
        if self.encoder.fifo.has_data():
            direction = self.encoder.fifo.get()
            
            
            #My version - Dont work
            #Options 0-1
            #if direction == 1 and self.main_menu_state <3:
                #time.sleep(0.5)
            #    self.main_menu_state += 1
            #    print(self.main_menu_state)
            
            #When youre at 3, u wanna go back to 0
            #if direction == 1 and self.main_menu_state == 3:
                #time.sleep(0.5)
            #    self.main_menu_state = 0  # back to one
            #    print(self.main_menu_state)
                
            #if direction == -1 and self.main_menu_state > 1:
                #time.sleep(0.5)
            #    self.main_menu_state -= 1
            #    print(self.main_menu_state)
            
            #if direction == -1 and self.main_menu_state == 0:
                #time.sleep(0.5)
            #    self.main_menu_state = 3  #Go 3 coz we went -1 on 0
            #    print(self.main_menu_state)
            

            #Prevents from going below or above max/min options on menu
            self.main_menu_state += direction
            
            if self.main_menu_state > 3:
                self.main_menu_state = 0
            elif self.main_menu_state < 0:
                self.main_menu_state = 3
                
            print(f"Current state/level: {self.main_menu_state}")
            self.first_page()
            
        #Clears the junk
        while self.encoder.fifo.has_data():
            discarded_trash = self.encoder.fifo.get()
            #print("junk: ", discarded_trash) #some unnecessary trash / noise we dont need - verified

        
        #Button pressed
        current_state = self.encoder.btn.value()
        if self.encoder.last_button_state == 1 and current_state == 0:
            print("button pressed test")
            self.button_clicked()
        self.encoder.last_button_state = current_state
            
            
            
                
    def button_clicked(self):
        #Measure HR page
        if self.main_menu_state == 0:
            main_basic_hr()
                
        if self.main_menu_state == 1:
            main_basichrv()
            #pass
            
        if self.main_menu_state == 2:
            main_kubios()
        #Another yet to do function or page here
            #pass #pass #for now
        if self.main_menu_state == 3:
            pass #also pass now
            
        #Then just from somewhere import something.. when u call the functions
    
    #test, not useful anymore tho
    def menu_screen(self):
        oled.fill(0)
        oled.text("-1. Measure HR", 0, 12)
        oled.text(">2. Basic HRV", 0, 22)
        oled.text("-3. Kubios", 0, 32)
        oled.text("-4. History", 0, 42)
        oled.show()
            


rot = Encoder(10, 11, 12)
menu = Menu_Screen(rot)
sample_rate = 250
#tmr = Piotimer(mode = Piotimer.PERIODIC, freq = sample_rate, callback = rot.handler)


def main_menu():
    while True:
        #menu.menu_screen() # this is the test menu screen with no functionality
        menu.choosing_option() #- my code
        #menu.first_page()
        time.sleep(0.1)
        
main_menu()
