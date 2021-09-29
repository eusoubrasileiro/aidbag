import time, re, subprocess

#def log_print(*args, **kwargs):
#    with lock:
#        print(time.strftime("%Y-%m-%d %H:%M:%S")," ".join(map(str,args)), file=log_file,**kwargs)
#        if kwargs.get('print_stdout', True):    # by default don't print on stdout - since inside tmux and log-file already exists    
#            print(time.strftime("%Y-%m-%d %H:%M:%S")," ".join(map(str,args)),**kwargs)

# import logging

# logging.basicConfig(
#     level=logging.INFO,
#     datefmt='%m/%d/%Y %I:%M:%S '
#     format='%(asctime)s %(message)s',
#     handlers=[
#         logging.FileHandler("core_temps.txt"),
#         logging.StreamHandler()
#     ]
# )

# logprint = logging.info

if __name__ == "__main__":
    while(True):
      try:      
        sensors = subprocess.check_output(['sensors']).decode()
        sensors = re.findall('([\+]*\d{1,3}\.\d+).+C', sensors)
        c0temp, c1temp = sensors[0], sensors[3]
        # cpu use to correlate info
        mpstat = subprocess.check_output(['mpstat', '1', '5']).decode() # average 5 measures
        cpuuse = float(mpstat.split('\n')[-2].split(' ')[8].replace(',','.'))

        print(time.strftime("%Y-%m-%d %H:%M:%S")+" "+" ".join(map(str,[c0temp, c1temp, cpuuse])))
        with open('core_temps.txt', 'a') as file:
            file.write(time.strftime("%Y-%m-%d %H:%M:%S")+" "+" ".join(map(str,[c0temp, c1temp, cpuuse]))+"\n")
        time.sleep(10*60)
      except:
          pass 

