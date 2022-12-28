# geopandas and pyproje area heavy dependencies
# and somewhat difficult to install
import numpy as np
import geopandas as gp
from shapely.geometry import Polygon, Point
import pyproj 
from ..scm.util import numberyearPname

CRS_SIRGAS2000 = "+proj=longlat +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +no_defs"


def savePolygonWGS84(vertices, shpname):
    vertices = np.array(vertices)
    temp = np.copy(vertices[:, 0])
    vertices[:, 0] = vertices[:, 1]
    vertices[:, 1] = temp
    gdfvs = gp.GeoSeries(Polygon(vertices))
    gdfvs.set_crs(pyproj.CRS.from_epsg(4326)) 
    gdfvs.to_file(shpname+'_poly')

def savePointsWGS84(vertices, shpname):
    gdfvs = gp.GeoSeries(list(map(Point, vertices)), index=np.arange(len(vertices)), 
        crs=pyproj.CRS.from_epsg(4326)) 
    gdfvs.to_file(shpname+'_points')

def readPolygon(shpname):
    """read a esri shape file and get its coordinates"""
    gdf = gp.read_file(shpname)
    lon = gdf.geometry.exterior.xs(0).coords.xy[0]
    lat = gdf.geometry.exterior.xs(0).coords.xy[1]
    points = np.array(list(zip(lat, lon)))
    return points

def readPolygonQuery(fname, processo='654/1938'):
    """read the SIGMINE shape esri file and the processo coordinates 
    after filtering by processo NUMERO & ANO"""
    shp = gp.read_file(fname)
    number, year = numberyearPname(processo, int)
    selected = shp.query("NUMERO == @number & ANO == @year")    
    if not len(selected) > 0:
        raise IndexError(f"Did not find processo {number}/{year}. Did you mistype?")
    coordinates = selected.geometry.apply(lambda x: np.array(x.exterior.coords)).values
    del shp 
    coordinates = np.vstack(coordinates) # turn nested list or arrays to multidim array
    return coordinates[:, :2][:, ::-1]
