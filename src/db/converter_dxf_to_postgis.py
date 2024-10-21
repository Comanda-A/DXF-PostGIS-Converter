from shapely.geometry import Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon, GeometryCollection
from shapely.wkt import loads
import re
from ..logger.logger import Logger


def convert_dxf_to_postgis(entity):
    '''
    examply entity

    {
        "entity_description": "POINT(#8708)",
        "attributes": [
            "Color: 256",
            "Linetype: BYLAYER",
            "Lineweight: -1",
            "Ltscale: 1.0",
            "Invisible: 0",
            "True Color: None",
            "Transparency: None",
        ],
        "geometry": [
            "Location: (3221571.839578762, 541035.9431979314, 26.4693631301718)"
        ],
    }
    '''

    dxftype = entity['entity_description'].split('(')[0]


    if dxftype == 'POINT':
        location = [geom for geom in entity['geometry'] if 'Location' in geom]
        if location:  # Check if location is not empty
            location_str = str(location[0])
            location_match = re.search(r'\(([^,]+), ([^,]+), ([^)]+)\)', location_str)
            if location_match:
                x, y, z = map(float, location_match.groups())
                return Point(x, y, z)
    elif dxftype == 'CIRCLE':
        center = None
        radius = None
        
        # Извлечение центра и радиуса из geometry
        for geom in entity['geometry']:
            if 'Center:' in geom:
                center_match = re.search(r'\(([^,]+), ([^,]+), ([^)]+)\)', geom)
                if center_match:
                    center = tuple(map(float, center_match.groups()))
            elif 'Radius:' in geom:
                radius_match = re.search(r'Radius: ([0-9\.]+)', geom)
                if radius_match:
                    radius = float(radius_match.group(1))

        if center and radius is not None:
            x, y, z = center
            # Создание многоугольника, представляющего круг
            return Point(x, y).buffer(radius)  # Возвращаем многоугольник круга

    return None  # Return None if location is empty

    # Добавьте другие типы по мере необходимости


    return None  # Если тип не поддерживается
