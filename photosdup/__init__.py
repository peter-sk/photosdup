import cv2
import itertools
import multiprocessing
import networkx
import numpy as np
import os
import photoscript
import pyheif
import random
import scipy.spatial
import skimage.color
import sys

class Namespace():

    def __init__(self, dict):
        self.__dict__.update(dict)

class Photo():
    def __init__(self,path,uuid=None):
        self.path = path
        self.uuid = path.split("/")[-1].split(".")[0]
        if uuid is not None:
            self.uuid = uuid(self.uuid)
        self.size = os.stat(path).st_size
        self.original_path = path

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
            img_data = np.fromfile(self.path,dtype=np.uint8)
            ext = self.path.split(".")[-1]
            if ext == "heic":
                heif_file = pyheif.read(img_data)
                assert(heif_file.mode == "RGB")
                expected_length = heif_file.size[0]*heif_file.size[1]*3
                img = np.array(heif_file.data)
                if len(img) > expected_length:
                    img = img[:expected_length]
                img = img.reshape(heif_file.size[1],heif_file.size[0],3)
            else:
                img = cv2.imdecode(img_data,cv2.IMREAD_UNCHANGED)
            if type(img) == np.ndarray:
                img = img[..., 0:3]
                img = cv2.resize(img,dsize=dimension,interpolation=cv2.INTER_CUBIC)
                if len(img.shape) == 2:
                    img = skimage.color.gray2rgb(img)
                self.representation = np.ndarray.flatten(img.astype("float"))
        except Exception as e:
            print("WARNING: could not load and resize",self.path,e,dir(e),file=sys.stdout,flush=True)
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
        self.library_dir = library_dir.rstrip(os.sep)
        self.is_photos = self.library_dir.endswith(".photoslibrary")
        if gui:
            from tqdm.gui import tqdm
        else:
            from tqdm import tqdm
        self.tqdm = tqdm
        self.batch = batch
        self.cores = cores
        self.max = max_images

    def scan(self,thumbs=False,dimensions=((10,10),(50,50)),radiuses=(200,1000),prefix=None):
        photos = self.load(thumbs=thumbs)
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

    def _join(self,dirs):
        return os.path.join(self.library_dir,*dirs)

    def load(self,thumbs=False):
        images_dir = self._join(["resources","derivatives","masters"]) if thumbs else self._join(["originals"])
        filenames = (os.path.join(rootname,filename) for rootname, _, filenames in os.walk(images_dir) for filename in filenames)
        if thumbs:
            def thumbs_remover(s):
                return s.split("_")[0]
        d = Description("gathering all photos from",self.library_dir)
        with d:
            photos = [Photo(filename,uuid=thumbs_remover if thumbs else None) for filename in self.tqdm(filenames,desc=d.desc)]
        if thumbs:
            d = Description("scanning for originals")
            with d:
                originals = (os.path.join(rootname,filename) for rootname, _, filenames in os.walk(self._join(["originals"])) for filename in filenames)
                originals = {path.split("/")[-1].split(".")[0]:path for path in originals}
                print(originals)
            d = Description("checking whether original exists")
            new_photos = []
            for photo in self.tqdm(photos,desc=d.desc):
                original_path = originals.get(photo.uuid,None)
                if original_path is not None:
                    photo.original_path = original_path
                    new_photos.append(photo)
            photos = new_photos
            print("INFO: reduced number of images to",len(photos),file=sys.stderr,flush=True)
        print("INFO: total amount of data to scan is",DuplicateFinder.humanize(sum((photo.size for photo in photos))),file=sys.stderr,flush=True)
        return photos

    def _represent(photo,dimension):
        return photo.represent(dimension)

    def represent(self, photos, dimension=(50,50)):
        if self.max:
            photos = random.sample(photos,k=self.max if self.max < len(photos) else len(photos))
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
