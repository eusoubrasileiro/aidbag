from .util import *

# simpler approach

#TODO implement same approach bellow two pathways
# but no reason since round angles/distances already deals with inprecision
def simple_memo_inverse(points, round_angle=True, round_dist=True):
    """
    memorial descritivo simples inverso a partir de coordenadas

    examplo:
        lat, lon primeiro ponto
        dist1 angle1
        dist2 angle2
        ...
    """
    dist_angle = []
    prev_point = points[0].tolist() # from numpy array
    dist_angle.append(prev_point)
    for point in points[1:]:
        dist = geocpp.Inverse(prev_point[0], prev_point[1], point[0],point[1])
        angle, _ = geocpp.InverseAngle(prev_point[0], prev_point[1], point[0],point[1])
        prev_point = point
        if round_angle:
            angle = round(angle)
        if round_dist:
            dist = round(dist)
        dist_angle.append([dist, angle])
    return dist_angle


def simple_memo_direct(smemo, repeat_end=False):
    """
    gera list de lat,lon a partir de memorial descritivo simples formato `simple_memo_inverse`
    """
    def direct(prevpoint, directions, revert=1):
        """revert=-1 go backwards"""
        points = []
        for dist, angle in directions:
            prevpoint = geocpp.Direct(*prevpoint, angle, dist*revert)
            points.append(prevpoint)
        return np.array(points)
    startpoint = smemo[0] # start
    directions = smemo[1:]
    # goind both sides - accuracy increase
    half = int(len(directions))//2
    ohalf = len(directions) - half
    points_fw = direct(startpoint, directions[:half]) # forward
    points_bk = direct(startpoint, directions[::-1][:ohalf], -1) # backwards
    # mid point is the average of foward and backward pathways more precision
    midpoint = (points_bk[-1]+points_fw[-1])/2.
    points = np.concatenate(([startpoint], points_fw[:-1], [midpoint], points_bk[:-1][::-1]))
    if repeat_end:
        points = np.concatenate((points,[points[0]]))
    return points


def simple_memo_newstart(smemo, index, start_point):
    """break walk way path simple_memo (memorial descritivo) at index-1
    and set new start coordinate point from there"""
    smemo = smemo.copy()
    smemo = smemo[1:] # discard original start
    # split at index since it's a walk way circular
    smemo = smemo[index-1:] + smemo[:index-1]
    # add new start point
    smemo = [start_point] + smemo
    return smemo




### Calcula informatino of displacement between
def translate_info(coords, ref_coords, displace_dist=1.5):
    """
    Get translate information using closest vertices from a reference polygon
    based on displace_dist

    coords: list
        coordinates to be translated
        [[lat0, lon0],[lat1, lon1]...]

    ref_coords: str or list
         memorial descritvo de referencia
         para translate das coordenadas
         ou
         list de coordenadas para translate

    displace_dist: default 1.5 (meters)
        displace distance
        maximum distance for translate coordinates (meters)
        only first 1 point will be used as reference

    returns: tuple
        - coordinates of vertex to be used as new start reference
        - index at coords path to be replaced by this
    """
    ref_points = ref_coords.copy()
    points = coords.copy()
    if isinstance(ref_points, str):
        ref_points = memorialRead(ref_points, decimal=True, verbose=True)
    elif( (isinstance(ref_points, list) or isinstance(ref_points, np.ndarray)) and
        (isinstance(points, list) or isinstance(points, np.ndarray)) ):
        pass
    else:
        print("Invalid input formats")
        return
    refs = []
    k=0
    for j, ref_point in enumerate(ref_points):
        for i, point in enumerate(points):
            distance = GeoInverseWGS84(*ref_point, *point)
            #print(distance)
            if(distance < displace_dist):
                angle, _ = geocpp.InverseAngle(*ref_point, *point)
                print("{:>3d} - distance is {:>+5.3f} m az. angle (degs) is {:>+4.3f} " "from ref-vertex {:>3d} : Lat {:>4.9f} Lon {:>4.9f} to "
                "vertex {:>3d} : Lat {:>4.9f} Lon {:>4.9f} ".format(k+1, distance, angle,
                     j+1, *ref_point, i+1, *point))
                k += 1 # another vertex possible to be used as reference for translation
                refs.append([ref_point, i+1])
    print("Choose which to use as a reference vertex")
    index = -1
    index = int(input())-1
    return refs[index][0], refs[index][1]

# draft version
# TODO make it better with new uses
def memorial_acostar(memorial, memorial_ref, reference_dist=50, mtolerance=0.5):
    """
    Acosta `memorial` à algum ponto escolhido da `memorial_ref`

    memorial_ref : str
        deve ser copiado da aba-poligonal

    memorial: str/list/np.ndarray

    """
    if isinstance(memorial_ref, str):
        ref_points = memorialRead(memorial_ref, decimal=True, verbose=False)
    else:
        print('memorial_ref : deve ser copiado da aba-poligonal (string)')
        return
    if isinstance(memorial, list):
        points = np.array(memorial)
    elif isinstance(memorial, str):
        points = np.array(memorialRead(memorial, decimal=True, verbose=False))
    elif isinstance(memorial, np.ndarray):
        points = memorial
    else:
        print("memorial : unknown format")

    ref_point, rep_index = translate_info(points, ref_points, displace_dist=reference_dist)
    smemo = simple_memo_inverse(points)
    print("simple inverse memorial")
    for line in smemo:
        print(line)
    smemo_restarted = simple_memo_newstart(smemo, rep_index, ref_point)
    smemo_restarted_points = simple_memo_direct(smemo_restarted, repeat_end=True)
    print(u"Ajustando para rumos verdadeiros, tolerância :", mtolerance, " metro")
    # make 'rumos verdadeiros' acceptable by sigareas
    smemo_restarted_points_verd = forceverdPoligonal(smemo_restarted_points, tolerancem=mtolerance)
    print("Area is ", PolygonArea(smemo_restarted_points_verd.tolist())[-1], " ha")
    formatMemorial(smemo_restarted_points_verd)
    print("Pronto para carregar no SIGAREAS -> corrigir poligonal")
    return smemo_restarted_points_verd