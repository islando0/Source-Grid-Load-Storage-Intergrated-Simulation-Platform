"""下载并检查公开光伏数据集（课程实验用，原始数据不随项目再分发）。"""

from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "external" / "solar_power_generation"
OUT.mkdir(parents=True, exist_ok=True)

BASE = "https://raw.githubusercontent.com/Bitakhparsa/Capstone/0850c8f65f74c58e45f6cdb2fc6d966e4c160a78"
FILES = {
    "Plant_1_Generation_Data.csv": f"{BASE}/Plant_1_Generation_Data.csv",
    "Plant_1_Weather_Sensor_Data.csv": f"{BASE}/Plant_1_Weather_Sensor_Data.csv",
}

for name, url in FILES.items():
    path = OUT / name
    if not path.exists():
        print("download", name)
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
    print(name, path.stat().st_size, "bytes")

gen = pd.read_csv(OUT / "Plant_1_Generation_Data.csv")
weather = pd.read_csv(OUT / "Plant_1_Weather_Sensor_Data.csv")
print("gen", gen.shape, gen.columns.tolist())
print(gen.head(3).to_string())
print("weather", weather.shape, weather.columns.tolist())
print(weather.head(3).to_string())
print("gen time", gen["DATE_TIME"].min(), "->", gen["DATE_TIME"].max())
print("weather time", weather["DATE_TIME"].min(), "->", weather["DATE_TIME"].max())
print("inverters", gen["SOURCE_KEY"].nunique(), "rows per time", gen.groupby("DATE_TIME").size().describe().to_dict())
print("AC max", gen["AC_POWER"].max(), "DC max", gen["DC_POWER"].max())
print("weather IRRA max", weather["IRRADIATION"].max(), "ambient range", (weather["AMBIENT_TEMPERATURE"].min(), weather["AMBIENT_TEMPERATURE"].max()))
print("weather missing", weather.isna().sum().to_dict())
print("gen missing", gen.isna().sum().to_dict())
