import argparse
import cv2
import itertools
import multiprocessing
import networkx
import numpy as np
import os
import photoscript
import random
import scipy.spatial
import skimage.color
import sys

class Namespace():

    def __init__(self, dict):
        self.__dict__.update(dict)

class Photo():
    def __init__(self,path):
        self.path = path
        self.uuid = path.split("/")[-1].split(".")[0]
        self.size = os.stat(path).st_size

    def __lt__(self,other):
        if self.size < other.size:
            return True
        if self.size > other.size:
            return False
        return self.uuid < other.uuid

    def __eq__(self,other):
        return self.uuid == other.uuid

    def __repr__(self):
        return "P(%d,%s)" % (self.size, self.uuid)

    def __hash__(self):
        return hash(self.uuid)

    def represent(self,dimension):
        try:
            img = cv2.imdecode(np.fromfile(self.path,dtype=np.uint8),cv2.IMREAD_UNCHANGED)
            if type(img) == np.ndarray:
                img = img[..., 0:3]
                img = cv2.resize(img,dsize=dimension,interpolation=cv2.INTER_CUBIC)
                if len(img.shape) == 2:
                    img = skimage.color.gray2rgb(img)
                self.representation = np.ndarray.flatten(img.astype("float"))
        except:
            print("WARNING: could not load and resize",self.path,file=sys.stdout,flush=True)
            self.representation = None
        return self

class Description():

    def __init__(self,*desc):
        self.desc = " ".join((str(d) for d in desc))

    def __enter__(self):
        print("INFO: BEGINNING",self.desc,file=sys.stderr,flush=True)

    def __exit__(self,type,value,traceback):
        print("INFO: FINISHING",self.desc,file=sys.stderr,flush=True)

