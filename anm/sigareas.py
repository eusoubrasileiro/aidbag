import re
from pyproj import CRS
from pyproj import Transformer
import numpy as np

# Ignorando sinal -S e -O latitude longitado consierando somente negativos
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

def memoPoligonPA(crscodEPSG, filestr):
    """
    Cria sequencia de vertices a partir de arquivo texto de
    memorial descritivo da poligonal de requerimento usando ponto de amarração.

    crscodeEPSG:
        Código EPSG do CRS (sistema de coordendas) do datum do
        Ponto de Amarração na zona UTM correta.
        Eg. 5533
        <Projected CRS: EPSG:5533>
        Name: SAD69(96) / UTM zone 23S
        ....

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
    crs = CRS.from_epsg(crscodEPSG)# 5533) # UTM SAD69
    print(crs)
    print(crs.geodetic_crs)
    lines = filestr.split('\n')
    # PA information
    latpa = get_graus(lines[0])
    lonpa = get_graus(lines[1])
    print(latpa, lonpa)
    # Projection transformation
    proj = Transformer.from_crs(crs.geodetic_crs, crs)
    xpa, ypa =  proj.transform(latpa, lonpa)
    print("{:.1f} {:.1f}".format(xpa, ypa))
    # Deprojection transformation UTM to Geographic
    deproj =Transformer.from_crs(crs, crs.geodetic_crs)

    lines = lines[3:]
    vertices_utm = []
    cx, cy = xpa, ypa
    for line in lines:
        result = re.findall('(\d+)\W*([NSEW]+)\W*(\d{1,2})\D+(\d{1,2})*', line) # rumos diversos
        if not result: # rumos verdadeiros
            result = re.findall('(\d+)\W*([NSEW]+)', line)
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
        print("{:>+9.1f} {:<4} {:>+4.2f} {:>+9.2f} {:>+9.2f}".format(dist, quad.ljust(8), angle, dx, dy))
        cx += dx; cy += dy
        vertices_utm.append([cx, cy])

    vertices_degree = []
    for vetex in vertices_utm:
        lat, lon = deproj.transform(vetex[0], vetex[1])
        vertices_degree.append([lat, lon])
        print("UTM X {:10.1f} Y {:10.1f} Lat {:4.6f} Lon {:4.6f}".format(
            vetex[0], vetex[1], lat, lon))

    return vertices_degree, vertices_utm

def projectxy(dist, quad, ang):
    """
    Recebe distancia, quadrante e angulo com relação a N-S
        1000, SW, 75.15
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
