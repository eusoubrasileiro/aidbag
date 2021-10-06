import time, re, subprocess

# if windows it is speedtest-cli cmd

if __name__ == "__main__":
    while(True):
        try:      
            # "server name","server id","latency","jitter","packet loss","download","upload","download bytes","upload bytes","share url"
            # "Connect Telecomunicaçoes - Pedro Leopoldo","31117","24.602","0.994","0","2415723","2817351","23229792","23130252","https://www.speedtest.net/result/c/7bced9f6-a6fc-46c6-82ff-2bdbb825d011"
            results = subprocess.run("speedtest -p no -f csv", stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            stdout = results.stdout.decode() 
            stderr = results.stderr.decode()
            with open('speed_test.txt', 'a') as file:
                if results.returncode != 0 and stderr.find('(Network is unreachable)') != -1:                
                    print(time.strftime("%Y-%m-%d %H:%M:%S")+" "+"internet down")            
                    file.write(time.strftime("%Y-%m-%d %H:%M:%S")+" "+"internet down"+"\n")
                else:
                    print(time.strftime("%Y-%m-%d %H:%M:%S")+" "+stdout)            
                    file.write(time.strftime("%Y-%m-%d %H:%M:%S")+" "+stdout+"\n")
            time.sleep(10*60)
        except Exception as exc:
            print("Exception: ", exc)