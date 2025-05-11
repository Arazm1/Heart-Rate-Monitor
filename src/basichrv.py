import time
import math
from machine import Pin, ADC, I2C, UART, Timer, PWM
from ssd1306 import SSD1306_I2C
import time
from fifo import Fifo
from led import Led
from piotimer import Piotimer
import ujson


import network
from time import sleep
from umqtt.simple import MQTTClient

import micropython
micropython.alloc_emergency_exception_buf(200)


class Basichrv:
    def __init__(self, pin_num, sample_rate):
        self.pulse_pin = ADC(pin_num)
        self.sample_amount =  7500  #You can test different values - however I think for 30 seconds it must be 7500
        self.sample_amount_counter_max = self.sample_amount + 1
        self.samples = Fifo(self.sample_amount)
        self.sample_rate = sample_rate
        
        self.sample_counter = 0 #we need it to 7500 to run lets_process
        
        #typeshhhh
        #Stuff for lets_process func
        self.sample_index = 0
        self.ppi = []
        self.prev_value = 0
        self.samples_valid = []
        
        #for the loop in lets_process func
        self.in_peak_area = False
        self.peak_found = False
        
        
        self.finger_is_on = True
        self.current_hr = 0
        
        
        #Screen
        self.WIDTH, self.HEIGHT = 128, 64
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.oled = SSD1306_I2C(self.WIDTH, self.HEIGHT, self.i2c)
        self.screen_state = "Basic HRV"
        
        
        self.x_pos = 0
        self.y_pos = self.HEIGHT // 2
        self.prev_y_pos = 0
        
        
        #Results:
        self.mean_ppi = 0
        self.mean_hr = 0
        self.sdnn = 0
        self.rmssd = 0
        
        #To be sent
        self.measurement = {}
        

    #Functions for screen displaying
    #"Start screen"
    def start_text(self):
        self.oled.fill(0)
        self.oled.text("Basic HRV", 20, 14)
        self.oled.text("Place your",20, 30)
        self.oled.text("finger", 32, 40)
        self.oled.show()
        
    #"Collecting data screen"
    def collecting_text(self):
        self.oled.fill(0)
        #Each line of text that comes on the screen can be put into list later on use for loop to 
        lines = ["Collecting", "samples for", "30 sec"]
        y = 14  #y level starts here, you can adjust
        
        for line in lines:
            #Each character is 8 pixels wide
            #//2 so center
            x = (self.WIDTH - len(line) * 8) // 2
            self.oled.text(line, x, y)
            y += 10  #next lines

        self.oled.show()
        
    
    
    
    #Seems to work so far, tested with 500 samples
    def detect_basichrv(self):
        self.start_text() #display
        time.sleep(3)
        
        
        
        while self.sample_counter <= self.sample_amount_counter_max:    
            try:
                value = self.pulse_pin.read_u16()
                #self.samples.put(value) #tarkistetaan ensin valuen validi
                

                #sormella on painettu nyt
                if value<500:
                    self.finger_is_on = True
                    self.collecting_text()
                    
                #sormi on pois
                if value >55000:
                    self.finger_is_on = False
                
                if self.finger_is_on == True and 25000 < value < 35000:
                    #print(self.samples)
                    self.samples.put(value)
                    self.sample_counter += 1
                    
                    
            except:
                #print("fifo is full")
                print(self.samples.data)
                self.process_data_hrv()
                break
            time.sleep(0.004)
            
        #Now theres enough
        #print("Collected enought", self.sample_counter)


    
    #Processing the data and as well as dealing with the results
    def process_data_hrv(self):    
        while self.samples.has_data():
            try:
                check_value = self.samples.get()
                if check_value > 0:
                    self.samples_valid.append(check_value)
            except RuntimeError:
                break
        #print(self.samples_valid)  #-works
        
        min_value = min(self.samples_valid)
        max_value = max(self.samples_valid)
        
        #print("min, max: ", min_value, max_value)  #-works
        
        h = max_value - min_value
        th = int(min_value + 0.8 * h)
        
        #print("th: ", th)  #Test -works

        for value in self.samples_valid:
            #print(value)
            if not self.in_peak_area:  #not in peak yet
                if value > th:
                    self.in_peak_area = True  #peak detection mode on fam
            
            #Now we look for the max point
            if self.in_peak_area == True:
                if self.prev_value > value and not self.peak_found:
                    #Peak found, calculate HR
                    ppi_in_samples = self.sample_index - 1
                    ppi_in_ms = ppi_in_samples * 4
                    #print("in_ms", ppi_in_ms)
                    seconds = 60000
                    hr = int(seconds / ppi_in_ms)
                    self.peak_found = True

                    if 30 <= hr <= 240:
                        self.ppi.append(ppi_in_ms)
                        print(f"HR: {hr}")

                    self.sample_index = 0

                if value < th:
                    self.in_peak_area = False
                    self.peak_found = False

            self.prev_value = value
            self.sample_index += 1
            
        #If there are enough ppi
        #print(self.ppi)
        if self.ppi:
            #print(self.ppi) - #Test print unnecessary now
            #Calculate the values
            self.mean_ppi = self.calc_meanppi()
            self.mean_hr = self.calc_meanhr()
            self.rmssd = self.calc_rmssd()
            self.sdnn = self.calc_sdnn()

            #Test prints
            #print(f"Mean PPI: {self.mean_ppi}")
            #print(f"Mean HR: {self.mean_hr}")
            #print(f"RMSSD: {self.rmssd}")
            #print(f"SDNN: {self.sdnn}")
            
            #For Kubios
            self.measurement = {
            "mean_ppi": self.mean_ppi,
            "mean_hr": self.mean_hr,
            "rmssd": self.rmssd,
            "sdnn": self.sdnn
            }

            #Test print
            #print("dict: ", self.measurement)


            #Display the results on the screen
            self.oled.fill(0)
            self.oled.text(f"PPI: {int(self.mean_ppi)}", 0, 0)
            self.oled.text(f"HR: {int(self.mean_hr)}", 0, 10)
            self.oled.text(f"RMSSD: {int(self.rmssd)}", 0, 20)
            self.oled.text(f"SDNN: {int(self.sdnn)}", 0, 30)
            self.oled.show()
            time.sleep(7) # allow the user to see the results for 7 seconds

            
    def calc_meanhr(self):
        self.mean_hr = int(60000 / self.mean_ppi)
        return self.mean_hr
    
    
    def calc_meanppi(self):
        self.mean_ppi = sum(self.ppi) / len(self.ppi)
        return self.mean_ppi
                    
        
    def calc_rmssd(self):
        self.diff_sq = [(self.ppi[i] - self.ppi[i - 1]) ** 2 for i in range(1, len(self.ppi))]
        self.rmssd = math.sqrt(sum(self.diff_sq) / len(self.diff_sq))
        return self.rmssd
    
    def calc_sdnn(self):
        self.v = sum((i - self.mean_ppi) ** 2 for i in self.ppi) / len(self.ppi)
        self.sdnn = math.sqrt(self.v)
        return self.sdnn



