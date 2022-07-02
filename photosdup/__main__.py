from photosdup import cli, gui
from sys import argv

args = argv[1:]
if "--gui" in args:
	gui.main(args)
else:
	cli.main(args)