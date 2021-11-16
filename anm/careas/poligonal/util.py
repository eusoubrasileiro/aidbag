import re
import numpy as np 
import sys 

from .geographic import ( 
    wgs84Inverse    
)

def ddegree2dmsms(dd): 
    """decimal degree to tuple (+/- 1 signal, degrees, minutes, seconds, miliseconds)
        * dd : float64
            degree coordinate (e.g. latitude or longitude)
    return tuple(+/- 1 signal, degrees, minutes, seconds, miliseconds)
    """       
    minutes,seconds = divmod(abs(dd)*3600,60)
    degrees,minutes = divmod(minutes,60)    
    mseconds = 1000*(seconds - int(seconds))
    signal = -1 if dd < 0 else 1
    return (signal, int(degrees), int(minutes), int(seconds), mseconds)


class NotPairofCoordinatesError(Exception):
    """It must be a pairs of coordinates (lat., lon) even number. Odd number found!"""
    pass

# coordinates regex for degree minutes seconds and miliseconds 
regex_dmsms = re.compile('(-)*(\d{1,2})\D+(\d{1,2})\D+(\d{1,2})\D+(\d{1,3})')
regex_dmsms_ = re.compile('([-+]);(\d{1,3});(\d{1,2});(\d{1,2});(\d{1,3})')     # crazy SIGAREAS format
# 10^-6 microseconds - 10^-5 seconds is 10 * microseconds - 
# 5 decimal places - GTM PRO format
regex_dms10us = re.compile('(-)*(\d{1,2})\D+(\d{1,2})\D+(\d{1,2})[\.\,](\d{5})')

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
    llcs = np.array(coords, dtype=np.double) #lat, lon = coords[::2],  coords[1::2]     
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

# gtm pro header allways SIRGAS 2000
gtmpro_header = """Version,212

SIRGAS 2000,289, 6378137, 298.257222101, 0, 0, 0
USER GRID,0,0,0,0,0

"""

def formatMemorial(latlon, fmt='sigareas', close_poly=False, view=False,
                    save=False, filename='MEMOCOORDS.TXT'):
    """
    Create formated text file poligonal ('Memorial Descritivo') 

    * latlon: numpy array from `memorialRead`
        [[lat,lon]...]

    coordinate have 5 fields:  [ signal +/- 1, degree, minutes, seconds, miliseconds ]
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
        # turn in [ signal +/- 1, degree, minutes, seconds, miliseconds ] array
        latlon = np.array(list(map(ddegree2dmsms, latlon.flatten()))).reshape(-1, 2, 5)
    if close_poly and (not np.alltrue(latlon[0] == latlon[-1])):  
        latlon = np.append(latlon, latlon[0:1], axis=0) # add first point to the end        
    fmtlines = ""
    if fmt == "sigareas":
        data = latlon.reshape(-1, 5)
        data[:, 4] = np.round(data[:, 4], 0) # round to 0 decimal places
        lines = data.reshape(-1, 10).astype(int).tolist()
        for line in lines:
            # -;019;44;18;173;-;044;17;41;702
            s0, s1 = map(str, [line[0], line[5]]) # to not print -1,+1 only - or +
            s0, s1 = s0[0], s1[0]            
            fmtlines += "{0:};{3:03};{4:02};{5:02};{6:03};{1:};{8:03};{9:02};{10:02};{11:03}\n".format(
                    s0, s1, *line) # for the rest * use positional arguments ignoring the old signals args [2, 7]           
    elif fmt == "gtmpro":
        fmtlines += gtmpro_header
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
    if debug:
        # not dists: # no distances means all zero - already rumos verdadeiros            
        print("Changes statistics min (m) : {:2.2f}  p50: {:2.2f} max: {:2.2f}".format(
            *(np.percentile(dists, [0, 50, 100]))), file=sys.stderr)
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
    if test_verd(vertices_new) == False:
        raise NotImplemented("failed check 'rumos verdadeiros'")     # 'rumos verdadeiros' NSEW check
    if close_poly: # close polygon back
        vertices_new = np.append(vertices_new, vertices_new[0:1], axis=0)
    if view:
        print(vertices_new)
    else: 
        return vertices_new





