import urllib.request
import urllib.error
import json

req = urllib.request.Request(
    'https://2slides.com/api/v1/slides/generate',
    data=json.dumps({"prompt": "Top 10 AI trends", "user_uid": "12345", "slide_count": 3, "mode": "sync"}).encode('utf-8'),
    headers={
        'Authorization': 'Bearer sk-2slides-851674b50a0b01971ae8b4879b4a51e03ea5c87e48b2d31a286f6ad59833f0ec',
        'Content-Type': 'application/json'
    }
)
try:
    res = urllib.request.urlopen(req)
    print("Success:")
    open("test_res.txt", "w").write(res.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print(f"Failed {e.code}:")
    open("test_res.txt", "w").write(e.read().decode('utf-8'))
