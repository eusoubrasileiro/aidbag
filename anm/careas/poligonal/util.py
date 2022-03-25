import os 
import re
import numpy as np 
import sys 

from .geographic import ( 
    wgs84Inverse    
)

def ddegree2dms(dd): 
    """decimal degree to tuple (degrees, minutes, seconds)
        * dd : float64
            degree coordinate (e.g. latitude or longitude)
    return tuple(degrees, minutes, seconds)
    """       
    minutes,seconds = divmod(abs(dd)*3600,60)
    degrees,minutes = divmod(minutes,60)        
    signal = -1 if dd < 0 else 1
    return (signal*int(degrees), int(minutes), seconds)


# coordinates regex for degree minutes seconds and miliseconds 
regex_dmsms = re.compile(r'([-|+]\d{1,2})\D+(\d{1,2})\D+(\d{1,2})\D+(\d{1,3})')
regex_dmsms_ = re.compile(r'([-+]);(\d{1,3});(\d{1,2});(\d{1,2});(\d{1,3})')     # crazy SIGAREAS format
# N decimal places - GTM PRO format but also some dms formats
regex_dms = re.compile(r'([-+]*\d{1,2})[ \'\"\,]+(\d{1,2})[ \'\"\,]+(\d{1,2}[\.\,]\d+)\D')

class NotPairofCoordinatesError(Exception):
    """It must be a pairs of coordinates (lat., lon) even number. Odd number found!"""
    pass

def parse_coordinates(text, decimal=False, fmt='scm'):
    """parse coordinate pairs `text` string using regex 

    * text: str          
        -19°44'18''174 -44°17'45''410 -24°17'15''410 ...  
        or 
        -;019;44;18;173;-;044;17;41;702 ...
        or 
        -19 44 18 174 -44 17 45 410 -24 17 15 410 ...          
        (dmsms) : degree, minute, second and mili seconds 
        or other supported format 

    ouput: numpy array - shape (-1, 2, 3) 
        [[-19, 44, 18.174], [-44, 17, 41.703] ...]
        [[lat0, lon0], [lat1, lon1]...]

    returns list of coordinates parsed
        [[-19, 44, 18.174], [-44, 17, 41.703] ...]

    coordinate has 3 fields:
        [ degree, minutes, seconds ]

    * decimal: bool (default=False)
        convert coordinates to decimal degrees 
        output shape becomes (-1, 2) 

    * fmt : 'scm' default
        'scm' -> try generic dmsms than SIGAREAS format
        'gtmpro' -> dms 10micro seconds, 5 decimal places

    """    
    text = re.sub("\n+", "\n", text) # \n\n are causes lots of problems even with re.MULTILINE
    if fmt == 'scm': # degree minute second milisecond format         
        if text.find('-;') != -1 or text.find('+;') != -1: # crazy SIGAREAS format
            data = np.array([ [ int(sg+d), int(m), float(s +'.'+ msc) ]  
                for sg, d, m, s, msc in regex_dmsms_.findall(text) ], dtype=np.double)
        else: # some degree minute second milisecond format 
            data = np.array([ [ int(d), int(m), float(s+'.'+ms)] 
                for d, m, s, ms in regex_dmsms.findall(text)], dtype=np.double)  
    elif fmt == 'gtmpro': # degree minute second decimal format               
        #text = re.sub("^[^t].*", "", text, flags=re.MULTILINE)  # must remove lines not with start pattern t,dms  
        text = text.replace(',','.')        
        data = np.array([ [*map(float, values)] 
            for values in regex_dms.findall(text) ], dtype=np.double)
    else:
        raise NotImplementedError()
    if data.shape[0]%2 != 0: # must be even lat, lon pairs        
        raise NotPairofCoordinatesError()     
    if decimal:        
        data = np.sum(np.abs(data)*[1., 1/60., 1/3600.], axis=-1)*np.sign(data[:,0])
        data = data.reshape(-1, 2)
    else:
        data = data.reshape(-1, 2, 3)
    return data 

readMemorial = parse_coordinates
readMemorial.__doc__ = """Parse lat, lon string (`llstr`) #Aba Poligonal Scm#
uses `parse_coordinates` that uses regex 
generating numpy array of coordinates.     
"""

# SIGAREAS
# -;019;44;18;173;-;044;17;41;702
# GTMPRO
#t,dms,-17 16' 10.78600'',-41 34' 01.19200'',00/00/00,00:00:00,0,0
# DECIMAL DEGREE
# 

