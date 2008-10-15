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