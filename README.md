# Photos Duplicates (photosdup)

**Tool to scan a Mac Photos library for duplicates, thumbnails etc.**

The photosdup tool is available from [PyPI](https://pypi.org/project/photosdup/1.0/):

```
pip install photosdup
```

## Command line interface
After installation, photosdup can be run by providing it with the directory of the Photos library you would like to scan.

```
python -m photosdup Pictures/Photos.photoslibrary
```
By default, the command line version prints a list of lists of images, with each interior list representing an original as its first element and its likely duplicates as the remaining elements.

To speed up the scanning considerably, you can scale the precomputed thumbnails instead of the originals:
```
python -m photosdup Pictures/Photos.photoslibrary --thumbs
```

To tag originals and duplicates with keywords and create albums for them instead, you can add the following parameter:
```
python -m photosdup Pictures/Photos.photoslibrary --tag
```

## Use as a library
You can instantiate a DuplicateFinder object by providing the path of the library to scan and using the scan convenience function:
``
from photosdup import DuplicateFinder
df = DuplicateFinder("Picturs/Photos Library.photoslibrary")
print(df.scan())
``
Finer control is available through the functions load, represent, find, and tag. See the implementation of scan for the typical usage.

## Graphical user interface (experimental)
There is an experimental graphical user interface, which attempts to aid in locating the Photos library and set the parameters (see next section).
```
python -m photosdup --gui
``` 
The graphical user interface always tags originals and duplicates with keywords and creates albums for them.

## Parameters
Several parameters such as the dimensions of the scaled down image used for comparison can be provided in both the command line and the graphical user interface. For an explanation and overview, just use the help function.
```
python -m photosdup --help
```
If the graphical user interface has stability problems, force single core code using 0 for the cores parameter.

## Result of scan
The result of the scan is stored by photosdup in two ways:
1. each time a duplicate is found, the higher-quality image (as judged by total file size) is tagged with the keyword photosdup-duplicate while the lower-quality duplicates are tagged with the keyword photosdup-original.
2. each set of original and duplicates is tagged with the UUID of the original and put in an album called photosdup-UUID.

## Related work and approach

The approach used for scaling images is inspired by the approach taken in difPy. Unfortunately, difPy could not be used as it does not integrate with the Photos database (minor nuisance regarding updating the database) and uses a quadratic algorithm that compares each image to all other images, i.e., N*(N-1) comparisons for N images. Nevertheless, the approach described here was a great inspiration:
https://towardsdatascience.com/finding-duplicate-images-with-python-71c04ec8051

The search for duplicates and near duplicates uses a radius query on a KD tree. The SciPy implementation was used as it supports parallelization via multiple threaded workers:
https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.KDTree.query_ball_point.html#scipy.spatial.KDTree.query_ball_point

Last, but not least, iterative deepening in the form of lower-resolution scanning is used to eliminate likely non-duplicates from the more costly higher-resolution scanning. This aspect can be controlled by the --xdims, --ydims, and --radiuses parameters (cf. the output of --help).