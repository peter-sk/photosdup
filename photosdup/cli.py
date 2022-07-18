import argparse
import json
from photosdup import DuplicateFinder

def main(argv):
    parser = argparse.ArgumentParser(description="Mac OS Photos Duplicate Finder")
    parser.add_argument("library_dir",type=str, help="Photos library to scan for duplicates and similar images")
    parser.add_argument("--xdims",type=int, nargs="+", default=[10,50], help="horizontal dimension to scale to (default: 50)")
    parser.add_argument("--ydims",type=int, nargs="+", default=[10,50], help="vertical dimension to scale to (default: 50)")
    parser.add_argument("--radiuses",type=float, nargs="+", default=[400,1000], help="radiuses for considering images to be duplicates (default: 400,1000)")
    parser.add_argument("--tag",action="store_true", help="tag duplicats and originals with keywords and create album folder")
    parser.add_argument("--prefix",type=str, default="photosdup", help="prefix for all keywords")
    parser.add_argument("--max",type=int, default="0", help="if non-zero, maximum number of photos to process (default: 0)")
    parser.add_argument("--batch",type=int, default=1000, help="if non-zero, limit the number of photos per query (default: 1000)")
    parser.add_argument("--cores",type=int, default=-1, help="if -1, use all cores, if 0 a single thread (default: -1)")
    parser.add_argument("--thumbs",action="store_true", help="use thumbnails instead of originals (default: False)")
    parser.add_argument("--gui",action="store_true", help="show progress using graphical progress bar")
    args = parser.parse_args(argv)
    df = DuplicateFinder(args.library_dir,args.gui,args.batch,args.cores,args.max)
    classes = df.scan(thumbs=args.thumbs,dimensions=tuple(zip(args.xdims,args.ydims)),radiuses=args.radiuses,prefix=args.prefix if args.tag else None)
    print(json.dumps([[photo.original_path for photo in equiv] for equiv in classes],indent=4))
    if args.tag:
        print("INFO: To delete duplicates, create a smart album for the keyword "+args.prefix+"-duplicates and delete its contents after careful review.")
