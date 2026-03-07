import traceback
import sys

try:
    import app.main
    print("Success")
except Exception as e:
    with open('error.txt', 'w', encoding='utf-8') as f:
        traceback.print_exc(file=f)
    print("Error written to error.txt")
