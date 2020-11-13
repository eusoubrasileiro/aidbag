import re
import pyproj
from pyproj import CRS
from pyproj import Transformer
from geographiclib import geodesic as gd
from geographiclib import polygonarea as pa
from shapely.geometry import Polygon
import geopandas as gp
import numpy as np

# Ignorando sinal -S e -O latitude longitado considerando somente negativos
# o sinal é inserido somente no arquivo antes do ';'
reg = re.compile('\D*(\d{2})\D*(\d{2})\D*(\d{2})\D*(\d{3,})')
def fformatPoligonal(mlinestring, filename='CCOORDS.TXT', verbose=True):
    "formated file de poligonal para uso em SIGAREAS->Administrador->Inserir Poligonal"
    #reg.findall(string)[:3]
    fields = reg.findall(mlinestring)
    if len(fields)%2 != 0:
        print('Algo errado faltando campo em coordenada (lat. ou lon.)')
    else:
        with open(filename.upper(), 'w') as f: # must be CAPS otherwise system doesnt load
            for i in range(0,len(fields)-1, 2):
                lat = "-;{:03};{:02};{:02};{:03};-;".format(*list(map(int,fields[i])))
                lon = "{:03};{:02};{:02};{:03}".format(*list(map(int,fields[i+1])))
                f.write(lat+lon)
                f.write('\n')
                if verbose:
                    print(lat+lon)
    print("Output filename is: ", filename.upper())



### Memorial descritivo através de PA e survey de estação total
# might be useful https://github.com/totalopenstation

