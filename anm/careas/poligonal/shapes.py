# geopandas and pyproje area heavy dependencies
# and somewhat difficult to install
import numpy as np
import geopandas as gp
from shapely.geometry import Polygon, Point
import pyproj 

CRS_SIRGAS2000 = "+proj=longlat +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +no_defs"


def savePolygonWGS84(vertices, shpname):
    vertices = np.array(vertices)
    temp = np.copy(vertices[:, 0])
    vertices[:, 0] = vertices[:, 1]
    vertices[:, 1] = temp
    gdfvs = gp.GeoSeries(Polygon(vertices))
    gdfvs.set_crs(pyproj.CRS(CRS_SIRGAS2000)) 
    gdfvs.to_file(shpname+'.shp')

def savePointsWGS84(vertices, shpname):
    gdfvs = gp.GeoSeries(list(map(Point, vertices)), index=np.arange(len(vertices)))
    gdfvs.set_crs(pyproj.CRS(CRS_SIRGAS2000)) 
    gdfvs.to_file(shpname+'points.shp')

def readPolygonWGS84(shpname):
    gdf = gp.read_file(shpname)
    lon = gdf.geometry.exterior.xs(0).coords.xy[0]
    lat = gdf.geometry.exterior.xs(0).coords.xy[1]
    points = np.array(list(zip(lat, lon)))
    return points