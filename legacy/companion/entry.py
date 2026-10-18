from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    from manga_live.host import main
    main()
