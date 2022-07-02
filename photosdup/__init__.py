import argparse
import cv2
import multiprocessing
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

    def __repr__(self):
        return "P(%d,%s)" % (self.size, self.uuid)

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
        print("INFO: BEGINNING",self.desc,file=sys.stdout,flush=True)

    def __exit__(self,type,value,traceback):
        print("INFO: FINISHING",self.desc,file=sys.stdout,flush=True)

class DuplicateFinder():

    def __init__(self,library_dir,gui=False):
        if gui:
            from tqdm.gui import tqdm
        else:
            from tqdm import tqdm
        self.tqdm = tqdm
        self.library = photoscript.PhotosLibrary()
        #self.library.open(library_dir)
        self.library.activate()
        originals_dir = os.path.join(library_dir,"originals")
        filenames_all = (os.path.join(rootname,filename) for rootname, _, filenames in os.walk(originals_dir) for filename in filenames)
        filenames = (filename for filename in filenames_all if filename.split(".")[-1] == "jpeg")
        d = Description("gathering all photos from",library_dir)
        with d:
            self.photos = [Photo(filename) for filename in self.tqdm(filenames,desc=d.desc)]

    def _represent(photo):
        return photo.represent((50,50))

    def represent(self, dimension, max=0, batch=1000):
        if max:
            self.photos = random.sample(self.photos,k=max)
        if batch:
            photos = []
            while len(self.photos):
                photos.append(self.photos[:batch])
                self.photos = self.photos[batch:]
        else:
            photos = [self.photos]
        self.photos = []
        d = Description("building representations resized to",dimension,("in batches of "+str(batch)) if batch else "")
        with d:
           for ps in self.tqdm(photos,desc=d.desc):
                with multiprocessing.Pool() as p:
                    self.photos.extend(p.map(DuplicateFinder._represent,ps))

    #def find(self, metric, radius, prefix, batch=1000):
    def find(self, radius, prefix, batch=1000):
        photos = [photo for photo in self.photos if photo.representation is not None]
        representations = [photo.representation for photo in photos]
        d = Description("building KD tree of",len(representations),"photo representations")
        with d:
            with self.tqdm(desc=d.desc) as pbar:
                #kdtree = sklearn.neighbors.KDTree(representations,metric=metric)
                kdtree = scipy.spatial.KDTree(representations)
                pbar.update(1)
        indexes = []
        if batch:
            reps = []
            while len(representations):
                reps.append(representations[:batch])
                representations = representations[batch:]
        else:
            reps = [representations]
        d = Description("querying KD tree",("in batches of "+str(batch)) if batch else "")
        with d:
            for rep in self.tqdm(reps,desc=d.desc):
                #indexes.extend([list(i) for i in kdtree.query_radius(rep,r=radius)])
                indexes.extend([list(i) for i in kdtree.query_ball_point(rep,r=radius,workers=-1)])
        classes = []
        d = Description("computing and sorting equivalence classes")
        with d:
            for i in self.tqdm(range(len(indexes)),desc=d.desc):
                if len(indexes[i]) > 1:
                    classes.append(sorted([photos[j] for j in indexes[i]],reverse=True))
                    for index in indexes[i]:
                        indexes[index] = []
        duplicates_folder = photoscript.run_script("_folder_by_name",prefix+"-duplicates",True)
        if duplicates_folder:
            photoscript.run_script("_photoslibrary_delete_folder",duplicates_folder)
        duplicates_folder = photoscript.run_script("_photoslibrary_create_folder",prefix+"-duplicates",None)
        d = Description("tagging duplicate images with keywords")
        with d:
            for equiv in self.tqdm(classes,desc=d.desc):
                try:
                    equiv_uuids = [photo.uuid for photo in equiv]
                    equiv_photos = self.library.photos(uuid=equiv_uuids)
                    photo_original = next(equiv_photos)
                    tag = prefix+"-uuid-"+photo_original.uuid
                    DuplicateFinder._add_keywords(photo_original,[tag,prefix+"-original"])
                    for photo_duplicate in equiv_photos:
                        DuplicateFinder._add_keywords(photo_duplicate,[tag,prefix+"-duplicate"])
                    duplicates_album = photoscript.run_script("_photoslibrary_create_album_at_folder", tag, duplicates_folder)
                    photoscript.run_script("_album_add",duplicates_album,equiv_uuids)
                except:
                    print("WARNING: failed to tag",equiv,file=sys.stdout,flush=True)

    def _add_keywords(photo,new_keywords):
        photo.keywords += new_keywords
        keywords = set(photo.keywords)
        for keyword in new_keywords:
            if keyword not in keywords:
                print("WARNING: could not tag",photo.uuid,"with keyword",keyword,file=sys.stdout,flush=True)
