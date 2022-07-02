from photosdup import DuplicateFinder, Namespace
import PySimpleGUI as sg
import subprocess

def main(args):
    result = subprocess.run(["mdfind","kMDItemDisplayName == *.photoslibrary"],stdout=subprocess.PIPE)
    values = [val.decode('utf-8') for val in result.stdout.split(b"\n") if val]
    scan = sg.Button("Scan for duplicates",disabled=False)
    params = [[sg.Text("x-dimension for scaling",size=(60,1)),sg.InputText("50",key="xdim",size=(60,1))],
              [sg.Text("y-dimension for scaling",size=(60,1)),sg.InputText("50",key="ydim",size=(60,1))],
              [sg.Text("radius for similarity search",size=(60,1)),sg.InputText("1000",key="radius",size=(60,1))],
              [sg.Text("prefix to use for keywords",size=(60,1)),sg.InputText("photosdup",key="prefix",size=(60,1))],
              [sg.Text("maximum number of photos to process (0 is unlimited)",size=(60,1)),sg.InputText("0",key="max",size=(60,1))],
              [sg.Text("size of batches to process",size=(60,1)),sg.InputText("100",key="batch",size=(60,1))]]
    layout = [[sg.Listbox(values=values,size=(125,25),enable_events=True,key="library")],
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
            df = DuplicateFinder(args.library[0],gui=True)
            df.represent(dimension=(int(args.xdim),int(args.ydim)),max=int(args.max),batch=int(args.batch))
            df.find(radius=float(args.radius),prefix=args.prefix,batch=int(args.batch))
            sg.Popup("To delete duplicates, create a smart album for the keyword "+args.prefix+"-duplicates and delete its contents after careful review.")
            break
