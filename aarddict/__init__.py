import zlib
import bz2
    
compression = (zlib.compress,
               bz2.compress)

decompression = (zlib.decompress,
                 bz2.decompress)


def main():
    try:
        import hildon
    except:        
        import ui
        viewer = ui.DictViewer()
    else:
        import hildonui
        viewer = hildonui.HildonDictViewer()
    viewer.main()