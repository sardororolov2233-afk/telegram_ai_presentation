import traceback
try:
    import app.main
except BaseException as e:
    with open("err_files.txt", "w", encoding="utf-8") as f:
        for x in traceback.extract_tb(e.__traceback__):
            f.write(f"{x.filename}:{x.lineno}\n")
        f.write(f"\n{type(e).__name__}: {str(e)}\n")
