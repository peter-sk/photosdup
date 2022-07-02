import argparse
from photosdup import DuplicateFinder

def main(argv):
    parser = argparse.ArgumentParser(description="Mac OS Photos Duplicate Finder")
    parser.add_argument("library_dir",type=str, help="Photos library to scan for duplicates and similar images")
    parser.add_argument("--xdim",type=int, default=50, help="horizontal dimension to scale to (default: 50)")
    parser.add_argument("--ydim",type=int, default=50, help="vertical dimension to scale to (default: 50)")
    parser.add_argument("--radius",type=float, default=1000, help="radius for considering images to be duplicates")
    parser.add_argument("--prefix",type=str, default="photosdup", help="prefix for all keywords")
    parser.add_argument("--max",type=int, default="0", help="if non-zero, maximum number of photos to process (default: 0)")
    parser.add_argument("--batch",type=int, default="1000", help="if non-zero, limit the number of photos per query (default: 1000)")
    parser.add_argument("--gui",action="store_true", help="show progress using graphical progress bar")
    args = parser.parse_args(argv)
    df = DuplicateFinder(args.library_dir,args.gui)
    df.represent(dimension=(args.xdim,args.ydim),max=args.max,batch=args.batch)
    df.find(radius=args.radius,prefix=args.prefix,batch=args.batch)
    print("INFO: To delete duplicates, create a smart album for the keyword "+args.prefix+"-duplicates and delete its contents after careful review.")
