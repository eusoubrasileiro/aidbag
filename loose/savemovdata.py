import os, datetime, glob, re
from pathlib import Path

# date time creation only linux
def modification_date(filename):
    t = os.path.getmtime(filename)
    return datetime.datetime.fromtimestamp(t)

cdir = os.getcwd()
os.chdir(os.path.join(str(Path.home()), '/mnt/data/motion_data/pictures'))

with open(os.path.join(cdir, 'cam3.txt'), 'a') as f: # better append than drop duplicates
    for fpath in glob.glob("*cam3.jpg"):     
        mvarea = re.findall('\_D(\d+)\_', fpath) # proportional area of moviment detected
        f.write(str(modification_date(fpath)) + ' ' + str(float(mvarea[0])) + '\n')
