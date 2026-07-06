from pathlib import Path
import ssl
from urllib.request import Request, urlopen


URL = (
    "https://assets.science.nasa.gov/content/dam/science/esd/eo/images/"
    "imagerecords/79000/79765/dnb_land_ocean_ice.2012.3600x1800.jpg"
)
OUT = Path(__file__).resolve().parent / "sources" / "black_marble_2012_3600x1800.jpg"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    request = Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=60) as response:
            data = response.read()
    except ssl.SSLError:
        context = ssl._create_unverified_context()
        with urlopen(request, timeout=60, context=context) as response:
            data = response.read()
    if len(data) < 100_000:
        raise SystemExit(f"download looked too small: {len(data)} bytes")
    OUT.write_bytes(data)
    print(f"written: {OUT}")
    print(f"bytes: {len(data)}")


if __name__ == "__main__":
    main()
