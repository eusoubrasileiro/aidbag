import os 
import pytest 
import numpy as np
import numpy.testing as npt
import xml.etree.ElementTree as ET

from poligonal.util import (
    readMemorial,
    formatMemorial,
    forceverdPoligonal
    )

from poligonal.memorial import (
    Poligon    
    )

from poligonal.geographic import (
    wgs84PolygonAttributes
    )


# test to be included
def test_memoPoligonPA():
    """Compara resultados Python Geographiclib vs CONVNAV.
    Exemplo de 1 processo simples retangular abaixo
    This package has twice the precision of convnav for example bellow.
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
    thruth_area = 590*780*0.0001

    poligon = Poligon.from_old_memo(filestr)    
    vertices = poligon.data

    convnav_vertices = [[-21.34129611, -44.95506889],
        [-21.34662472, -44.95506889],
        [-21.34662444, -44.96258861],
        [-21.34129583, -44.96258861]]

    convnav_num, convnav_perim, convnav_area = wgs84PolygonAttributes(convnav_vertices)
    py_num, py_perim, py_area = wgs84PolygonAttributes(vertices.tolist())

    print("convnav errors - area {:>+9.8f} perimeter {:>+9.8f}".format(
            thruth_area-convnav_area, thruth_perimeter-convnav_perim))

    print("python  errors - area {:>+9.8f} perimeter {:>+9.8f}".format(
            thruth_area-py_area, thruth_perimeter-py_perim))


# test to be included
def test_memo_from_points():
    memorial_points = """-20°18'32''049	-43°24'42''792
    -20°18'46''682	-43°24'42''792
    -20°18'46''682	-43°24'59''338
    -20°18'36''926	-43°24'59''338
    -20°18'36''925	-43°25'20''019
    -20°18'43''429	-43°25'20''020
    -20°18'43''428	-43°25'30''361
    -20°18'49''932	-43°25'30''361
    -20°18'49''931	-43°25'34''498
    -20°18'32''046	-43°25'34''496""" # don't needed to be closed. It will be closed.
    points = readMemorial(memorial_points, decimal=True)    
    poligon = Poligon.from_points(points)
    poligon.points_from_memo()    
    npt.assert_almost_equal(points, poligon.data[:-1], decimal=6)
    # import numpy as np 
    # np.abs(points-poligon.data[:-1])


# parse xml and create test data samples 
root = ET.parse(os.path.join(os.path.dirname(__file__), 'tests.xml'))
test_samples = [] 
test_names = []
for test in root.findall("test"):
    input, expected = list(test)
    # expected from xml comes with two \n begin and end  
    test_samples.append((input.text, input.attrib['type'], 
        expected.attrib['type'], expected.text.strip(), expected.attrib['nsew'] == 'true'))
    test_names.append(test.attrib['name'])    


@pytest.mark.parametrize("text, itype, otype, expected, nsew", test_samples, ids=test_names)
def test_memorial(text, itype, otype, expected, nsew):
     parsed_data = readMemorial(text, fmt=itype, decimal=True)
     if nsew:        
        parsed_data = forceverdPoligonal(parsed_data, debug=False)
     result = formatMemorial(parsed_data, fmt=otype)
     if otype == 'gtmpro': # uses '\r\n' as line ending 
        result = result.replace("\r\n", "\n") # since python string defaults to '\n'     
     assert(result == expected) 