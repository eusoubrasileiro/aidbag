from pyproj import CRS, Transformer
import numpy as np
import re 

from .geographic import (
    wgs84Inverse, 
    wgs84Direct,
    wgs84PolygonAtributes
    )

from .util import (
    forceverdPoligonal,
    formatMemorial    
    )

from .shapes import (
    savePolygonWGS84,
    savePointsWGS84
)


### Memorial descritivo através de PA e survey de estação total
# might be useful https://github.com/totalopenstation

CRS_SAD69_96 = "+proj=longlat +ellps=aust_SA +towgs84=-67.35,3.88,-38.22,0,0,0,0 +no_defs" # sad69(96) lat lon
CRS_SIRGAS2000 = "+proj=longlat +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +no_defs"

def memoPoligonPA(filestr, shpname='memopa', crs=None, geodesic=True,
        cfile=True, verbose=False, saveshape=True,  wincpp=True, verdadeiro=True, tolerance=1e-6,
        snap_points=[], snap_dist=10.):
    """
    Cria sequencia de vertices a partir de string de arquivo texto de
    memorial descritivo da poligonal de requerimento usando ponto de amarração.
    Vertices output em SIRGAS 2000.

    crs: crs do memorial default p/ SAD69(96)
        prj4 string
        based on
        https://wiki.osgeo.org/wiki/Brazilian_Coordinate_Reference_Systems#Ellipsoids_in_use
        ....

    snap_points: list [ [lat, lon] ]
        snap coordinate considering `snap_dist` to ONLY ONE point and
        recalculate walking vertices
        TODO: implement for 2/3 ... more points


    geodesic: default True  - calculos geodésicos
                      False - calculos planimetricos UTM projetado



    ### Calculos Geodésicos - SIGAREAS/SCM
    Usa pacote Geographiclib (Charles F. F. Karney)
    p/ calculos e distâncias, azimutes geodesicos (isso é direto no elipsoide)
    usa matemática esférica/elipsoidal para calculo direto ou inverso.

    ### Calculos Planimetricos
    Utiliza pacote Pyproj/PRJ4 para projeção em UTM e calculo distâncias. azimutes
    considerando o norte do GRID UTM.

    ### Transformações entre datuns
    Transformaçao de coordenadas entre datuns utilizando pacote Pyproj/PRJ4.
    Testado dando resultados identicos ao do site INPE Calculadora http://www.dpi.inpe.br/calcula/
    Mais precisos que o CONVNAV.

    Testado contra o CONVNAV dandos resultados na ordem em média < 1 metro de diferença.
    Quase certeza que é diferença de abordagem provavelmente na hora de contruir a navegação.
    CONVNAV mantem longitude constante quando N, S rumos verdadeiros.

    cfile: default True
        Cria arquivo COORDS.txt adequado
        para inserir no SIGAREAS->Administrador->Inserir Poligonal

    wincpp : default True
        use geographiclib compiled on windows/pybind11 vstudio by Andre
        8th order

    verdadeiro: default True
        force 'rumos verdadeiros'
        force decimal coordinates lat, lon to repeat last lat, lon

    tolerance: default 1e-6 (decimal degrees)
        diference to previous lat or lon to force 'verdadeiro' option
        WARNING:
        If navigation is very detailed this parameter may change it COMPLETELY

    Conforme Emilio todo o banco de dados do SCM foi convertido
    considerando que os dados já estavam no datum SAD69(96).

    Exemplos:

    1. Com rumos verdadeiros

    -20 14 14 3  # latitude do Ponto de Amarração
    -43 52 50 2  # longitude do Ponto de Amarração

    1000 SW 75 15  # distancia (metros) direção grau-minutos para o primeiro vértice
    2200 E         # incremento direcional a partir do primeiro vértice
    1350 S
    2200 W
    1350 N

    2. Com rumos diversos

    -20 16 38 4
    -43 55 15 0

    4836 NE 51 12
    286  NW 00 00
    302  SE 90 00
    140  NW 00 00

    Aproximadamente 0.001 (1 mm) walk changes 8 casa ou 10-8 grau decimal.
    """
    wincpp = wincpp
    if crs is not None:
        crs = CRS(crs)
    else:
        # older sad69
        #crs = CRS('+proj=longlat +ellps=aust_SA +towgs84=-66.87,4.37,-38.52,0,0,0,0 +no_defs')
        crs = CRS(CRS_SAD69_96) # sad69(96) lat lon
    print("Input CRS: ", crs)
    lines = filestr.split('\n')
    # PA information
    latpa = get_graus(lines[0])
    lonpa = get_graus(lines[1])
    print("Input lat, lon : {:.8f} {:.8f} {:}".format(latpa, lonpa, 'SAD69(96)'))
    print("lat {:} {:} {:} {:} | lon {:} {:} {:} {:}".format(
        *decdeg2dmsd(latpa), *decdeg2dmsd(lonpa)))
    # convert PA geografica de datum de SAD69(96)  para SIRGAS 2000
    # conforme Emilio todo o banco de dados do SCM foi convertido
    # considerando que os dados eram SAD69(96)
    sirgas = CRS_SIRGAS2000
    tosirgas = Transformer.from_crs(crs, sirgas)
    lonpa, latpa =  tosirgas.transform(lonpa, latpa)
    print("Input lat, lon: {:.8f} {:.8f} {:}".format(latpa, lonpa, 'SIRGAS2000'))
    print("lat {:} {:} {:} {:} | lon {:} {:} {:} {:}".format(
        *decdeg2dmsd(latpa), *decdeg2dmsd(lonpa)))

    # Projection transformation
    # get adequate UTM zone by using the simple equation
    # 1 + np.floor((-44 + 180)/6) % 60
    zone = 1 + np.floor((lonpa + 180)/6) % 60
    utm_crs = CRS("+proj=utm +zone={:} +south +units=m +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +no_defs".format(zone))
    # custom CRS LTM primeiro vertice
    # utm_crs = """+proj=tmerc +ellps=WGS84 +datum=WGS84 +units=m +no_defs +lon_0={:} +x_0=50000 +y_0=0 +k_0=0.9996
    #+towgs84=0,0,0,0,0,0,0""".format(lonpa)
    # Lambert Azimuthal Equal Area
    # utm_crs = """+proj=laea +ellps=WGS84 +datum=WGS84 +units=m +no_defs +lon_0={:} +lat_0={:} +x_0=0 +y_0=0 +towgs84=0,0,0,0,0,0,0""".format(lonpa, latpa)
    if not geodesic:
        print("PRJ4 string UTM:", utm_crs)
    proj = Transformer.from_crs(sirgas, utm_crs)
    deproj = Transformer.from_crs(utm_crs, sirgas) # Deprojection

    # read all lines of segments defining the polygon
    # assumed clockwise
    directions_xy = []
    directions_az = []
    lines = lines[3:]
    idx = 0
    print("First vertex at index 1, 0 is PA")
    for line in lines:
        dist, quad, angle = memoLineRead(line)
        azimuth = getazimuth(quad, angle)
        dx, dy = projectxy(dist, quad, angle)
        directions_xy.append([dx, dy])
        directions_az.append([dist, azimuth])
        print("{:3d} : {:>+9.3f} {:>5} {:>+7.2f} {:>+7.2f} {:>+9.2f} {:>+9.2f}".format(idx, dist, quad.ljust(5), angle, azimuth, dx, dy))
        idx += 1

    vertices_dg = []
    vertices_utm = []
    if geodesic: # geodesic calculations # go to first vertex
        # assume clockwise, assume closed polygon otherwise BROKE
        first_vertex = geodesic_walk((latpa, lonpa), directions_az[:1])[1]
        # ignora  PA not vertex, remove from directions also
        directions_az = directions_az[1:]
        vertices_dg = geodesic_poly_walk(first_vertex, directions_az, 0)

        rsnap_points = [] # new reference points from snapping points
        if snap_points:
            for spoint in snap_points: # list of lat, lon points
                for i in range(len(vertices_dg)):
                    distance = wgs84Inverse(*spoint, *vertices_dg[i])
                    #print(distance)
                    if(distance < snap_dist):
                        print("Snaping: distance from snap-vertex : Lat {:>4.8f} Lon {:>4.8f} to "
                                "vertex : {:>3d} is {:>5.3f} m".format(*spoint, i, distance))
                        #print("accept?")
                        rsnap_points.append([i, spoint])
            if rsnap_points: # at least one acceptable snap_point
                print("Recalculating vertices")
                if len(rsnap_points) == 1:
                    vertices_dg = geodesic_poly_walk(rsnap_points[0][1],
                                            directions_az, rsnap_points[0][0])

        # create UTM equivalents
        for vertex in vertices_dg:
            utmx, utmy = proj.transform(vertex[1], vertex[0])
            vertices_utm += [utmx, utmy]
            print("UTM X {:10.3f} Y {:10.3f} Lat {:4.8f} Lon {:4.8f}".format(
                utmx, utmy, vertex[0], vertex[1]))

    else: # planimetric calculations
        xpa, ypa =  proj.transform(lonpa, latpa)
        cx, cy = xpa, ypa
        for segment in directions_xy:
            dx, dy = segment
            cx += dx; cy += dy
            vertices_utm.append([cx, cy])
        for vertex in vertices_utm:
            lon, lat = deproj.transform(vertex[0], vertex[1])
            vertices_dg.append([lat, lon])
            print("UTM X {:10.3f} Y {:10.3f} Lat {:4.8f} Lon {:4.8f}".format(
                vertex[0], vertex[1], lat, lon))

    if verdadeiro: # force verdadeiro
        vertices_dg = forceverdPoligonal(vertices_dg, tolerance).tolist()

    if cfile:
        formatMemorial(vertices_dg, verbose=verbose, endfirst=True)

    # Create polygon shape file
    if saveshape:
        savePolygonWGS84(vertices_dg, shpname)
        savePointsWGS84(vertices_dg, shpname+'p')

    if verbose:
        nvertices, perimeter, area = wgs84PolygonAtributes(vertices_dg)
        print("nvertices {:} area {:>9.8f} perimeter {:>9.8f}".format(
                nvertices, area, perimeter))

    return vertices_dg, vertices_utm


