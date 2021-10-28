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
# I could use a regex that supports both cases but I am not sure that's ideal 
#regex_dmsmsg = re.compile('([-+])*;*(\d{1,3})\D+(\d{1,2})\D+(\d{1,3})\D+(\d{1,3})')

def parse_coordinates(text, decimal=False):
    """parse coordinate pairs `text` string using regex 

    * text: str          
        -19°44'18''174 -44°17'45''410 -24°17'15''410 ...  
        or 
        -;019;44;18;173;-;044;17;41;702 ...
        or 
        -19 44 18 174 -44 17 45 410 -24 17 15 410 ...          
        # degree, minute, second and mili seconds   
    
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

    """
    regex = regex_dmsms
    if text.find('-;') != -1 or text.find('+;') != -1: # crazy SIGAREAS format
        regex = regex_dmsms_
    csparsed = re.findall(regex, text)
    coords = [ [int(sg+'1'), *map(int, [dg, mn, sc, msc])] 
                for sg, dg, mn, sc, msc in csparsed ]
    if len(csparsed)%2 != 0: # must be even lat, lon pairs        
        raise NotPairofCoordinatesError() 
    #lat, lon = coords[::2],  coords[1::2]  
    llcs = np.array(coords).reshape(-1, 2, 5)          
    if decimal:
        npl = llcs.reshape(-1, 5)
        # convert to decimal ignore signal than finally multiply by signal back
        npl = np.sum(npl*[0, 1., 1/60., 1/3600., 0.001*1/3600.], axis=-1)*npl[:,0]
        llcs = npl.reshape(-1, 2)
    return llcs 


def memorialRead(llstr, decimal=False):
    """
    Parse lat, lon string (`llstr`) #Aba Poligonal Scm#
    uses `parse_coordinates` that uses regex 
    generating numpy array of coordinates.     
    """
    return parse_coordinates(llstr, decimal)


def formatMemorial(latlon, endfirst=False, 
                    save=True, filename='MEMOCOORDS.TXT', verbose=True):
    """
    Create formated file poligonal ('Memorial Descritivo') to use on SIGAREAS
        SIGAREAS->Administrador->Inserir Poligonal|Corrigir Poligonal

    latlon: numpy array from `memorialRead`
        [[lat,lon]...] 

    endfirst: default True
        copy first point in the end
    
    file: default
        save a file with this poligonal
    
    filename: str
        name of filename to save this poligonal
    """
    lines = []
    if isinstance(latlon, np.ndarray):
        lines = latlon.reshape(-1, 10).tolist()
    else:
        return
    if endfirst:  # copy first point in the end
        lines.append(lines[0])
    if save:
        f = open(filename.upper(), 'w') # must be CAPS otherwise can't upload
    for line in lines:
        s0, s1 = map(str, [line[0], line[5]]) # to not print -1,+1 only - or +
        fline = "{0:};{3:03};{4:02};{5:02};{6:03};{1:};{8:03};{9:02};{10:02};{11:03}".format(
        s0[0], s1[0], *line) # for the rest * use positional arguments ignoring the old signals args [2, 7]   
        if save:
            f.write(fline+'\n')
        if verbose:
            print(fline)
    if save:
        print("Output filename is: ", filename.upper())
        f.close()


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