class ConnectWlan():
    def __init__(self, wlan_ssid, wlan_password, broker_ip):
        self.ssid = wlan_ssid
        self.password = wlan_password
        self.broker_ip = broker_ip
        
    def connect_wlan(self):   
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(self.ssid, self.password)

        #Attemt to connect
        while wlan.isconnected() == False:
            print("Connecting... ")
            sleep(1)
        print("Connection successful. Pico IP:", wlan.ifconfig()[0])
        
    def connect_mqtt(self):
        mqtt_client=MQTTClient("", self.broker_ip)
        mqtt_client.connect(clean_session=True)
        print("connected to mqtt")
        return mqtt_client


#Network function
def basichrv_wlan():
    ssid = "KMD751_Group_10"
    password = "salasana_ryhma5"
    broker_ip = "192.168.5.14"
    MoumenDidThis = ConnectWlan(ssid, password, broker_ip)
    MoumenDidThis.connect_wlan()
    mqtt_client = MoumenDidThis.connect_mqtt()


#Main function
def main_basichrv():
    
    ssid = "KMD751_Group_10"
    password = "salasana_ryhma5"
    broker_ip = "192.168.5.14"
    MoumenDidThis = ConnectWlan(ssid, password, broker_ip)
    MoumenDidThis.connect_wlan()
    mqtt_client = MoumenDidThis.connect_mqtt()
    
    pin_num = 27
    sample_rate = 250
    hrv_program = Basichrv(pin_num, sample_rate)
    hrv_program.detect_basichrv()
    

    json_message_hrv = ujson.dumps(hrv_program.measurement)
    
    mqtt_client.publish("pico/test", json_message_hrv)

#main_basichrv() #call this from menu



