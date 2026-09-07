"""Display-only optical conversion and alignment; temperatures stay untouched."""
import math

import numpy as np
from PIL import Image

from .tc001_max import FRAME_BYTES
from .validation import finite, ValidationError

OPTICAL_OFFSET = 197632
WIDTH, HEIGHT = 256, 192


def optical_image(raw):
    if len(raw) != FRAME_BYTES:
        raise ValidationError('Optical frame length mismatch')
    return optical_plane_image(raw[OPTICAL_OFFSET:])


def optical_plane_image(plane):
    if len(plane)!=1024*768*2:raise ValidationError('Optical plane length mismatch')
    packed = np.frombuffer(plane, np.uint8).reshape(768, 512, 4).astype(np.float32)
    y = packed[:, :, [0, 2]].reshape(768, 1024) - 16
    u = np.repeat(packed[:, :, 1] - 128, 2, axis=1)
    v = np.repeat(packed[:, :, 3] - 128, 2, axis=1)
    rgb = np.stack((1.164383*y + 1.596027*v,
                    1.164383*y - .391762*u - .812968*v,
                    1.164383*y + 2.017232*u), axis=-1)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


def alignment_matrix(settings):
    scale = finite(settings.get('scale', 1), 'Overlay scale', .1, 8)
    angle = math.radians(finite(settings.get('angle', 0), 'Overlay angle', -180, 180))
    dx = finite(settings.get('dx', 0), 'Overlay X', -512, 512)
    dy = finite(settings.get('dy', 0), 'Overlay Y', -384, 384)
    a, b = scale*math.cos(angle), scale*math.sin(angle)
    return np.array([[a, -b, 128+dx-a*128+b*96],
                     [b, a, 96+dy-b*128-a*96], [0, 0, 1]])


def aligned_optical(image, settings):
    # Both display layers use a 1024x768 canvas (four display pixels per sensor pixel).
    inv = np.linalg.inv(alignment_matrix(settings))
    coefficients = (inv[0, 0], inv[0, 1], inv[0, 2]*4,
                    inv[1, 0], inv[1, 1], inv[1, 2]*4)
    return image.transform((1024, 768), Image.Transform.AFFINE, coefficients,
                           Image.Resampling.BILINEAR, fillcolor=(15, 20, 28))


def thermal_image(values, palette='Iron', limits=None):
    data = np.asarray(values, dtype=np.float32).reshape(HEIGHT, WIDTH)
    low, high = limits if limits is not None else (float(data.min()), float(data.max()))
    if not math.isfinite(low) or not math.isfinite(high) or high <= low:
        high = low + .1
    t = np.clip((data-low)/(high-low), 0, 1)
    if palette in ('White hot', 'Black hot'):
        if palette == 'Black hot': t = 1-t
        rgb = np.repeat(t[:, :, None], 3, axis=2)
    else:
        colors = (np.array([[0,0,12],[65,12,110],[190,35,70],[252,145,30],[255,255,215]])
                  if palette == 'Iron' else np.array([[20,20,120],[0,130,230],[30,210,95],[250,230,20],[225,30,15]])) / 255
        rgb = np.stack([np.interp(t, np.linspace(0,1,len(colors)), colors[:,i]) for i in range(3)], axis=-1)
    image = Image.fromarray((rgb*255).astype(np.uint8)).resize((1024,768), Image.Resampling.NEAREST)
    return image, (low, high)


def rotate_image(image, rotation):
    return image.rotate(-rotation, expand=True)


def sensor_to_view(x, y, rotation):
    return {0:(x,y),90:(HEIGHT-y,x),180:(WIDTH-x,HEIGHT-y),270:(y,WIDTH-x)}[rotation]


def view_to_sensor(x, y, rotation):
    return {0:(x,y),90:(y,HEIGHT-x),180:(WIDTH-x,HEIGHT-y),270:(WIDTH-y,x)}[rotation]


def canvas_to_sensor(x, y, viewport, rotation):
    left,top,scale,w,h,clip_left,clip_right,clip_top,clip_bottom=viewport
    if not (clip_left<=x<clip_right and clip_top<=y<clip_bottom):return None
    vx,vy=(x-left)/scale,(y-top)/scale
    if not (0<=vx<w and 0<=vy<h):return None
    sx,sy=view_to_sensor(vx,vy,rotation)
    return min(255.999999,max(0,sx)),min(191.999999,max(0,sy))
