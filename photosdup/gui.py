from photosdup import DuplicateFinder, Namespace
import PySimpleGUI as sg
import subprocess

def main(args):
    result = subprocess.run(["mdfind","kMDItemDisplayName == *.photoslibrary"],stdout=subprocess.PIPE)
    values = [val.decode('utf-8') for val in result.stdout.split(b"\n") if val]
    scan = sg.Button("Scan for duplicates",disabled=True)
    params = [[sg.Text("x-dimensions for scaling",size=(60,1)),sg.InputText("10,50",key="xdims",size=(60,1))],
              [sg.Text("y-dimensions for scaling",size=(60,1)),sg.InputText("10,50",key="ydims",size=(60,1))],
              [sg.Text("radiuses for similarity search",size=(60,1)),sg.InputText("400,1000",key="radiuses",size=(60,1))],
              [sg.Text("prefix to use for keywords",size=(60,1)),sg.InputText("photosdup",key="prefix",size=(60,1))],
              [sg.Text("maximum number of photos to process (0 is unlimited)",size=(60,1)),sg.InputText("0",key="max",size=(60,1))],
              [sg.Text("size of batches to process",size=(60,1)),sg.InputText("100",key="batch",size=(60,1))],
              [sg.Text("number of cores to use (-1 is all)",size=(60,1)),sg.InputText("-1",key="cores",size=(60,1))],
              [sg.Text("use thumbnails instead of originals (True/False)",size=(60,1)),sg.InputText("False",key="thumbs",size=(60,1))],
              [sg.Text("show progress as experimental graphical plots (True/False)"),sg.InputText("False",key="gui",size=(60,1))]]
    layout = [[sg.Listbox(values=values,size=(125,24),enable_events=True,key="library")],
              [sg.Frame("Parameters",layout=params)],
              [scan]]
    window = sg.Window(title="Mac Photos Duplicate Finder",layout=layout,size=(800,500),resizable=True)
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break
        scan.update(disabled=len(values["library"]) != 1)
        if event == "Scan for duplicates":
            args = Namespace(values)
            window.close()
            df = DuplicateFinder(args.library[0],gui=True,batch=int(args.batch),cores=int(args.cores),max_images=int(args.max))
            classes = df.scan(thumbs=bool(args.thumbs),dimensions=tuple(zip((int(xdim) for xdim in args.xdims.split(",")),(int(ydim) for ydim in args.ydims.split(",")))),radiuses=tuple((float(radius) for radius in args.radiuses.split(","))),prefix=args.prefix,gui=eval(args.gui))
            sg.Popup("To delete duplicates, create a smart album for the keyword "+args.prefix+"-duplicates and delete its contents after careful review.")
            break
