import requests

urls = [
    "https://raw.githubusercontent.com/Bitakhparsa/Capstone/0850c8f65f74c58e45f6cdb2fc6d966e4c160a78/Plant_1_Generation_Data.csv",
    "https://raw.githubusercontent.com/Bitakhparsa/Capstone/0850c8f65f74c58e45f6cdb2fc6d966e4c160a78/Plant_1_Weather_Sensor_Data.csv",
    "https://raw.githubusercontent.com/kaivalpanchal/Solar-Panel-Power-Generation/main/Plant_1_Generation_Data.csv",
]
for url in urls:
    try:
        r = requests.get(url, timeout=60)
        print(r.status_code, len(r.content), url)
        print(r.text[:200].replace("\n", " | "))
    except Exception as exc:
        print("ERROR", url, exc)
