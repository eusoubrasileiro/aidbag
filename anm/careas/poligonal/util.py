import re
import numpy as np 

from .geographic import ( 
    wgs84Inverse    
)

def decdeg2dmsms(dd): 
    """decimal degree to (degrees, minutes, seconds, miliseconds)
        * dd : float

    return tuple(degrees, minutes, seconds, miliseconds)
    """       
    minutes,seconds = divmod(abs(dd)*3600,60)
    degrees,minutes = divmod(minutes,60)    
    mseconds = 1000*(seconds - int(seconds))
    signal = -1 if dd < 0 else 1
    return (signal*int(degrees), int(minutes), int(seconds), int(mseconds))


class NotPairofCoordinatesError(Exception):
    """It must be a pairs of coordinates (lat., lon) even number. Odd number found!"""
    pass

# coordinates regex for degree minutes seconds and miliseconds 
regex_dmsms = re.compile('(-)*(\d{1,2})\D+(\d{1,2})\D+(\d{1,2})\D+(\d{1,3})')
regex_dmsms_ = re.compile('([-+]);(\d{1,3});(\d{1,2});(\d{1,2});(\d{1,3})')     # crazy SIGAREAS format
# 10^-6 microseconds - 10^-5 seconds is 10 * microseconds - 
# 5 decimal places - GTM PRO format
regex_dms10us = re.compile('(-)*(\d{1,2})\D+(\d{1,2})\D+(\d{1,2})\D+(\d{5})') 

def parse_coordinates(text, decimal=False, fmt='auto'):
    """parse coordinate pairs `text` string using regex 

    * text: str          
        -19°44'18''174 -44°17'45''410 -24°17'15''410 ...  
        or 
        -;019;44;18;173;-;044;17;41;702 ...
        or 
        -19 44 18 174 -44 17 45 410 -24 17 15 410 ...          
        (dmsms) : degree, minute, second and mili seconds 
    
    ouput: numpy array - shape (-1, 2, 5) 
        [[-1, 19, 44, 18, 174], [-1, 44, 17, 41, 703] ...]
        [[lat0, lon0], [lat1, lon1]...]

    returns list of coordinates parsed
        [[-1, 19, 44, 18, 174], [-1, 44, 17, 41, 703] ...]

    coordinate have 5 fields:
        [ signal +/- 1, degree, minutes, seconds, miliseconds ]

    * decimal: bool (default=False)
        convert coordinates to decimal degrees 
        output shape becomes (-1, 2) 

    * fmt : 'auto' default
        'auto' -> try generic dmsms than SIGAREAS format
        'gtmpro' -> dms 10micro seconds, 5 decimal places

    """    
    regex = regex_dmsms
    if fmt == 'auto':        
        if text.find('-;') != -1 or text.find('+;') != -1: # crazy SIGAREAS format
            regex = regex_dmsms_
    if fmt == 'gtmpro':        
        regex = regex_dms10us
    csparsed = re.findall(regex, text)
    coords = [ [int(sg+'1'), *map(int, [dg, mn, sc, msc])] 
                for sg, dg, mn, sc, msc in csparsed ]
    if len(csparsed)%2 != 0: # must be even lat, lon pairs        
        raise NotPairofCoordinatesError()     
    llcs = np.array(coords) #lat, lon = coords[::2],  coords[1::2]     
    if fmt == 'gtmpro': # convert from 10us (10^-5) to miliseconds (from gtmpro)
        llcs[:, 4] = llcs[:, 4]*0.01        
    if decimal:
        npl = llcs.reshape(-1, 5)
        # convert to decimal ignore signal than finally multiply by signal back
        npl = np.sum(npl*[0, 1., 1/60., 1/3600., 0.001*1/3600.], axis=-1)*npl[:,0]
        llcs = npl.reshape(-1, 2)
    else:
        llcs = llcs.reshape(-1, 2, 5)
    return llcs 

readMemorial = parse_coordinates
readMemorial.__doc__ = """Parse lat, lon string (`llstr`) #Aba Poligonal Scm#
uses `parse_coordinates` that uses regex 
generating numpy array of coordinates.     
"""

# SIGAREAS
# -;019;44;18;173;-;044;17;41;702
# GTMPRO
#t,dms,-17 16' 10.78600'',-41 34' 01.19200'',00/00/00,00:00:00,0,0
#t,dms,-17 16' 10.78600'',-41 33' 58.96200'',00/00/00,00:00:00,0,0
#t,dms,-17 16' 10.33500'',-41 33' 58.96200'',00/00/00,00:00:00,0,0
# DECIMAL DEGREE
# 
#
# 

