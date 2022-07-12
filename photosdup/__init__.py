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
        print("INFO: BEGINNING",self.desc,file=sys.stderr,flush=True)

    def __exit__(self,type,value,traceback):
        print("INFO: FINISHING",self.desc,file=sys.stderr,flush=True)

class DuplicateFinder():

    def __init__(self,library_dir,gui=False,batch=1000,cores=-1,max=0):
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
        self.batch = batch
        self.cores = cores
        self.max = max

    def _represent(self,photo):
        return photo.represent(self.dimension)

    def represent(self, dimension=(50,50)):
        if self.max:
            self.photos = random.sample(self.photos,k=self.max)
        if self.batch:
            photos = []
            while len(self.photos):
                photos.append(self.photos[:self.batch])
                self.photos = self.photos[self.batch:]
        else:
            photos = [self.photos]
        self.photos = []
        self.dimension = dimension
        d = Description("building representations resized to",dimension,("in batches of "+str(self.batch)) if self.batch else "")
        with d:
           for ps in self.tqdm(photos,desc=d.desc):
                if self.cores == 0:
                    self.photos.extend((DuplicateFinder._represent(p) for p in ps))
                else:
                    with multiprocessing.Pool(self.cores if self.cores > 0 else None) as p:
                        self.photos.extend(p.map(self._represent,ps))

    def find(self, radius=1000):
        photos = [photo for photo in self.photos if photo.representation is not None]
        representations = [photo.representation for photo in photos]
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
        classes = []
        d = Description("computing and sorting equivalence classes")
        with d:
            for i in self.tqdm(range(len(indexes)),desc=d.desc):
                if len(indexes[i]) > 1:
                    classes.append(sorted([photos[j] for j in indexes[i]],reverse=True))
                    for index in indexes[i]:
                        indexes[index] = []
        self.duplicates = classes

    def _tag(self,equiv):
        try:
            equiv_uuids = [photo.uuid for photo in equiv]
            equiv_photos = self.library.photos(uuid=equiv_uuids)
            photo_original = next(equiv_photos)
            tag = self.prefix+"-uuid-"+photo_original.uuid
            DuplicateFinder._add_keywords(photo_original,[tag,self.prefix+"-original"])
            for photo_duplicate in equiv_photos:
                DuplicateFinder._add_keywords(photo_duplicate,[tag,self.prefix+"-duplicate"])
            duplicates_album = photoscript.run_script("_photoslibrary_create_album_at_folder", tag, self.duplicates_folder)
            photoscript.run_script("_album_add",duplicates_album,equiv_uuids)
        except Exception as e:
            print("WARNING: failed to tag",equiv,e,file=sys.stderr,flush=True)

    def tag(self, prefix):
        duplicates_folder = photoscript.run_script("_folder_by_name",prefix+"-duplicates",True)
        if duplicates_folder:
            photoscript.run_script("_photoslibrary_delete_folder",duplicates_folder)
        self.duplicates_folder = photoscript.run_script("_photoslibrary_create_folder",prefix+"-duplicates",None)
        if self.batch:
            duplicates = self.duplicates[:]
            equivs = []
            while len(duplicates):
                equivs.append(duplicates[:self.batch])
                duplicates = duplicates[self.batch:]
        else:
            equivs = [self.duplicates]
        self.prefix = prefix
        d = Description("tagging duplicate images with keywords",("in batches of "+str(self.batch)) if self.batch else "")
        with d:
            for duplicates in self.tqdm(equivs,desc=d.desc):
                if self.cores == 0:
                    for equiv in duplicates:
                        self._tag(equiv)
                else:
                    with multiprocessing.Pool(self.cores if self.cores > 0 else None) as p:
                        p.map(self._tag,duplicates)

    def _add_keywords(photo,new_keywords):
        photo.keywords += new_keywords
        keywords = set(photo.keywords)
        for keyword in new_keywords:
            if keyword not in keywords:
                print("WARNING: could not tag",photo.uuid,"with keyword",keyword,file=sys.stderr,flush=True)