# gtm pro header/footer allways SIRGAS 2000
gtmpro_header = "Version,212\n\nSIRGAS 2000,289, 6378137, 298.257222101, 0, 0, 0\nUSER GRID,0,0,0,0,0\n\n"
gtmpro_footer = "\nn,Track 0001,16711680,1,13" 
# cannot have new lines at the end of the file 
# due pytest using XML tree parser that strips them 

def formatMemorial(latlon, fmt='sigareas', close_poly=True, view=False,
                    save=False, filename='MEMOCOORDS.TXT'):
    """
    Create formated text file poligonal ('Memorial Descritivo') 

    * latlon: numpy array from `memorialRead`
        [[lat,lon]...]

    coordinate have 3 fields:  [ degree, minutes, seconds ]
    * fmt : str 

        'sigareas' : to use on SIGAREAS->Administrador->Inserir Poligonal|Corrigir Poligonal
        
        'gtmpro' : to use on GTM PRO 
            uses header for SIRGAS 2000

        'ddegree' : decimal degree
   
    * save: default=False
        save a file with this poligonal
    
    * filename: str
        name of filename to save this poligonal

    * returns: str 
        formatted string unless `view=True`
    """
    if not isinstance(latlon, np.ndarray):
        raise NotImplemented()    
    if len(latlon.shape) == 2: # decimal degree array as input shape(-1, 2) len(2) instead of len(3)
        # turn in [ degree, minutes, seconds ] array
        latlon = np.array(list(map(ddegree2dms, latlon.flatten()))).reshape(-1, 2, 3)
    if close_poly and (not np.alltrue(latlon[0] == latlon[-1])):  
        latlon = np.append(latlon, latlon[0:1], axis=0) # add first point to the end        
    fmtlines = ""
    if fmt == "sigareas":
        for line in latlon.tolist():
            # -;019;44;18;173;-;044;17;41;702
            line = [ [ str(np.sign(d))[0] , abs(int(d)), int(m), int(s), int(np.round(1000*(s-int(s)),0))  ] 
                for d, m, s in line ]
            fmtlines += "{:};{:03};{:02};{:02};{:03};{:};{:03};{:02};{:02};{:03}\n".format(*line[0], *line[1])      
    elif fmt == "gtmpro":
        fmtlines += gtmpro_header # add header
        for row in latlon.reshape(-1, 2, 3): # dms
            #t,dms,-17 16' 10.33500'',-41 33' 58.96200'',00/00/00,00:00:00,0,0            
            fmtlines += "t,dms,{:03.0f} {:02.0f}\' {:08.5f}\'\',{:03.0f} {:02.0f}\' {:08.5f}\'\',00/00/00,00:00:00,0,0\n".format(
                *row.flatten().tolist())     
        fmtlines += gtmpro_footer # add footer 
        ## needs line ending by windows one '\r\n' otherwise GTMPRO can't read - string will be downloaded directly
        fmtlines = fmtlines.replace("\n", "\r\n") # change here to windows lineseparator '\r\n'
        fmtlines += 'x' # to be removed bellow due pytest xml tree data load 'gambiarra'
    elif fmt == "ddegree":
        data = latlon.reshape(-1, 3)
        # convert to decimal ignore signal than finally multiply by signal back
        data = np.sum(np.abs(data)*[1., 1/60., 1/3600.], axis=-1)*np.sign(data[:,0])
        for row in data.reshape(-1, 2):                 
            fmtlines += "{:12.9f} {:12.9f} \n".format(*row.flatten().tolist())     
    # remove last newline due pytest xml tree test data load ignoring it    
    fmtlines = fmtlines[:-1]  
    if save:
        # newline='' force it not to change lineseparator chars
        with open(filename.upper(), 'wt', newline='', encoding="utf-8") as f: # 't' for text, must be CAPS otherwise can't upload
            f.write(fmtlines)
        print("Output filename is: ", filename.upper())    
    if view: # only to see         
        return print(fmtlines)    
    else:
        return fmtlines