def formatMemorial(latlon, fmt='sigareas', endfirst=False, view=False,
                    save=False, filename='MEMOCOORDS.TXT'):
    """
    Create formated text file poligonal ('Memorial Descritivo') 

    * latlon: numpy array from `memorialRead`
        [[lat,lon]...]

    coordinate have 5 fields:  [ signal +/- 1, degree, minutes, seconds, miliseconds ]

    * fmt : str 

        'sigareas' : to use on SIGAREAS->Administrador->Inserir Poligonal|Corrigir Poligonal
        
        'gtmpro' : to use on GTM PRO ?
        
        'ddegree' : decimal degree

    * endfirst: default True
        copy first point in the end
    
    * save: default=False
        save a file with this poligonal
    
    * filename: str
        name of filename to save this poligonal

    * returns: str 
        formatted string unless `view=True`
    """
    if not isinstance(latlon, np.ndarray):
        raise NotImplemented()    
    if endfirst:  # add first point to the end
        latlon = np.append(latlon, latlon[-1]) 
    fmtlines = ""
    if fmt == "sigareas":
        lines = latlon.reshape(-1, 10).tolist()
        for line in lines:
            # -;019;44;18;173;-;044;17;41;702
            s0, s1 = map(str, [line[0], line[5]]) # to not print -1,+1 only - or +
            s0, s1 = s0[0], s1[0]            
            fmtlines += "{0:};{3:03};{4:02};{5:02};{6:03};{1:};{8:03};{9:02};{10:02};{11:03}\n".format(
                    s0, s1, *line) # for the rest * use positional arguments ignoring the old signals args [2, 7]           
    elif fmt == "gtmpro":
        data = latlon.reshape(-1, 5).astype(np.double)
        data[:,1] = data[:,0]*data[:,1] # 'add' signal 
        data[:,3] = data[:,3]+0.001*data[:,4] # add miliseconds to seconds
        data = data[:,1:4] # dms
        for row in data.reshape(-1, 2, 3): # dms
            #t,dms,-17 16' 10.33500'',-41 33' 58.96200'',00/00/00,00:00:00,0,0            
            fmtlines += "t,dms,{:03.0f} {:02.0f}\' {:08.5f}\'\',{:03.0f} {:02.0f}\' {:08.5f}\'\',00/00/00,00:00:00,0,0 \n".format(
                *row.flatten().tolist())     
    elif fmt == "ddegree":
        data = latlon.reshape(-1, 5)
        # convert to decimal ignore signal than finally multiply by signal back
        data = np.sum(data*[0, 1., 1/60., 1/3600., 0.001*1/3600.], axis=-1)*data[:,0]
        for row in data.reshape(-1, 2):                 
            fmtlines += "{:12.9f} {:12.9f} \n".format(*row.flatten().tolist())             
    if save:
        with open(filename.upper(), 'w') as f: # must be CAPS otherwise can't upload
            f.write(fmtlines)
        print("Output filename is: ", filename.upper())    
    if view: # only to see         
        return print(fmtlines)    
    else:
        return fmtlines


def forceverdPoligonal(vertices, tolerancem=0.5, verbose=True, ignlast=True):
    """
    #Força rumos verdadeiros#
    Force decimal coordinates (lat,lon) to previous (lat/lon)
    otherwise sigareas wont accept this polygon

    *ignlast : default True
            ignore last point (repeated from first)
    *tolerancem: default 0.5 meter
            distance to accept as same lat or lon as previous
    """
    cvertices = np.copy(np.array(vertices))
    vertices_new = np.copy(cvertices)
    if ignlast:
        cvertices = cvertices[:-1]
    dists = []
    for i, (plat, plon) in enumerate(cvertices):
        for j, (lat, lon) in enumerate(cvertices[i+1:]): # compare with next one : downward
            dlat, dlon = lat-plat, lon-plon
            dist = wgs84Inverse(lat, lon, plat, lon)
            if(dlat != 0.0 and abs(dist) < tolerancem ):
                print('line: {:>3d} - lat {:.8f} changed to {:.8f} distance {:2.2f} (m)'.format(i+1+j+1,
                    lat, plat, dist))
                vertices_new[i+1+j, 0] = plat
                dists.append(dist)
            dist = wgs84Inverse(lat, lon, lat, plon)
            if(dlon != 0.0 and abs(dist) < tolerancem):
                print('line: {:>3d} - lon {:.8f} changed to {:.8f} distance {:2.2f} (m)'.format(i+1+j+1,
                    lon, plon, dist))
                dists.append(dist)
                vertices_new[i+1+j, 1] = plon
    if ignlast: # replace instead of ignoring last
        vertices_new[-1] = vertices_new[0]
    
    if not dists: # no distances means all zero - already rumos verdadeiros
        print("Already rumos verdadeiros - no change!")
    else:
        print("Changes statistics min (m) : {:2.2f}  p50: {:2.2f} max: {:2.2f}".format(
            *(np.percentile(dists, [0, 50, 100]))))

    def test_verd(vertices):
        """test wether vertices are lat/lon 'rumos verdadeiros' """
        dlat, dlon = np.diff(vertices[:,0]), np.diff(vertices[:,1])
        for dif in (dlat, dlon): # for lat and lon check
            if np.alltrue(dif[::2] != 0):
                if np.alltrue(dif[1::2] == 0):
                    continue
            if np.alltrue(dif[::2] == 0):
                if np.alltrue(dif[1::2] != 0):
                    continue
            return False
        return True
    check_verd = test_verd(vertices_new)
    print("rumos verdadeiros check: ", "passed" if check_verd else "failed")
    return vertices_new