def memoLineRead(line):
    """
    read line like:

        4836 NE 51 12 # rumos diversos
    or
        1350 S # rumos verdadeiros

    returns:
        dist, quadrant, angle
    """
    # replace ',' with '.' decimal only . on python
    line = line.replace(',', '.')
    result = re.findall('(\d+\.*\d*)\W*([NSEW]+)\W*(\d{1,2})\D+(\d{1,2})*', line) # rumos diversos
    if not result: # rumos verdadeiros
        # an azimuth is defined as a horizontal angle measured clockwise
        # from a north base line or meridian
        result = re.findall('(\d+\.*\d*)\W*([NSEW]+)', line)
    if not result:
        raise Exception("Cant parse line for dist/azimuth! Empty line?")
    result = result[0] # list of 1 item
    dist, quad = float(result[0]), result[1] # distance and quadrant
    angle = 0.0 # angle may or may not be present
    if len(result) > 2:
        angle = float(result[2])
        if len(result) == 4:
            angle += float(result[3])/60.

    return dist, quad, angle

def projectxy(dist, quad, ang):
    """
    Recebe distancia, quadrante e angulo com relação a N-S
        2153, SE, 17.05
    Retorna projeções em DX, DY
    """
    angle = ang*np.pi/180.
    dx, dy = np.sin(angle)*dist, np.cos(angle)*dist
    # rumos diversos
    if quad == 'SW':
        return -dx, -dy
    if quad == 'SE':
        return +dx, -dy
    if quad == 'NE':
        return +dx, +dy
    if quad == 'NW':
        return -dx, +dy
    # rumos verdadeiros, angulo ignorado
    if quad == 'N':
        return 0.0, +dist
    if quad == 'W':
        return -dist, 0.0
    if quad == 'S':
        return 0.0, -dist
    if quad == 'E':
        return +dist, 0.0

