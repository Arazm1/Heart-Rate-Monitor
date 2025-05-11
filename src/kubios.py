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


class Basichrv_kubios:
    def __init__(self, pin_num, sample_rate):
        self.pulse_pin = ADC(pin_num)
        self.sample_amount =  7500  #You can test different values however I think for 30 seconds it must be 7500
        self.sample_amount_counter_max = self.sample_amount + 1
        self.samples = Fifo(self.sample_amount)
        self.sample_rate = sample_rate
        
        self.sample_counter = 0
        
        #typeshhhh
        #Stuff for processing func
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
        


    #Functions for OLED screens
    def start_text(self):
        self.oled.fill(0)
        self.oled.text("Kubios", 20, 14)
        self.oled.text("Place your",20, 30)
        self.oled.text("finger", 32, 40)
        self.oled.show()
        
        
    
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
    def detect_kubios(self):
        self.start_text()
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
                    #print(value)
                    self.samples.put(value)
                    self.sample_counter += 1
                    
                    
            except:
                print("fifo is full")
                #Apparently heres the correct place to call it
                print(self.samples.data)
                self.process_kubios()
                break
            time.sleep(0.004)
            
        #Now theres enough
        #print("Collected enought", self.sample_counter)
        #self.lets_process()
        
    
    def process_kubios(self):

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
        
        #print("th: ", th)  #-works

        for value in self.samples_valid:
            #print(value)
            if not self.in_peak_area:  #not in peak et
                if value > th:
                    self.in_peak_area = True  #peak detection mode on fam
            
            
            #Now we look for the max point
            if self.in_peak_area == True:
                if self.prev_value > value and not self.peak_found:
                    # Peak found, calculate HR
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
            

        #print(self.ppi)    
        if self.ppi:
        #    print(self.ppi)

            self.mean_ppi = self.calc_meanppi()
            self.mean_hr = self.calc_meanhr()
            self.rmssd = self.calc_rmssd()
            self.sdnn = self.calc_sdnn()

            print(f"Mean PPI: {self.mean_ppi}")
            print(f"Mean HR: {self.mean_hr}")
            print(f"RMSSD: {self.rmssd}")
            print(f"SDNN: {self.sdnn}")
            
            
            #Kubiokseen
            self.measurementOLD = {
            "mean_ppi": self.mean_ppi,
            "mean_hr": self.mean_hr,
            "rmssd": self.rmssd,
            "sdnn": self.sdnn
            }
            
            #get the time
            current_time = int(time.time())
            

            #test:
            sns = 1.234
            pns = -1.234
            
            heart_rate_intervals = [828, 836, 852, 760, 800, 796, 856, 824, 808, 776, 724, 816, 800, 812, 812, 812, 756, 820, 812, 800]

            
            #print("need to send this: ", self.ppi)

            self.measurement = {
            "id": 123,
            "type": "RRI",
            "data": self.ppi,
            "analysis": { "type": "readiness" }
          }

            
            #Test prints
            #print("dict: ", self.measurement)
            
            
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
    def __init__(self, wlan_ssid, wlan_password, broker_ip, port):
        self.ssid = wlan_ssid
        self.password = wlan_password
        self.broker_ip = broker_ip
        self.port = port
        
    def connect_wlan(self):   
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.wlan.connect(self.ssid, self.password)

        while self.wlan.isconnected() == False:
            print("Connecting... ")
            sleep(1)
        print("Connection successful. Pico IP:", self.wlan.ifconfig()[0])
        return self.wlan
        
    def connect_mqtt(self):
        self.mqtt_client=MQTTClient("", self.broker_ip, self.port)
        self.mqtt_client.connect(clean_session=True)
        print("connected to mqtt")
        return self.mqtt_client


