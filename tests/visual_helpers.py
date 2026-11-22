"""Pixel probes for visual regressions; independent of runtime calibration tables."""
from PIL import ImageChops


def white_face_width(image):
    image = image.convert("RGBA")
    r, g, b, alpha = image.split()
    low = ImageChops.darker(ImageChops.darker(r, g), b)
    high = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mask = ImageChops.multiply(low.point(lambda v: 255 if v >= 190 else 0),
                              ImageChops.subtract(high, low).point(lambda v: 255 if v <= 48 else 0))
    mask = ImageChops.multiply(mask, alpha.point(lambda v: 255 if v >= 200 else 0))
    w, h = image.size
    visible = alpha.getbbox()
    data = bytearray(mask.tobytes())
    groups = []
    start = data.find(b"\xff")
    while start >= 0:
        todo = [start]; data[start] = 0
        x0 = x1 = start % w; y0 = y1 = start // w; count = 0
        while todo:
            index = todo.pop(); x = index % w; y = index // w; count += 1
            x0 = min(x0, x); x1 = max(x1, x); y0 = min(y0, y); y1 = max(y1, y)
            for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if 0 <= nx < w and 0 <= ny < h and data[ny*w+nx]:
                    data[ny*w+nx] = 0; todo.append(ny*w+nx)
        width, height = x1-x0+1, y1-y0+1
        if (width > (visible[2]-visible[0])*.25 and .35 < height/width < 1.6
                and y0 < visible[1]+(visible[3]-visible[1])*.6):
            groups.append((count, width))
        start = data.find(b"\xff", start+1)
    return max(groups)[1] if groups else 0
