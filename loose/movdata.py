import os, datetime, glob, re
from pathlib import Path

# date time creation only linux
def modification_date(filename):
    t = os.path.getmtime(filename)
    return datetime.datetime.fromtimestamp(t)

os.chdir(os.path.join(str(Path.home()), 'nwrouter/motion_data/pictures'))

for fpath in glob.glob("*09.2*cam3.jpg"):    
    mvarea = re.findall('\_D(\d+)\_', fpath) # proportional area of moviment detected
    print(modification_date(fpath), float(mvarea[0]))