class DuplicateFinder():

    def __init__(self,library_dir,gui=False,batch=1000,cores=-1,max_images=0):
        self.library_dir = library_dir
        if gui:
            from tqdm.gui import tqdm
        else:
            from tqdm import tqdm
        self.tqdm = tqdm
        self.batch = batch
        self.cores = cores
        self.max = max_images

    def scan(self,dimensions=((10,10),(50,50)),radiuses=(200,1000),prefix=None):
        photos = self.load()
        while dimensions and radiuses:
            dimension, dimensions = dimensions[0], dimensions[1:]
            radius, radiuses = radiuses[0], radiuses[1:]
            rep_photos = self.represent(photos,dimension=dimension)
            classes = self.find(rep_photos,radius=radius)
            if dimensions and radiuses:
                photos = list({photo for equiv in classes for photo in equiv})
        if prefix is not None:
            self.tag(classes=classes,prefix=prefix)
        return classes

    def humanize(num, separator=" ", suffix="B"):
        for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
            if abs(num) < 1024.0:
                return f"{num:3.1f}{separator}{unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f}Yi{suffix}"

    def load(self):
        originals_dir = os.path.join(self.library_dir,"originals")
        filenames_all = (os.path.join(rootname,filename) for rootname, _, filenames in os.walk(originals_dir) for filename in filenames)
        filenames = (filename for filename in filenames_all if filename.split(".")[-1] == "jpeg")
        d = Description("gathering all photos from",self.library_dir)
        with d:
            photos = [Photo(filename) for filename in self.tqdm(filenames,desc=d.desc)]
        print("INFO: total amount of data to scan is",DuplicateFinder.humanize(sum((photo.size for photo in photos))),file=sys.stderr,flush=True)
        return photos

    def _represent(photo,dimension):
        return photo.represent(dimension)

    def represent(self, photos, dimension=(50,50)):
        if self.max:
            photos = random.sample(photos,k=self.max)
        if self.batch:
            old_photos = photos[:]
            photos = []
            while len(old_photos):
                photos.append(old_photos[:self.batch])
                old_photos = old_photos[self.batch:]
        else:
            photos = [photos]
        rep_photos = []
        d = Description("building representations resized to",dimension,("in batches of "+str(self.batch)) if self.batch else "")
        with d:
           for ps in self.tqdm(photos,desc=d.desc):
                if self.cores == 0:
                    rep_photos.extend((DuplicateFinder._represent(p,dimension) for p in ps))
                else:
                    with multiprocessing.Pool(self.cores if self.cores > 0 else None) as p:
                        rep_photos.extend(p.starmap(DuplicateFinder._represent,zip(ps,itertools.repeat(dimension))))
        return [photo for photo in rep_photos if photo.representation is not None]

    def find(self, rep_photos, radius=1000):
        representations = [photo.representation for photo in rep_photos]
        d = Description("building KD tree of",len(representations),"photo representations")
        with d:
            with self.tqdm(desc=d.desc) as pbar:
                kdtree = scipy.spatial.KDTree(representations)
                pbar.update(1)
        indexes = []
        if self.batch:
            reps = []
            while len(representations):
                reps.append(representations[:self.batch])
                representations = representations[self.batch:]
        else:
            reps = [representations]
        d = Description("querying KD tree",("in batches of "+str(self.batch)) if self.batch else "")
        with d:
            for rep in self.tqdm(reps,desc=d.desc):
                indexes.extend([list(i) for i in kdtree.query_ball_point(rep,r=radius,workers=self.cores if self.cores else 1)])
        graph = networkx.Graph()
        d = Description("computing similarity graph")
        with d:
            for i in self.tqdm(range(len(indexes)),desc=d.desc):
                for j in indexes[i]:
                    if j != i:
                        graph.add_edge(i,j)
        classes = []
        d = Description("computing and sorting equivalence classes")
        with d:
            for cc in self.tqdm(list(networkx.connected_components(graph)),desc=d.desc):
                classes.append(sorted([rep_photos[i] for i in cc],reverse=True))
        num_classes = len(classes)
        num_duplicates = sum((len(equiv)-1 for equiv in classes))
        print("INFO: found",num_classes,"classes containing",num_duplicates,"duplicates",file=sys.stderr,flush=True)
        return classes

    def _tag(equiv,prefix,library,duplicates_folder):
        try:
            equiv_uuids = [photo.uuid for photo in equiv]
            equiv_photos = library.photos(uuid=equiv_uuids)
            photo_original = next(equiv_photos)
            tag = prefix+"-uuid-"+photo_original.uuid
            DuplicateFinder._add_keywords(photo_original,[tag,prefix+"-original"])
            for photo_duplicate in equiv_photos:
                DuplicateFinder._add_keywords(photo_duplicate,[tag,prefix+"-duplicate"])
            duplicates_album = photoscript.run_script("_photoslibrary_create_album_at_folder", tag, duplicates_folder)
            photoscript.run_script("_album_add",duplicates_album,equiv_uuids)
        except Exception as e:
            print("WARNING: failed to tag",equiv,e,file=sys.stderr,flush=True)

    def tag(self, classes, prefix="photosdup"):
        library = photoscript.PhotosLibrary()
        library.open(self.library_dir)
        library.activate()
        duplicates_folder = photoscript.run_script("_folder_by_name",prefix+"-duplicates",True)
        if duplicates_folder:
            photoscript.run_script("_photoslibrary_delete_folder",duplicates_folder)
        duplicates_folder = photoscript.run_script("_photoslibrary_create_folder",prefix+"-duplicates",None)
        if self.batch:
            duplicates = classes[:]
            equivs = []
            while len(duplicates):
                equivs.append(duplicates[:self.batch])
                duplicates = duplicates[self.batch:]
        else:
            equivs = [self.duplicates]
        prefix = prefix
        d = Description("tagging duplicate images with keywords",("in batches of "+str(self.batch)) if self.batch else "")
        with d:
            for duplicates in self.tqdm(equivs,desc=d.desc):
                if self.cores == 0:
                    for equiv in duplicates:
                        DuplicateFinder._tag(equiv,prefix,library,duplicates_folder)
                else:
                    with multiprocessing.Pool(self.cores if self.cores > 0 else None) as p:
                        p.starmap(DuplicateFinder._tag,zip(duplicates,itertools.repeat(prefix),itertools.repeat(library),itertools.repeat(duplicates_folder)))

    def _add_keywords(photo,new_keywords):
        photo.keywords += new_keywords
        keywords = set(photo.keywords)
        for keyword in new_keywords:
            if keyword not in keywords:
                print("WARNING: could not tag",photo.uuid,"with keyword",keyword,file=sys.stderr,flush=True)