def getazimuth(quad, ang):
    """
    converte
        SE, 17.05
    em azimute com relação ao norte e clock-wise
    geographiclib convention
    range [+180,-180]
    """
    # rumos diversos
    if quad == 'SW':
        return -180.+ang
    if quad == 'SE':
        return 180.-ang
    if quad == 'NE':
        return ang
    if quad == 'NW':
        return -ang
    # rumos verdadeiros
    if quad == 'N':
        return 0.
    if quad == 'S':
        return 180.
    if quad == 'W':
        return -90.
    if quad == 'E':
        return  90.

def get_graus(coord):
    """parse coordinates string like:
    -20 14 14 3  # degree, minute, second and dec of second
    return: decimal degree
    """
    dg, mn, sc, dsc =  re.findall('(-*\d{1,2})\D+(\d{1,2})\D+(\d{1,2})\D+(\d*)', coord)[0]
    dg = float(dg)
    # case sign is 0, will be 0 .. set to 1
    sign = 1 if np.sign(dg) == 0 else np.sign(dg)
    dsc = float(dsc)/(10.**len(dsc))
    print(sign, dg, mn, sc, dsc)
    return dg + sign*float(mn)/60. + sign*float(sc)/3600. + sign*dsc/3600.

def decdeg2dmsd(dd):
    negative = dd < 0
    dd = abs(dd)
    minutes,seconds = divmod(dd*3600,60)
    degrees,minutes = divmod(minutes,60)
    if negative:
        if degrees > 0:
            degrees = -degrees
        elif minutes > 0:
            minutes = -minutes
        else:
            seconds = -seconds
    dseconds = seconds - int(seconds)
    return (int(degrees), int(minutes), int(seconds), int(1000*dseconds))