def memoPoligonPA(filestr, shpname='memopa', crs=None, geodesic=True, cfile=True, verbose=False, saveshape=True):
    """
    Cria sequencia de vertices a partir de string de arquivo texto de
    memorial descritivo da poligonal de requerimento usando ponto de amarração.
    Vertices output em SIRGAS 2000.

    crs: crs do memorial default p/ SAD69(96)
        prj4 string
        based on
        https://wiki.osgeo.org/wiki/Brazilian_Coordinate_Reference_Systems#Ellipsoids_in_use
        ....

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

    """
    if crs is not None:
        crs = CRS(crs)
    else:
        # older sad69
        #crs = CRS('+proj=longlat +ellps=aust_SA +towgs84=-66.87,4.37,-38.52,0,0,0,0 +no_defs')
        crs = CRS("+proj=longlat +ellps=aust_SA +towgs84=-67.35,3.88,-38.22,0,0,0,0 +no_defs") # sad69(96) lat lon
    print("Input CRS: ", crs)
    lines = filestr.split('\n')
    # PA information
    latpa = get_graus(lines[0])
    lonpa = get_graus(lines[1])
    print("Input lat, lon : {:.7f} {:.7f} {:}".format(latpa, lonpa, 'SAD69(96)'))
    print("lat {:} {:} {:} {:} | lon {:} {:} {:} {:}".format(
        *decdeg2dmsd(latpa), *decdeg2dmsd(lonpa)))
    # convert PA geografica de datum de SAD69(96)  para SIRGAS 2000
    # conforme Emilio todo o banco de dados do SCM foi convertido
    # considerando que os dados eram SAD69(96)
    sirgas = CRS("+proj=longlat +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +no_defs")
    tosirgas = Transformer.from_crs(crs, sirgas)
    lonpa, latpa =  tosirgas.transform(lonpa, latpa)
    print("Input lat, lon: {:.7f} {:.7f} {:}".format(latpa, lonpa, 'SIRGAS2000'))
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
    print("PRJ4 string UTM:", utm_crs)
    proj = Transformer.from_crs(sirgas, utm_crs)
    deproj = Transformer.from_crs(utm_crs, sirgas) # Deprojection

    vertices_degree = []
    vertices_utm = []
    if geodesic: # geodesic calculations
        geod = gd.Geodesic.WGS84 # define the WGS84 ellipsoid - SIRGAS 2000 same
        #The point 20000 km SW of Perth, Australia (32.06S, 115.74E) using Direct():
        # g = geod.Direct(-32.06, 115.74, 225, 20000e3)
        # print("The position is ({:.8f}, {:.8f}).".format(g['lat2'],g['lon2']))
        clat, clon = latpa, lonpa # start point
        vertices_degree.append([clat, clon])
        lines = lines[3:]
        for line in lines:
            dist, quad, angle = memoLineRead(line)
            azimuth = getazimuth(quad, angle)
            print("{:>+9.3f} {:<4} {:>+4.2f} {:>+9.2f}".format(dist, quad.ljust(8), angle, azimuth))
            g = geod.Direct(clat, clon, azimuth, dist)
            vertices_degree.append([g['lat2'], g['lon2']])
            clat, clon = g['lat2'], g['lon2']
        for vertex in vertices_degree:
            utmx, utmy = proj.transform(vertex[1], vertex[0])
            vertices_utm.append([utmx, utmy])
            print("UTM X {:10.3f} Y {:10.3f} Lat {:4.7f} Lon {:4.7f}".format(
                utmx, utmy, vertex[0], vertex[1]))

    else: # planimetric calculations
        xpa, ypa =  proj.transform(lonpa, latpa)
        vertices_utm.append([xpa, ypa])
        lines = lines[3:] #
        cx, cy = xpa, ypa
        for line in lines:
            dist, quad, angle = memoLineRead(line)
            dx, dy = projectxy(dist, quad, angle)
            print("{:>+9.3f} {:<4} {:>+4.2f} {:>+9.2f} {:>+9.2f}".format(dist, quad.ljust(8), angle, dx, dy))
            cx += dx; cy += dy
            vertices_utm.append([cx, cy])
        for vertex in vertices_utm:
            lon, lat = deproj.transform(vertex[0], vertex[1])
            vertices_degree.append([lat, lon])
            print("UTM X {:10.3f} Y {:10.3f} Lat {:4.7f} Lon {:4.7f}".format(
                vertex[0], vertex[1], lat, lon))

    if cfile:
        # print coordendas format fformatPoligonal
        # possa criar um arquivo para inserier poligonal
        strfile = ''
        # fechamento perfeito primeiro ponto e
        # ignora primeiro (PA) - MUST BE rumos diversos
        vs = vertices_degree.copy()[1:]
        vs.append(vs[1])
        for v in vs[1:]:
            line = ('{:03d} {:02d} {:02d} {:03d} '*2).format(
                *decdeg2dmsd(v[0]), *decdeg2dmsd(v[1]))
            if verbose:
                print(line)
            strfile = strfile + "\n" + line
        fformatPoligonal(strfile)

    # Create polygon shape file
    if saveshape:
        vertices = np.array(vertices_degree)
        temp = np.copy(vertices[:, 0])
        vertices[:, 0] = vertices[:, 1]
        vertices[:, 1] = temp
        gdfvs = gp.GeoSeries(Polygon(vertices))
        gdfvs.set_crs(pyproj.CRS("""+proj=longlat +ellps=GRS80 +towgs84=0,0,0 +no_defs""")) # SIRGAS 2000
        gdfvs.to_file(shpname+'.shp')

    return vertices_degree, vertices_utm

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
    """
    # rumos diversos
    if quad == 'SW':
        return 180.+ang
    if quad == 'SE':
        return 180.-ang
    if quad == 'NE':
        return ang
    if quad == 'NW':
        return -ang
    # rumos verdadeiros
    if quad == 'N':
        return 0.
    if quad == 'W':
        return -90.
    if quad == 'S':
        return 180.
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


## Tests



def test_memoPoligonPA():
    """Testa código
    Compara resultados Python Geographiclib vs CONVNAV.
    Exemplo de 1 quadrado abaixo
    """
    # sample square
    filestr="""-21 19 20 0
    -44 57 38 6

    2153 SE 17 03
    590 S
    780 W
    590 N
    780 E"""
    thruth_perimeter = 590*2+780*2
    thruth_area = 46.02

    vertices, utm =  memoPoligonPA(filestr, geodesic=True, cfile=False)
    convnav_vertices = np.array([[-44.955068889, -21.341296111],
        [-44.955068889, -21.346624722],
        [-44.962588611, -21.346624444],
        [-44.962588611, -21.341295833]])

    geoobj = gd.Geodesic(gd.Constants.WGS84_a, gd.Constants.WGS84_f)
    poly = pa.PolygonArea(geoobj)
    for p in convnav_vertices:
        poly.AddPoint(*p[::-1])
    convnav_num, convnav_perim, convnav_area = poly.Compute(True)
    convnav_area = convnav_area*10**(-4) # to hectares

    poly = pa.PolygonArea(geoobj)
    for p in vertices[1:-1]:
        poly.AddPoint(*p)
    poly.Compute(True)
    py_num, py_perim, py_area = poly.Compute(True)
    py_area = py_area*10**(-4) # to hectares

    print("convnav errors - area {:>+9.6f} perimeter {:>+9.6f}".format(
            thruth_area-convnav_area, thruth_perimeter-convnav_perim))

    print("python  errors - area {:>+9.6f} perimeter {:>+9.6f}".format(
            thruth_area-py_area, thruth_perimeter-py_perim))