class Kubios():
    def __init__(self, wlan, mqtt_client):
        self.test_msg = {
            "id": 123,
            "type": "RRI",
            "data": [
            828, 836, 852, 760, 800, 796, 856, 824, 808, 776, 724, 816, 800, 812, 812,
            812, 756, 820, 812, 800
            ],
            "analysis": { "type": "readiness" }
        }

        self.kubios_response_data = {}

        self.reply = {}

        self.wlan = wlan
        self.mqtt_client = mqtt_client

        self.SSID = "KMD751_Group_10"
        self.PASSWORD = "salasana_ryhma5"
        self.kubios_req = "kubios-request"
        self.kubios_resp = "kubios-response"

        self.response_received = False
        
        
        #Screen
        self.WIDTH, self.HEIGHT = 128, 64
        self.i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
        self.oled = SSD1306_I2C(self.WIDTH, self.HEIGHT, self.i2c)
        
    
    def kubios_request(self, measurement):
        msg = ujson.dumps(measurement)
        self.msg = ujson.dumps(measurement)

        self.mqtt_client.publish(self.kubios_req, self.msg)
        #test to see
        #print(f"Published message to {self.kubios_req}: {self.msg}")


    #lot of debugging, clean this up
    def kubios_response(self, topic, msg):
        print(f"Received on topic: {topic}")
        print(f"Message received: {msg}")
        try:
            msg_in_dict = ujson.loads(msg)
            self.reply = msg_in_dict
            self.response_received = True
            print("processed response: ", self.reply)
        except Exception as e:
            print("Error in kubios_response function", e)


    #clean the useless print after done
    def sub_kubios_response(self):
        self.mqtt_client.set_callback(self.kubios_response)
        self.mqtt_client.subscribe(self.kubios_resp)
        print(f"Subscribed to {self.kubios_resp} for responses.")
        

    def check_kubios_response(self):
        self.mqtt_client.check_msg()
        return self.response_received
    

    def get_response(self):
        self.response_received = False
        return self.reply
    
    
    #Gets the specific values we want
    def get_results_printoled(self):
        try:
            results = self.reply['data']['analysis']
            self.mean_hr_bpm = results.get('mean_hr_bpm')
            self.rmssd_ms = results.get('rmssd_ms')
            self.sdnn_ms = results.get('sdnn_ms')
            self.sns_index = results.get('sns_index')
            self.pns_index = results.get('pns_index')
            return True
            #return self.reply['data']['analysis']['mean_hr_bpm']['mean_hr_bpm']['rmssd_ms']['sdnn_ms']['sns_index']['pns_index']
        except:
            return None
        
        
    #Displays the results
    def results_on_oled(self):
        self.oled.fill(0)
        self.oled.text(f"HR: {self.mean_hr_bpm:.2f}", 0, 2)
        self.oled.text(f"RMSSD: {self.rmssd_ms:.2f}", 0, 12)
        self.oled.text(f"SDNN: {self.sdnn_ms:.2f}", 0, 22)
        self.oled.text(f"SNS: {self.sns_index:.2f}", 0, 32)
        self.oled.text(f"PNS: {self.pns_index:.2f}", 0, 42)
        self.oled.show()
        
        time.sleep(10)
        

ssid = "KMD751_Group_10"
password = "salasana_ryhma5"
broker_ip = "192.168.5.14"
port = 21883

network_connection = ConnectWlan(ssid, password, broker_ip, port)
wlan = network_connection.connect_wlan()
mqtt_client = network_connection.connect_mqtt()


kubios = Kubios(wlan, mqtt_client)
kubios.sub_kubios_response()
#kubios.kubios_request()

def main_kubios():
    pin_num = 27
    sample_rate = 250
    program_kubios = Basichrv_kubios(pin_num, sample_rate)
    program_kubios.detect_kubios()
    
    #Basichrv_kubios.start_text()
    #time.sleep(3)


    kubios.kubios_request(program_kubios.measurement)


    attempts = 0
    while attempts < 5:
        sleep(1)
        kubios.mqtt_client.check_msg()
        if kubios.check_kubios_response():
            print("Received:", kubios.get_response())

            kubios.get_results_printoled()
            #Now it displays them on OLED
            kubios.results_on_oled()
            break
        attempts += 1
    else:
        print("Did not receive response from Kubios.")
        
    #if kubios.check_kubios_response():
        
#main_kubios() #call this from menu.py (or screentest.py)


