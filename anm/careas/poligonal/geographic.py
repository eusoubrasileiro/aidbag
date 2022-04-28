# wrapper for geographiclib and my custom geographiclib 
# only compiled for windows VStudio C++ yet

from geographiclib import polygonarea # PyP package Geographiclib
from geographiclib.geodesic import Geodesic, Constants

wGS84 = Geodesic(Constants.WGS84_a, Constants.WGS84_f)   

def wgs84PoligonArea():
    return polygonarea.PolygonArea(wGS84)

def wgs84PolygonAttributes(cords):
    """Calculate number of vertices, perimeter and area (hectares) for passed polygon as coordinates.
    *cords: list
        [[lat,lon]...] 
    return nvertices, perimeter, area 
    """
    poly = wgs84PoligonArea()
    for p in cords:
        poly.AddPoint(*p)
    n, perim, area = poly.Compute(True)
    area = area*10**(-4) # to hectares
    return n, perim, area


try: 
    from . import geolib # Geographiclib wrapped in pybind11 by me py38

    geolib.WGS84() # it's not necessary it's default
    def wgs84Direct(lat1, lon1, az1, s12):    
        """Solve the direct geodesic problem where the length of the geodesic is specified in terms of distance."""           
        return geolib.Direct(lat1, lon1, az1, s12)

    def wgs84Inverse(lat1, lon1, lat2, lon2):
        """Solve the inverse geodesic problem return the length between two points."""
        return geolib.Inverse(lat1, lon1, lat2, lon2)

    def wgs84InverseAngle(lat1, lon1, lat2, lon2):
        "Solve the inverse geodesic problem return the angles pair (az1, az2) in the two points."
        return geolib.InverseAngle(lat1, lon1, lat2, lon2)

except:  # use geographiclib default PyP when not available    

    def wgs84Direct(lat1, lon1, az1, s12):                
        """Solve the direct geodesic problem where the length of the geodesic is specified in terms of distance."""   
        res = wGS84.Direct(lat1, lon1, az1, s12)
        return  res['lat2'], res['lon2']

    def wgs84Inverse(lat1, lon1, lat2, lon2):
        """Solve the inverse geodesic problem return the length between two points."""
        return wGS84.Inverse(lat1, lon1, lat2, lon2)['s12']

    def wgs84InverseAngle(lat1, lon1, lat2, lon2):
        res = wGS84.Inverse(lat1, lon1, lat2, lon2)
        return res['azi1'], res['azi2']
