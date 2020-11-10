import re
from pyproj import CRS
from pyproj import Transformer
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info
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

def memoPoligonPA(filestr, crs=None, cfile=True):
    """
    Cria sequencia de vertices a partir de string de arquivo texto de
    memorial descritivo da poligonal de requerimento usando ponto de amarração.
    Vertices output em SIRGAS 2000.

    crs: default p/ SAD69(96)
        prj4 string
        based on
        https://wiki.osgeo.org/wiki/Brazilian_Coordinate_Reference_Systems#Ellipsoids_in_use
        ....

    Dando resultados identicos ao do site INPE Calculadora
    http://www.dpi.inpe.br/calcula/
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
    print("Input lat, lon : {:.6f} {:.6f} {:}".format(latpa, lonpa, 'SAD69(96)'))
    print("lat {:} {:} {:} {:} | lon {:} {:} {:} {:}".format(
        *decdeg2dmsd(latpa), *decdeg2dmsd(lonpa)))
    # convert PA geografica de datum de SAD69(96)  para SIRGAS 2000
    # conforme Emilio todo o banco de dados do SCM foi convertido
    # considerando que os dados eram SAD69(96)
    sirgas = CRS("+proj=longlat +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +no_defs")
    tosirgas = Transformer.from_crs(crs, sirgas)
    lonpa, latpa =  tosirgas.transform(lonpa, latpa)
    print("Input lat, lon: {:.6f} {:.6f} {:}".format(latpa, lonpa, 'SIRGAS2000'))
    print("lat {:} {:} {:} {:} | lon {:} {:} {:} {:}".format(
        *decdeg2dmsd(latpa), *decdeg2dmsd(lonpa)))
    # Projection transformation
    # get adequate UTM zone
    # by using the simple Formulario
    # 1 + np.floor((-44 + 180)/6) % 60
    zone = 1 + np.floor((lonpa + 180)/6) % 60
    utm_crs = CRS("+proj=utm +zone={:} +south +units=m +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +no_defs".format(zone))
    print("PRJ4 string UTM:", utm_crs)
    proj = Transformer.from_crs(sirgas, utm_crs)
    xpa, ypa =  proj.transform(lonpa, latpa)
    print("PA UTM {:.3f} {:.3f} {:}".format(xpa, ypa, 'SIRGAS'))
    # Deprojection transformation UTM to Geographic
    deproj =Transformer.from_crs(utm_crs, sirgas)

    lines = lines[3:]
    vertices_utm = []
    cx, cy = xpa, ypa
    for line in lines:
        # replace ',' with '.' decimal only . on python
        line = line.replace(',', '.')
        result = re.findall('(\d+\.*\d*)\W*([NSEW]+)\W*(\d{1,2})\D+(\d{1,2})*', line) # rumos diversos
        if not result: # rumos verdadeiros
        # an azimuth is defined as a horizontal angle measured clockwise
        # from a north base line or meridian
            result = re.findall('(\d+\.*\d*)\W*([NSEW]+)', line)
        if not result:
            break
        result = result[0] # list of 1 item
        dist, quad = float(result[0]), result[1] # distance and quadrant
        angle = 0.0 # angle may or may not be present
        if len(result) > 2:
            angle = float(result[2])
            if len(result) == 4:
                angle += float(result[3])/60.
        dx, dy = projectxy(dist, quad, angle)
        print("{:>+9.3f} {:<4} {:>+4.2f} {:>+9.2f} {:>+9.2f}".format(dist, quad.ljust(8), angle, dx, dy))
        cx += dx; cy += dy
        vertices_utm.append([cx, cy])

    vertices_degree = []
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
        vs = vertices_degree.copy()
        vs.append(vs[1])
        for v in vs[1:]:
            line = '{:} {:} {:} {:} {:} {:} {:} {:} \n'.format(
                *decdeg2dmsd(v[0]), *decdeg2dmsd(v[1]))
            strfile = strfile + line
        fformatPoligonal(strfile)

    return vertices_degree, vertices_utm

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
