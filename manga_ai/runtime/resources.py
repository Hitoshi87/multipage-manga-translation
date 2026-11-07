"""Bounded-memory file and image readers."""
import hashlib
import numpy as np
from PIL import Image


def sha256_file(path):
    digest=hashlib.sha256()
    with open(path,'rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def read_rgb(path):
    with Image.open(path) as image:return np.array(image.convert('RGB'))


def read_gray(path):
    with Image.open(path) as image:return np.array(image.convert('L'))