def geodesic_walk(rpoint, directions, inverse=False, force_verd=True):
        """create points starting at rpoint for all directions passed

        rpoint : lat, lon
            reference point

        directions: list of lists
            [distance, angle]

        inverse : bool
            wether walking backwards, -distance

        force_verd:
            wether repeat last latitude or longitude based on
            'rumos verdadeiros'
        """
        #The point 20000 km SW of Perth, Australia (32.06S, 115.74E) using Direct():
        # g = geod.Direct(-32.06, 115.74, 225, 20000e3)
        # print("The position is ({:.8f}, {:.8f}).".format(g['lat2'],g['lon2']))
        vertices = []
        clat, clon = rpoint # start point
        vertices.append([clat, clon])

        inverse = -1 if inverse else 1
        for segment in directions:
            dist, azimuth = segment
            clat, clon = wgs84Direct(clat, clon, azimuth, dist*inverse)
            if force_verd:
                if azimuth == 0. or azimuth == 180.: # walking N/S
                    _, clon = vertices[-1] # ignore computed lon
                elif azimuth == -90. or azimuth == 90.: # walking W,E
                    clat , _ = vertices[-1] # ignore computed lat
            vertices.append([clat, clon])
        return vertices

def geodesic_poly_walk(start_vertex, directions, start_idx=0, closed=True):
    """
    create vertices of polygon walking using directions from one start_vertex
    start_vertex: (lat, lon)
        coordinates of starting point
    start_idx : default 0
        specify where in the directions list is the start_vertex
        (max value len(directions) - 1)
    Note: clockwise directions ONLY
    """
    # rool directions to specified start_vertex using start_idx
    # start_idx=0 does nothing
    directions = directions[start_idx:] + directions[:start_idx]
    # simpler approach but second is better compared with CONVNAV
    # vertices_dg = geodesic_walk(first_vertex, directions_az)
    # aproach going to both sides from first vertex
    ndirs = len(directions)
    nfst = ndirs//2 # first group number of directions
    nscd = ndirs-nfst # second group number of directions
    fst_group = geodesic_walk(start_vertex, directions[:nfst])
    scd_group = geodesic_walk(start_vertex, directions[nfst:][::-1], inverse=True)
    mid_vertex = np.mean([fst_group[-1]]+[scd_group[-1]], axis=0).tolist() # it is better!
    vertices_dg = fst_group[:-1] + [mid_vertex] + scd_group[1:-1][::-1]
    return vertices_dg







