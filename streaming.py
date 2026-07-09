import network, socket
import time, gc
from scanwheel import ScanWheel

def read_config(config):
    ssid = 'guest'
    pw = 'guest'
    
    try:
        with open(config) as f:
            for line in f:
                line = line.split('#',1)[0].strip()
                if line and '=' in line:
                    k,v = line.split('=',1)
                    k = k.strip()
                    
                    if   k == 'ssid':
                        ssid = v.strip()
                    elif k == 'wifipw':
                        pw = v.strip()

    except:
        pass
    
    return ssid, pw
    
    


def wifi_connect():
    wlan = None

    try:
        config = ScanWheel.read_config()

        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(config['ssid'], config['wifipw'])

        connection_timeout = 10
        while connection_timeout > 0:
            if wlan.status() >= 3:
                break
            
            connection_timeout -= 1
            print('connecting...')
            time.sleep(1)

        if wlan.status() == 3:
            print('connected')
        else:
            wlan = None
        
    except:
        wlan = None

    return wlan

def main():
    sw = ScanWheel(linewidth=1024, framerate=15)

    sw.align()
    sw.start(leds_state=0b00000010)
    
    wlan = wifi_connect()
    if wlan is None:
        return
    
    network_info = wlan.ifconfig()
    ipaddress = network_info[0]
    print('ip address:', ipaddress)

    try:
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", 2000))
        sock.listen(1)
        
        while True:
            client, addr = sock.accept()
            connected = True
            print(addr)
            
            mv = memoryview(sw.frame_memory)
            while connected:
                f = 0
                while f < sw.frame_size:
                    r = client.readinto(mv[f:])
                    if r == 0:
                        print('connection closed')
                        connected = False
                        break
                    f += r
                    
            client.close()
            
    finally:
        client.close()
        sock.close()
        gc.collect()
        
            
if __name__ == "__main__":
    main()
