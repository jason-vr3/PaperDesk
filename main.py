from paperdesk.app import main

if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == '--self-check':
        from paperdesk.selfcheck import run
        run(sys.argv[2])
    else:
        main()