def check_nsew_memo(data, maxdev=1):
    """simple fast check if its a nsew navigation

    * latlon: numpy array from `memorialRead(...,decimal=True)`
        [[lat,lon]...]

    * maxdev : angle in degrees for maximum deviation acceptable
        from north/south/east/west

    tan of theta = theta : for angles < 9 degrees (error < 1%)

    Hence we calculate tan(deviation angle) on first quadrant using 
    deviation angle (min(abs(lat),abs(lon))/max(abs(lat), abs(lon)))

    Note: use maxdev=0 for check use on sigareas
    """
    vectors = np.abs(np.diff(data, axis=0)) # vectors on first quadrant
    maxs = np.max(vectors, axis=-1) 
    mins = np.min(vectors, axis=-1)
    dev_angles = np.rad2deg(mins/maxs) # angles of deviation from n/s/e/w
    return np.alltrue(dev_angles <= maxdev)  

class forceverdFailed(Exception):
    """increase the tolerance distance to adjust to nsew"""
    pass

# this poly is kinda troublesome it can't get
# rectlinear even if tolerance is put too high 
issue_poly = """-19°44'18''174 -44°17'41''703||
-19;44;;18''174 -44°17'45''410
xxxx -19°44'16''507 -44°17'45''410
-19°44'16''507   -44°17'52''079
-19°44'18''250 -44°17'52''079
-19°44'18|295 -44°17'53''625
"""
# that one is an open polygon that cannot be easly 
# made a rectilinear polygon (correct term by wikipedia)
# https://en.wikipedia.org/wiki/Rectilinear_polygon

# the algo bellow works only for simple approximations to rectlinear polygons

# it's a problem inherent from setting tolerance too high
# what the algorithm bellow does is 'to trace straigth lines' 
# from each y, x (lat, lon) coordinate and check if any
# of the coordinates nearby y or x can be replaced 
# without much loss given by tolerance (distance maximum acceptable)
# but if you set a too high distance things will get weird 
# because you can scramble coordinates througout the for loop
# since you will adjuste and readjust more than once
# doesn't make sense at all 

def _forceverdAprox(vertices, tolerancem=0.5, debug=True):
    cvertices = np.copy(vertices)
    vertices_new = np.copy(cvertices)
    dists = []
    for i, (plat, plon) in enumerate(cvertices):
        for j, (lat, lon) in enumerate(cvertices[i+1:]): # compare with next one : downward
            dlat, dlon = lat-plat, lon-plon
            dist = wgs84Inverse(lat, lon, plat, lon)
            if(dlat != 0.0 and abs(dist) < tolerancem ):
                if debug:
                    print('line: {:>3d} - lat {:.8f} changed to {:.8f} distance {:2.2f} (m)'.format(i+1+j+1,
                        lat, plat, dist), file=sys.stderr)
                vertices_new[i+1+j, 0] = plat
                dists.append(dist)
            dist = wgs84Inverse(lat, lon, lat, plon)
            if(dlon != 0.0 and abs(dist) < tolerancem):
                if debug:
                    print('line: {:>3d} - lon {:.8f} changed to {:.8f} distance {:2.2f} (m)'.format(i+1+j+1,
                        lon, plon, dist), file=sys.stderr)
                dists.append(dist)
                vertices_new[i+1+j, 1] = plon    
    return dists, vertices_new 

def forceverdPoligonal(vertices, tolerancem=0.5, view=False, close_poly=True, debug=True):
    """
    Aproxima coordenadas para rumos verdadeiros.
    Aproximate decimal coordinates (lat,lon) to previous (lat or lon).    

    *close_poly : default True
            close polygon (if needed) repeating first vertex at the end
    *tolerancem: default 0.5 meter
            distance to accept as same lat or lon as previous
    
    """
    if not isinstance(vertices, np.ndarray):
        raise NotImplemented()          
    if np.alltrue(vertices[0] == vertices[-1]): # needed for calculations bellow
        vertices = vertices[:-1]  # remove end (repeated vertex)      
    dists, vertices_new = _forceverdAprox(vertices, tolerancem, debug)
    if debug and dists: # not dists: means no statistics to report and nothing more            
        print("Changes statistics min (m) : {:2.2f}  p50: {:2.2f} max: {:2.2f}".format(
            *(np.percentile(dists, [0, 50, 100]))), file=sys.stderr)
    if check_nsew_memo(vertices_new, 0) == False:
        print(vertices_new)
        raise forceverdFailed(str(vertices_new))  # 'rumos verdadeiros' NSEW check sigareas deviation 0
    if close_poly: # close polygon back
        vertices_new = np.append(vertices_new, vertices_new[0:1], axis=0)
    if view:
        print(vertices_new)
    else: 
        return vertices_new
