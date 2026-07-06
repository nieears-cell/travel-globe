# -*- coding: utf-8 -*-
"""Build Travel_Globe.html as a single-file, offline Three.js travel album."""
from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import math
import os
import struct
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
    from PIL.ExifTags import GPSTAGS, TAGS
except Exception as exc:  # pragma: no cover - build-time guard
    raise SystemExit("Pillow is required to build this demo: %s" % exc)


ROOT = Path(__file__).resolve().parent
THREE = ROOT / "three.min.js"
OUT = ROOT / "Travel_Globe.html"
SOURCES = ROOT / "sources"
NE_LAND_ZIP = SOURCES / "ne_50m_land.zip"
NE_COAST_ZIP = SOURCES / "ne_50m_coastline.zip"
PORTOLAN_SCAN = SOURCES / "maggiolo_1547_2560.jpg"
BLACK_MARBLE_SOURCE = SOURCES / "black_marble_2012_3600x1800.jpg"
BLACK_MARBLE_2K = SOURCES / "black_marble_2012_2048.jpg"
MAX_HTML_BYTES = 15 * 1024 * 1024
# GitHub Pages 部署基址(og:image 等绝对 URL 用);换仓库名时改这里并重建
PAGES_BASE = "https://nieears-cell.github.io/travel-globe/"

DEMO_ROWS = [
    ("tokyo-01.jpg", "东京", "日本", 35.6762, 139.6503, "#d85c48", "#f5d06f"),
    ("tokyo-02.jpg", "东京", "日本", 35.6895, 139.6917, "#6abf69", "#e9f0c9"),
    ("paris-01.jpg", "巴黎", "法国", 48.8566, 2.3522, "#5874c8", "#f2d7aa"),
    ("paris-02.jpg", "巴黎", "法国", 48.8738, 2.2950, "#c66b9b", "#f7d5e5"),
    ("new-york.jpg", "纽约", "美国", 40.7128, -74.0060, "#3f89b8", "#f6f1df"),
    ("cairo.jpg", "开罗", "埃及", 30.0444, 31.2357, "#c78f42", "#f2d1a3"),
    ("cape-town.jpg", "开普敦", "南非", -33.9249, 18.4241, "#4b9a76", "#d9ead3"),
    ("sydney.jpg", "悉尼", "澳大利亚", -33.8688, 151.2093, "#d76f43", "#f6c1a0"),
    ("rio.jpg", "里约热内卢", "巴西", -22.9068, -43.1729, "#42a85f", "#f7e47d"),
    ("reykjavik.jpg", "雷克雅未克", "冰岛", 64.1466, -21.9426, "#6eb7d8", "#e7f4fb"),
]

PERSONA_CITIES = ROOT / "persona-core" / "cities.json"

# 国际城市扩展坐标表(cities.json 之外的常见目的地,离线兜底,符合断网可用约束)
# 名称: (纬度, 经度, 国家/地区)
EXT_CITIES: Dict[str, Tuple[float, float, str]] = {
    "东京": (35.68, 139.65, "日本"), "大阪": (34.69, 135.50, "日本"), "京都": (35.01, 135.77, "日本"),
    "名古屋": (35.18, 136.91, "日本"), "札幌": (43.06, 141.35, "日本"), "福冈": (33.59, 130.40, "日本"),
    "冲绳": (26.21, 127.68, "日本"), "首尔": (37.57, 126.98, "韩国"), "釜山": (35.18, 129.08, "韩国"),
    "济州岛": (33.50, 126.53, "韩国"), "曼谷": (13.76, 100.50, "泰国"), "清迈": (18.79, 98.99, "泰国"),
    "普吉岛": (7.88, 98.39, "泰国"), "新加坡": (1.35, 103.82, "新加坡"), "吉隆坡": (3.14, 101.69, "马来西亚"),
    "巴厘岛": (-8.34, 115.09, "印尼"), "雅加达": (-6.21, 106.85, "印尼"), "河内": (21.03, 105.85, "越南"),
    "胡志明市": (10.82, 106.63, "越南"), "岘港": (16.05, 108.22, "越南"), "暹粒": (13.36, 103.86, "柬埔寨"),
    "马尼拉": (14.60, 120.98, "菲律宾"), "长滩岛": (11.97, 121.92, "菲律宾"), "新德里": (28.61, 77.21, "印度"),
    "孟买": (19.08, 72.88, "印度"), "加德满都": (27.72, 85.32, "尼泊尔"), "马累": (4.18, 73.51, "马尔代夫"),
    "迪拜": (25.20, 55.27, "阿联酋"), "阿布扎比": (24.45, 54.38, "阿联酋"), "多哈": (25.29, 51.53, "卡塔尔"),
    "伊斯坦布尔": (41.01, 28.98, "土耳其"), "开罗": (30.04, 31.24, "埃及"), "特拉维夫": (32.08, 34.78, "以色列"),
    "巴黎": (48.86, 2.35, "法国"), "尼斯": (43.70, 7.27, "法国"), "伦敦": (51.51, -0.13, "英国"),
    "爱丁堡": (55.95, -3.19, "英国"), "罗马": (41.90, 12.50, "意大利"), "米兰": (45.46, 9.19, "意大利"),
    "威尼斯": (45.44, 12.32, "意大利"), "佛罗伦萨": (43.77, 11.26, "意大利"), "巴塞罗那": (41.39, 2.17, "西班牙"),
    "马德里": (40.42, -3.70, "西班牙"), "阿姆斯特丹": (52.37, 4.90, "荷兰"), "柏林": (52.52, 13.40, "德国"),
    "慕尼黑": (48.14, 11.58, "德国"), "布拉格": (50.08, 14.44, "捷克"), "维也纳": (48.21, 16.37, "奥地利"),
    "苏黎世": (47.38, 8.54, "瑞士"), "因特拉肯": (46.69, 7.85, "瑞士"), "圣托里尼": (36.39, 25.46, "希腊"),
    "雅典": (37.98, 23.73, "希腊"), "里斯本": (38.72, -9.14, "葡萄牙"), "布达佩斯": (47.50, 19.04, "匈牙利"),
    "哥本哈根": (55.68, 12.57, "丹麦"), "斯德哥尔摩": (59.33, 18.07, "瑞典"), "赫尔辛基": (60.17, 24.94, "芬兰"),
    "都柏林": (53.35, -6.26, "爱尔兰"), "莫斯科": (55.76, 37.62, "俄罗斯"), "圣彼得堡": (59.93, 30.34, "俄罗斯"),
    "纽约": (40.71, -74.01, "美国"), "洛杉矶": (34.05, -118.24, "美国"), "旧金山": (37.77, -122.42, "美国"),
    "西雅图": (47.61, -122.33, "美国"), "芝加哥": (41.88, -87.63, "美国"), "拉斯维加斯": (36.17, -115.14, "美国"),
    "波士顿": (42.36, -71.06, "美国"), "华盛顿": (38.91, -77.04, "美国"), "迈阿密": (25.76, -80.19, "美国"),
    "檀香山": (21.31, -157.86, "美国"), "温哥华": (49.28, -123.12, "加拿大"), "多伦多": (43.65, -79.38, "加拿大"),
    "墨西哥城": (19.43, -99.13, "墨西哥"), "坎昆": (21.16, -86.85, "墨西哥"), "里约热内卢": (-22.91, -43.17, "巴西"),
    "圣保罗": (-23.55, -46.63, "巴西"), "布宜诺斯艾利斯": (-34.60, -58.38, "阿根廷"), "利马": (-12.05, -77.04, "秘鲁"),
    "库斯科": (-13.53, -71.97, "秘鲁"), "悉尼": (-33.87, 151.21, "澳大利亚"), "墨尔本": (-37.81, 144.96, "澳大利亚"),
    "奥克兰": (-36.85, 174.76, "新西兰"), "皇后镇": (-45.03, 168.66, "新西兰"), "开普敦": (-33.92, 18.42, "南非"),
    "马拉喀什": (31.63, -7.99, "摩洛哥"), "内罗毕": (-1.29, 36.82, "肯尼亚"),
}


def build_city_coords() -> Dict[str, Dict[str, object]]:
    """城市名 -> {lat, lon, country}。persona-core/cities.json 优先,再补 demo 世界城与扩展表。"""
    coords: Dict[str, Dict[str, object]] = {}
    try:
        data = json.loads(PERSONA_CITIES.read_text(encoding="utf-8"))
        for c in data.get("cities", []):
            nm = c.get("name")
            if nm and "lat" in c and "lon" in c:
                coords[nm] = {"lat": c["lat"], "lon": c["lon"], "country": c.get("region", "")}
    except Exception:
        pass
    for _f, place, country, lat, lon, _a, _b in DEMO_ROWS:
        coords.setdefault(place, {"lat": lat, "lon": lon, "country": country})
    # 扩展表:坐标用已有的(cities.json 更准),但用真实国名覆盖粗略 region 做显示
    for nm, (lat, lon, country) in EXT_CITIES.items():
        if nm in coords:
            coords[nm]["country"] = country
        else:
            coords[nm] = {"lat": lat, "lon": lon, "country": country}
    return coords


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def ensure_demo_photos(photo_dir: Path) -> None:
    photo_dir.mkdir(parents=True, exist_ok=True)
    existing = [p for p in photo_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    csv_path = photo_dir / "locations.csv"
    if existing and csv_path.exists():
        return

    for idx, (filename, city, country, _lat, _lon, c1, c2) in enumerate(DEMO_ROWS, start=1):
        w, h = 1200, 840
        img = Image.new("RGB", (w, h), c2)
        draw = ImageDraw.Draw(img)
        for y in range(h):
            mix = y / h
            r1, g1, b1 = tuple(int(c1[i : i + 2], 16) for i in (1, 3, 5))
            r2, g2, b2 = tuple(int(c2[i : i + 2], 16) for i in (1, 3, 5))
            col = (
                int(r1 * (1 - mix) + r2 * mix),
                int(g1 * (1 - mix) + g2 * mix),
                int(b1 * (1 - mix) + b2 * mix),
            )
            draw.line((0, y, w, y), fill=col)
        for k in range(18):
            x = 70 + ((idx * 137 + k * 97) % (w - 160))
            y = 80 + ((idx * 83 + k * 73) % (h - 210))
            rr = 18 + ((idx + k) % 7) * 12
            draw.ellipse((x - rr, y - rr, x + rr, y + rr), outline=(255, 255, 255), width=3)
        draw.rounded_rectangle((60, 540, 610, 760), radius=22, fill=(22, 24, 28), outline=(255, 255, 255), width=2)
        draw.text((92, 575), "%02d" % idx, font=font(42, True), fill=(245, 226, 174))
        draw.text((92, 632), city, font=font(56, True), fill=(255, 255, 255))
        draw.text((94, 705), country, font=font(30), fill=(220, 224, 224))
        draw.line((700, 140, 1090, 700), fill=(255, 255, 255), width=5)
        draw.line((705, 700, 1095, 145), fill=(255, 255, 255), width=5)
        draw.ellipse((790, 250, 1010, 470), outline=(245, 226, 174), width=10)
        img.save(photo_dir / filename, "JPEG", quality=90, optimize=True)

    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["filename", "place", "country", "lat", "lon"])
        for filename, city, country, lat, lon, _c1, _c2 in DEMO_ROWS:
            writer.writerow([filename, city, country, lat, lon])


def read_locations(photo_dir: Path) -> Dict[str, Dict[str, object]]:
    csv_path = photo_dir / "locations.csv"
    rows: Dict[str, Dict[str, object]] = {}
    if not csv_path.exists():
        return rows
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("filename") or "").strip()
            if not name:
                continue
            rows[name.lower()] = {
                "place": (row.get("place") or "").strip() or Path(name).stem,
                "country": (row.get("country") or "").strip(),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
            }
    return rows


def rational_to_float(value: object) -> float:
    try:
        return float(value)
    except TypeError:
        return float(value[0]) / float(value[1])


def gps_to_decimal(values: Iterable[object], ref: str) -> float:
    deg, minute, sec = [rational_to_float(v) for v in values]
    out = deg + minute / 60.0 + sec / 3600.0
    if ref in {"S", "W"}:
        out *= -1
    return out


def exif_gps(path: Path) -> Optional[Tuple[float, float]]:
    try:
        with Image.open(path) as img:
            raw = img.getexif()
            if not raw:
                return None
            gps_tag = next((k for k, v in TAGS.items() if v == "GPSInfo"), None)
            gps_info = raw.get_ifd(gps_tag) if gps_tag else None
            if not gps_info:
                return None
            gps = {GPSTAGS.get(k, k): v for k, v in gps_info.items()}
            lat = gps_to_decimal(gps["GPSLatitude"], gps.get("GPSLatitudeRef", "N"))
            lon = gps_to_decimal(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E"))
            return lat, lon
    except Exception:
        return None


def encode_image(path: Path, max_side: int, quality: int) -> Tuple[str, float, int, int]:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality, optimize=True)
        data = base64.b64encode(buf.getvalue()).decode("ascii")
        return "data:image/jpeg;base64," + data, img.width / img.height, img.width, img.height


def collect_items(photo_dir: Path, full_quality: int) -> List[Dict[str, object]]:
    locations = read_locations(photo_dir)
    photos = sorted(
        p for p in photo_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )
    items: List[Dict[str, object]] = []
    for idx, path in enumerate(photos):
        loc = locations.get(path.name.lower())
        gps = exif_gps(path)
        if gps:
            lat, lon = gps
            place = loc["place"] if loc else path.stem
            country = loc["country"] if loc else ""
        elif loc:
            lat, lon = float(loc["lat"]), float(loc["lon"])
            place = str(loc["place"])
            country = str(loc["country"])
        else:
            continue
        thumb, aspect, tw, th = encode_image(path, 256, 78)
        full, _a, fw, fh = encode_image(path, 920, full_quality)
        items.append(
            {
                "id": idx,
                "file": path.name,
                "place": place,
                "country": country,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "aspect": round(aspect, 4),
                "thumb": thumb,
                "full": full,
                "thumbSize": [tw, th],
                "fullSize": [fw, fh],
            }
        )
    if not items:
        raise SystemExit("No photos with EXIF GPS or locations.csv rows were found in %s" % photo_dir)
    return items


def read_shapefile_parts(zip_path: Path) -> List[List[Tuple[float, float]]]:
    if not zip_path.exists():
        raise SystemExit("Missing Natural Earth source: %s" % zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        shp_name = next((name for name in zf.namelist() if name.lower().endswith(".shp")), None)
        if not shp_name:
            raise SystemExit("No .shp file found in %s" % zip_path)
        data = zf.read(shp_name)

    parts_out: List[List[Tuple[float, float]]] = []
    offset = 100
    while offset + 8 <= len(data):
        _record_number, content_words = struct.unpack(">2i", data[offset : offset + 8])
        offset += 8
        content_len = content_words * 2
        content = data[offset : offset + content_len]
        offset += content_len
        if len(content) < 44:
            continue
        shape_type = struct.unpack("<i", content[:4])[0]
        if shape_type not in {3, 5, 13, 15, 23, 25, 31}:
            continue
        num_parts, num_points = struct.unpack("<2i", content[36:44])
        if num_parts <= 0 or num_points <= 1:
            continue
        idx_start = 44
        pts_start = idx_start + num_parts * 4
        if pts_start + num_points * 16 > len(content):
            continue
        part_starts = list(struct.unpack("<" + "i" * num_parts, content[idx_start:pts_start]))
        points: List[Tuple[float, float]] = []
        for i in range(num_points):
            lon, lat = struct.unpack("<2d", content[pts_start + i * 16 : pts_start + i * 16 + 16])
            if -181 <= lon <= 181 and -91 <= lat <= 91:
                points.append((float(lon), float(lat)))
            else:
                points.append((0.0, 0.0))
        part_starts.append(num_points)
        for start, end in zip(part_starts, part_starts[1:]):
            part = points[start:end]
            if len(part) >= 3:
                parts_out.append(part)
    return parts_out


def sample_line(line: List[Tuple[float, float]], step: int, min_points: int = 3) -> List[Tuple[float, float]]:
    if len(line) < min_points:
        return []
    if step <= 1:
        sampled = line[:]
    else:
        sampled = line[::step]
        if sampled[-1] != line[-1]:
            sampled.append(line[-1])
    return [(round(lon, 3), round(lat, 3)) for lon, lat in sampled] if len(sampled) >= min_points else []


def compact_lines_for_js(lines: List[List[Tuple[float, float]]], step: int) -> List[List[List[float]]]:
    compact: List[List[List[float]]] = []
    for line in lines:
        sampled = sample_line(line, step, 5)
        if sampled:
            compact.append([[lon, lat] for lon, lat in sampled])
    return compact


def map_x(lon: float, width: int) -> float:
    return (lon + 180.0) / 360.0 * width


def map_y(lat: float, height: int) -> float:
    return (90.0 - lat) / 180.0 * height


def crop_cover(img: Image.Image, size: Tuple[int, int]) -> Image.Image:
    src_w, src_h = img.size
    dst_w, dst_h = size
    src_ratio = src_w / src_h
    dst_ratio = dst_w / dst_h
    if src_ratio < dst_ratio:
        crop_h = int(src_w / dst_ratio)
        top = max(0, (src_h - crop_h) // 2)
        img = img.crop((0, top, src_w, top + crop_h))
    else:
        crop_w = int(src_h * dst_ratio)
        left = max(0, (src_w - crop_w) // 2)
        img = img.crop((left, 0, left + crop_w, src_h))
    return img.resize(size, Image.Resampling.LANCZOS)


def alpha_layer(size: Tuple[int, int]) -> Image.Image:
    return Image.new("RGBA", size, (0, 0, 0, 0))


def draw_wrapped_line(
    draw: ImageDraw.ImageDraw,
    points: List[Tuple[float, float]],
    size: Tuple[int, int],
    fill: Tuple[int, int, int, int],
    width: int,
    jitter: float = 0.0,
) -> None:
    if len(points) < 2:
        return
    w, h = size
    segment: List[Tuple[float, float]] = []
    last_x: Optional[float] = None
    for lon, lat in points:
        x = map_x(lon, w)
        y = map_y(lat, h)
        if jitter:
            wobble = math.sin(lon * 12.91 + lat * 4.17) * jitter
            x += wobble
            y += math.cos(lon * 7.73 - lat * 5.21) * jitter
        if last_x is not None and abs(x - last_x) > w * 0.45:
            if len(segment) > 1:
                draw.line(segment, fill=fill, width=width, joint="curve")
            segment = []
        segment.append((x, y))
        last_x = x
    if len(segment) > 1:
        draw.line(segment, fill=fill, width=width, joint="curve")


def draw_land_fill(layer: Image.Image, land_parts: List[List[Tuple[float, float]]]) -> None:
    draw = ImageDraw.Draw(layer, "RGBA")
    w, h = layer.size
    for part in land_parts:
        if len(part) < 4:
            continue
        xs = [map_x(lon, w) for lon, _lat in part]
        if max(xs) - min(xs) > w * 0.7:
            continue
        pts = [(map_x(lon, w), map_y(lat, h)) for lon, lat in sample_line(part, 2, 4)]
        if len(pts) >= 4:
            draw.polygon(pts, fill=(247, 221, 166, 118))
            draw.line(pts + [pts[0]], fill=(121, 82, 43, 34), width=2)


def draw_rhumb_texture(layer: Image.Image) -> None:
    draw = ImageDraw.Draw(layer, "RGBA")
    w, h = layer.size
    centers = [(-28, 36), (12, 36), (42, 31), (-76, 22), (112, 2)]
    palette = [(166, 47, 32, 92), (32, 132, 84, 84), (92, 61, 35, 48)]
    lat_min, lat_max = -72.0, 72.0
    for ci, (lon0, lat0) in enumerate(centers):
        cx, cy = map_x(lon0, w), map_y(lat0, h)
        for a_idx in range(32):
            angle = math.radians(a_idx * 11.25)
            dx = math.sin(angle)
            dy = math.cos(angle) * 0.56
            candidates = []
            if abs(dx) > 1e-4:
                candidates.extend([(-180 - lon0) / dx, (180 - lon0) / dx])
            if abs(dy) > 1e-4:
                candidates.extend([(lat_min - lat0) / dy, (lat_max - lat0) / dy])
            valid = [
                t
                for t in candidates
                if -180 <= lon0 + dx * t <= 180 and lat_min <= lat0 + dy * t <= lat_max
            ]
            if len(valid) < 2:
                continue
            t0, t1 = min(valid), max(valid)
            p0 = (map_x(lon0 + dx * t0, w), map_y(lat0 + dy * t0, h))
            p1 = (map_x(lon0 + dx * t1, w), map_y(lat0 + dy * t1, h))
            draw.line([p0, p1], fill=palette[(ci + a_idx) % len(palette)], width=2)
        for radius in (24, 42, 58):
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(94, 57, 31, 64), width=2)


def draw_paper_aging(layer: Image.Image) -> None:
    draw = ImageDraw.Draw(layer, "RGBA")
    w, h = layer.size

    # Darkened edges, blurred by stacking wide translucent rectangles.
    for idx, alpha in enumerate((48, 36, 26, 18, 12)):
        pad = idx * 74
        draw.rectangle((pad, pad, w - pad, h - pad), outline=(55, 39, 25, alpha), width=92)

    stains = [
        (0.18, 0.28, 0.16, 0.10, (92, 63, 34, 30)),
        (0.34, 0.73, 0.20, 0.12, (245, 225, 176, 28)),
        (0.57, 0.18, 0.13, 0.08, (86, 60, 34, 24)),
        (0.76, 0.62, 0.22, 0.15, (250, 230, 184, 20)),
        (0.88, 0.32, 0.16, 0.11, (79, 58, 35, 22)),
    ]
    for cx, cy, rx, ry, fill in stains:
        x, y = cx * w, cy * h
        rxx, ryy = rx * w, ry * h
        draw.ellipse((x - rxx, y - ryy, x + rxx, y + ryy), fill=fill)

    for i in range(4600):
        x = (i * 1871) % w
        y = (i * 1307) % h
        length = 10 + (i * 17) % 42
        tint = 255 if i % 3 else 70
        alpha = 10 if tint == 255 else 8
        color = (tint, tint - 16 if tint == 255 else 48, tint - 45 if tint == 255 else 28, alpha)
        draw.line((x, y, min(w, x + length), y + ((i % 7) - 3) * 0.28), fill=color, width=1)


def build_land_mask(land_parts: List[List[Tuple[float, float]]], size: Tuple[int, int]) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    w, h = size
    for part in land_parts:
        if len(part) < 4:
            continue
        xs = [map_x(lon, w) for lon, _lat in part]
        if max(xs) - min(xs) > w * 0.7:
            continue
        pts = [(map_x(lon, w), map_y(lat, h)) for lon, lat in sample_line(part, 2, 4)]
        if len(pts) >= 4:
            draw.polygon(pts, fill=255)
    return mask


def make_data_dot_samples(land_parts: List[List[Tuple[float, float]]]) -> List[List[float]]:
    mask_size = (1440, 720)
    mask = build_land_mask(land_parts, mask_size)
    w, h = mask_size
    dots: List[List[float]] = []
    row = 0
    lat = -58.0
    while lat <= 78.0:
        lon = -180.0 + (0.78 if row % 2 else 0.0)
        while lon <= 180.0:
            jitter_lon = math.sin((lon + 11.7) * 8.13 + lat * 1.31) * 0.22
            jitter_lat = math.cos(lon * 3.91 - (lat + 4.2) * 5.27) * 0.18
            sample_lon = max(-179.95, min(179.95, lon + jitter_lon))
            sample_lat = max(-59.5, min(80.0, lat + jitter_lat))
            x = int(map_x(sample_lon, w)) % w
            y = max(0, min(h - 1, int(map_y(sample_lat, h))))
            if mask.getpixel((x, y)) > 0:
                seed = math.sin(sample_lon * 12.9898 + sample_lat * 78.233) * 43758.5453
                rnd = seed - math.floor(seed)
                size = 0.013 + rnd * 0.011
                alpha = 0.58 + (1.0 - rnd) * 0.34
                tone = 1 if (int((sample_lon + 180) * 3 + (sample_lat + 90) * 5) % 7 == 0) else 0
                dots.append([round(sample_lon, 2), round(sample_lat, 2), round(size, 4), round(alpha, 2), tone])
            lon += 1.56
        lat += 1.08
        row += 1
    return dots


def make_vintage_map_data_url(land_parts: List[List[Tuple[float, float]]], coast_parts: List[List[Tuple[float, float]]]) -> str:
    size = (4096, 2048)
    if PORTOLAN_SCAN.exists():
        scan = crop_cover(Image.open(PORTOLAN_SCAN).convert("RGB"), size)
        scan = scan.filter(ImageFilter.GaussianBlur(1.2))
        gray = ImageOps.grayscale(scan)
        paper = ImageOps.colorize(gray, black="#aa8754", white="#f8e7c4").convert("RGB")
        paper = ImageEnhance.Contrast(paper).enhance(0.78)
        paper = ImageEnhance.Color(paper).enhance(0.42)
    else:
        paper = Image.new("RGB", size, "#ead8ac")

    base = paper.convert("RGBA")
    ocean = Image.new("RGBA", size, (82, 101, 87, 96))
    base = Image.alpha_composite(base, ocean)

    land_layer = alpha_layer(size)
    draw_land_fill(land_layer, land_parts)
    base = Image.alpha_composite(base, land_layer)

    rhumb = alpha_layer(size)
    draw_rhumb_texture(rhumb)
    base = Image.alpha_composite(base, rhumb)

    coast_shadow = alpha_layer(size)
    shadow_draw = ImageDraw.Draw(coast_shadow, "RGBA")
    for line in coast_parts:
        sampled = sample_line(line, 1, 3)
        draw_wrapped_line(shadow_draw, sampled, size, (65, 40, 22, 64), 7, jitter=1.1)
    base = Image.alpha_composite(base, coast_shadow)

    coast_ink = alpha_layer(size)
    ink_draw = ImageDraw.Draw(coast_ink, "RGBA")
    for line in coast_parts:
        sampled = sample_line(line, 1, 3)
        draw_wrapped_line(ink_draw, sampled, size, (92, 64, 35, 186), 3, jitter=0.72)
        draw_wrapped_line(ink_draw, sampled, size, (45, 30, 18, 72), 1, jitter=1.35)
    base = Image.alpha_composite(base, coast_ink)

    stain = alpha_layer(size)
    stain_draw = ImageDraw.Draw(stain, "RGBA")
    for i in range(150):
        x = (i * 1543 % size[0])
        y = (i * 907 % size[1])
        r = 18 + (i * 37 % 110)
        alpha = 8 + (i * 13 % 18)
        stain_draw.ellipse((x - r, y - r, x + r, y + r), fill=(88, 50, 27, alpha))
    base = Image.alpha_composite(base, stain)

    aging = alpha_layer(size)
    draw_paper_aging(aging)
    aging = aging.filter(ImageFilter.GaussianBlur(0.45))
    base = Image.alpha_composite(base, aging)

    buf = io.BytesIO()
    base.convert("RGB").save(buf, "JPEG", quality=86, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def make_black_marble_data_url() -> str:
    if not BLACK_MARBLE_SOURCE.exists():
        raise SystemExit("Missing NASA Black Marble source: %s" % BLACK_MARBLE_SOURCE)
    img = Image.open(BLACK_MARBLE_SOURCE).convert("RGB")
    img = ImageOps.fit(img, (2048, 1024), method=Image.Resampling.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.18)
    img = ImageEnhance.Color(img).enhance(1.08)
    img = ImageEnhance.Sharpness(img).enhance(1.18)
    BLACK_MARBLE_2K.parent.mkdir(parents=True, exist_ok=True)
    img.save(BLACK_MARBLE_2K, "JPEG", quality=84, optimize=True, progressive=True)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=84, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<link rel="icon" href="data:,">
<title>@@PAGE_TITLE@@</title>
<meta property="og:title" content="@@PAGE_TITLE@@">
<meta property="og:description" content="@@OG_DESC@@">
<meta property="og:type" content="website">
<meta property="og:image" content="@@OG_IMAGE@@">
<meta name="description" content="@@OG_DESC@@">
<style>
  :root {
    --bg:#071017; --panel:rgba(12,18,22,.78); --line:rgba(241,224,178,.24);
    --ink:#f7f0dc; --muted:#b8ad92; --accent:#a7472f; --accent2:#2aa48f;
  }
  * { box-sizing:border-box; }
  html, body { width:100%; height:100%; margin:0; overflow:hidden; background:var(--bg); color:var(--ink);
    font-family:Georgia,"Times New Roman","Noto Serif SC","Songti SC",serif; -webkit-font-smoothing:antialiased; }
  body.data { --bg:#030811; --panel:rgba(5,12,20,.78); --line:rgba(77,204,255,.22);
    --ink:#e8fbff; --muted:#86a9ba; --accent:#47d7ff; --accent2:#ffd166;
    font-family:"Segoe UI","Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif; }
  body.night { --bg:#01040b; --panel:rgba(3,9,18,.76); --line:rgba(95,196,255,.30);
    --ink:#f2fbff; --muted:#91b7d3; --accent:#68d8ff; --accent2:#f7d783;
    font-family:"Segoe UI","Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif; }
  #gl { position:fixed; inset:0; width:100%; height:100%; display:block; touch-action:none; }
  #topbar { position:fixed; left:14px; right:14px; top:12px; z-index:20; display:flex; align-items:center;
    justify-content:space-between; gap:10px; pointer-events:none; }
  .brand { min-width:0; color:var(--ink); text-shadow:0 1px 10px rgba(0,0,0,.34); font-size:18px; font-weight:700; }
  .brand small { display:block; margin-top:2px; color:var(--muted); font-size:12px; font-weight:400; }
  .controls { display:flex; align-items:center; gap:8px; pointer-events:auto; background:var(--panel);
    border:1px solid var(--line); border-radius:8px; padding:6px; backdrop-filter:blur(12px); }
  button { height:34px; border-radius:6px; border:1px solid transparent; background:transparent; color:var(--ink);
    font:inherit; font-size:13px; cursor:pointer; }
  button.icon { width:34px; font-size:22px; line-height:1; font-family:Arial,sans-serif; }
  button.theme { padding:0 10px; color:var(--muted); }
  button.theme.active { color:var(--ink); border-color:var(--line); background:rgba(255,255,255,.09); }
  #status { position:fixed; left:14px; bottom:14px; z-index:20; min-width:210px; max-width:min(360px,calc(100vw - 28px));
    padding:10px 12px; background:var(--panel); border:1px solid var(--line); border-radius:8px;
    backdrop-filter:blur(12px); pointer-events:none; }
  #status b { display:block; font-size:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  #status span { display:block; margin-top:4px; color:var(--muted); font-size:12px; }
  #compass { position:fixed; right:16px; bottom:18px; z-index:20; width:78px; height:78px; opacity:.9;
    color:var(--accent); pointer-events:none; }
  body.data #compass, body.night #compass { display:none; }
  #compass svg { width:100%; height:100%; filter:drop-shadow(0 2px 8px rgba(0,0,0,.3)); }
  #lightbox { position:fixed; inset:0; z-index:60; display:none; align-items:center; justify-content:center;
    background:rgba(3,5,7,.88); padding:18px; cursor:zoom-out; }
  #lightbox.open { display:flex; }
  #lightbox figure { margin:0; max-width:min(960px,96vw); max-height:92vh; display:flex; flex-direction:column; gap:10px;
    transition:transform .42s cubic-bezier(.2,.85,.25,1), opacity .42s ease; will-change:transform,opacity; }
  #lightbox img { max-width:100%; max-height:82vh; object-fit:contain; border-radius:8px; box-shadow:0 20px 70px rgba(0,0,0,.48); }
  #lightbox figcaption { color:var(--ink); font-size:14px; text-align:center; }
  #lightboxClose { position:absolute; top:18px; right:20px; width:44px; height:44px; border-radius:50%;
    background:rgba(20,16,12,.55); color:#f3ead4; border:1px solid rgba(243,234,212,.35);
    font-size:26px; line-height:1; cursor:pointer; display:flex; align-items:center; justify-content:center;
    backdrop-filter:blur(4px); transition:background .15s; }
  #lightboxClose:hover { background:rgba(40,32,24,.8); }
  /* 按钮层级:图标按钮(缩放/复位)弱化为次级,主题切换为主操作;hover 提亮 */
  button:hover { color:var(--ink); background:rgba(255,255,255,.07); }
  button.icon { color:var(--muted); }
  .controls .sep { width:1px; align-self:stretch; margin:2px 2px; background:var(--line); }
  /* 内容优先:静止数秒后 chrome 淡隐,一动就回来 */
  #topbar, #status, #compass { transition:opacity .55s ease; }
  body.idle #topbar, body.idle #status { opacity:0; }
  body.idle #compass { opacity:0; }
  body.idle .controls { pointer-events:none; }
  /* 极轻 onboarding 提示 */
  #hint { position:fixed; left:50%; bottom:88px; transform:translateX(-50%); z-index:30;
    padding:9px 16px; background:var(--panel); border:1px solid var(--line); border-radius:999px;
    color:var(--ink); font-size:13px; letter-spacing:.03em; backdrop-filter:blur(12px);
    opacity:0; pointer-events:none; transition:opacity .6s ease; white-space:nowrap;
    box-shadow:0 6px 24px rgba(0,0,0,.32); }
  #hint.show { opacity:.96; }
  /* 主题切换溶解过渡层 */
  #themeFade { position:fixed; inset:0; z-index:50; background:var(--bg); opacity:0;
    pointer-events:none; transition:opacity .26s ease; }
  #themeFade.on { opacity:1; }
  #fallback { position:fixed; inset:0; z-index:80; display:none; overflow:auto; padding:24px; background:#101316; color:#f7f0dc; }
  #fallback.visible { display:block; }
  #fallback img { width:120px; height:86px; object-fit:cover; margin:8px; border-radius:8px; }
  @media (max-width:600px) {
    #topbar { align-items:stretch; flex-direction:column; left:10px; right:10px; top:10px; }
    .brand { font-size:15px; }
    .brand small { font-size:11px; }
    .controls { gap:4px; padding:5px; max-width:none; flex-wrap:wrap; justify-content:center; }
    button { height:44px; min-height:44px; font-size:13px; }
    button.icon { width:44px; min-width:44px; font-size:21px; }
    button.theme { padding:0 12px; }
    #status { bottom:10px; left:10px; right:10px; max-width:none; }
    #compass { width:62px; height:62px; right:12px; bottom:86px; }
  }
</style>
</head>
<body class="vintage">
<div id="boot" style="position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:#071017;color:#cdbf9d;font:15px/1.6 Georgia,serif;z-index:99;letter-spacing:.2em;">正在展开你的地球…</div>
<canvas id="gl"></canvas>
<div id="topbar">
  <div class="brand">Travel Globe<small id="countLabel"></small></div>
  <div class="controls" aria-label="controls">
    <button class="theme active" data-theme="vintage" aria-pressed="true">复古航海图</button>
    <button class="theme" data-theme="night" aria-pressed="false">写实夜景</button>
    <span class="sep" aria-hidden="true"></span>
    <button id="zoomOut" class="icon" title="Zoom out" aria-label="Zoom out">-</button>
    <button id="zoomIn" class="icon" title="Zoom in" aria-label="Zoom in">+</button>
    <button id="resetView" class="icon" title="重置视角" aria-label="重置视角">⟳</button>
  </div>
</div>
<style>
#actionBar{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(env(safe-area-inset-bottom,0px) + 18px);z-index:30;display:flex;gap:10px;align-items:center;}
#actionBar .pill{padding:13px 22px;border-radius:999px;border:1px solid rgba(233,217,171,.5);background:rgba(20,16,10,.8);color:#ecdcae;font-size:15px;font-weight:600;cursor:pointer;-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);box-shadow:0 6px 22px rgba(0,0,0,.45);text-decoration:none;display:inline-block;line-height:1.2;}
#actionBar .pill.primary{background:linear-gradient(180deg,#e8be6f,#c4964c);color:#1a140a;border-color:rgba(233,217,171,.8);}
#actionBar .pill.mini{padding:11px 16px;font-size:13px;opacity:.92;}
body.tour #topbar,body.tour #status,body.tour #compass,body.tour #actionBar,body.tour #hint{display:none !important;}
#tourBrand{display:none;position:fixed;right:18px;bottom:calc(env(safe-area-inset-bottom,0px) + 16px);z-index:31;color:rgba(236,220,174,.85);font:600 14px Georgia,serif;letter-spacing:.14em;text-shadow:0 1px 8px rgba(0,0,0,.6);pointer-events:none;}
body.tour #tourBrand{display:block;}
</style>
<div id="actionBar">
  <a id="ctaCreate" class="pill primary" href="create.html" style="display:none;">🌍 创建我的旅行地球 →</a>
  <button id="exportImg" class="pill" aria-label="保存我的旅行地球" style="display:none;">⬇ 保存我的旅行地球</button>
  <a id="editCities" class="pill mini" href="create.html" style="display:none;">✎ 改城市</a>
</div>
<div id="tourBrand" aria-hidden="true">✦ 我的旅行地球</div>
<div id="status"><b id="statusTitle"></b><span id="statusSub"></span></div>
<div id="compass" aria-hidden="true">
  <svg viewBox="0 0 100 100">
    <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" stroke-width="2"/>
    <path id="compassNeedle" d="M50 7 L59 50 L50 93 L41 50 Z" fill="currentColor" opacity=".86"/>
    <path d="M50 18 L55 50 L50 82 L45 50 Z" fill="#f7f0dc" opacity=".7"/>
    <text x="50" y="15" text-anchor="middle" fill="currentColor" font-size="13" font-family="Georgia">N</text>
    <text x="50" y="92" text-anchor="middle" fill="currentColor" font-size="11" font-family="Georgia">S</text>
    <text x="10" y="54" text-anchor="middle" fill="currentColor" font-size="11" font-family="Georgia">W</text>
    <text x="90" y="54" text-anchor="middle" fill="currentColor" font-size="11" font-family="Georgia">E</text>
  </svg>
</div>
<div id="hint" aria-hidden="true">拖动旋转 · 滚轮缩放 · 点照片看大图</div>
<div id="themeFade" aria-hidden="true"></div>
<div id="lightbox" role="dialog" aria-modal="true" aria-label="照片大图"><button id="lightboxClose" aria-label="关闭">&times;</button><figure><img id="lightboxImg" alt=""><figcaption id="lightboxCap"></figcaption></figure></div>
<div id="fallback"><h1>Travel Globe Album</h1><div id="fallbackList"></div></div>
<script>@@THREE@@</script>
<script>
var DEMO_ITEMS = @@ITEMS@@;
var CITY_COORDS = @@CITY_COORDS@@;
var FORCE_DEMO = @@FORCE_DEMO@@; // album 演示页锁定内置数据,不被 localStorage/URL 劫持
(function(){ var b = document.getElementById('boot'); if (b) b.parentNode.removeChild(b); })();
// 把城市名列表 join 成地球能吃的 item(无照片,运行时定位)
function citiesToItems(names){
  var out = [];
  for (var i = 0; i < names.length; i++) {
    var nm = String(names[i]).trim();
    if (!nm) continue;
    var c = CITY_COORDS[nm];
    if (!c) continue;
    out.push({ id: out.length, place: nm, country: (c.country || ''), lat: c.lat, lon: c.lon, custom: true });
  }
  return out;
}
// 轻量版(无内置照片)的落地示例:精选世界名城,铭牌钉展示产品真实形态
var SHOWCASE_CITIES = ['上海','东京','京都','曼谷','新加坡','巴厘岛','巴黎','罗马','巴塞罗那','伦敦','纽约','旧金山','温哥华','悉尼','开普敦','里约热内卢','雷克雅未克'];
var IS_SHOWCASE = false;
// 运行时数据源:URL ?cities= → localStorage('myGlobeCities') → 内置 demo → 示例名城(轻量版)
var ITEMS = (function(){
  if (FORCE_DEMO) return DEMO_ITEMS;
  try {
    var qs = new URLSearchParams(window.location.search);
    var q = qs.get('cities');
    if (q) { var it = citiesToItems(q.split(',')); if (it.length) return it; }
    var raw = localStorage.getItem('myGlobeCities');
    if (raw) { var arr = JSON.parse(raw); if (arr && arr.length) { var it2 = citiesToItems(arr); if (it2.length) return it2; } }
  } catch (e) {}
  if (DEMO_ITEMS.length) return DEMO_ITEMS;
  IS_SHOWCASE = true;
  return citiesToItems(SHOWCASE_CITIES);
})();
var TOUR = (function(){ try { return new URLSearchParams(window.location.search).get('tour') === '1'; } catch(e){ return false; } })();
var TOUR_SWITCH = (function(){ try { return new URLSearchParams(window.location.search).get('switch') === '1'; } catch(e){ return false; } })();
var VINTAGE_MAP_URL = @@VINTAGE_MAP_URL@@;
var BLACK_MARBLE_URL = @@BLACK_MARBLE_URL@@;
var COAST_LINES = @@COAST_LINES@@;
var DATA_DOTS = @@DATA_DOTS@@;
var THEMES = {
  vintage: {
    label: '复古航海图', locked: false, body: 'vintage',
    bg: 0x15110c, fog: 0x15110c, globe: 'vintage', route: 0x8f3f28,
    pinText: '#3c2116', pinPaper: '#f5efdd', pinBorder: '#ead9ad', cluster: '#8f3f28',
    glow: 0xd0a968, atmosphere: 0x2b2118
  },
  data: {
    label: '点阵数据风', locked: false, body: 'data',
    bg: 0x02050a, fog: 0x02050a, globe: 'data', route: 0x43d8ff,
    pinText: '#e9fbff', pinPaper: '#06111b', pinBorder: '#37d6ff', cluster: '#37d6ff',
    glow: 0x47d7ff, atmosphere: 0x37d6ff
  },
  night: {
    label: '写实夜景', locked: false, body: 'night',
    bg: 0x01040b, fog: 0x01040b, globe: 'night', route: 0x77d8ff,
    pinText: '#f3fbff', pinPaper: '#06111d', pinBorder: '#6ad8ff', cluster: '#76e2ff',
    glow: 0x74dfff, atmosphere: 0x5ecbff, anchor: 0x79e6ff
  }
};

(function(){
'use strict';

var R = 2.22;
// 母港 / 起航点 — 航线与帆船从这里出发,海图上这片会被标记加深。改这里即可换成你的家乡。
var HOME_PORT = (function(){
  try {
    var qs = new URLSearchParams(window.location.search);
    var h = qs.get('home');
    if (h && CITY_COORDS[h]) return { name: h, lat: CITY_COORDS[h].lat, lon: CITY_COORDS[h].lon };
  } catch (e) {}
  if (ITEMS && ITEMS.length && ITEMS[0].custom) return { name: ITEMS[0].place, lat: ITEMS[0].lat, lon: ITEMS[0].lon };
  return { name: '上海', lat: 31.23, lon: 121.47 };
})();
var renderer, scene, camera, earth, atmosphere, vintageMat, dataMat, nightMat, routeLine, dataRouteLine, dataRoutePoints;
var voyageShip = null, routeCurvePts = null, shipT = 0;
var vintageAtmosphereMat, dataAtmosphereMat, nightAtmosphereMat;
var graticuleGroup = new THREE.Group();
var coastlineGroup = new THREE.Group();
var decorGroup = new THREE.Group();
var dataDots = new THREE.Group();
var auroraGroup = new THREE.Group();
var anchorLines = [];
var anchorBeams = [];
var photoGroups = [];
var clusterSprites = [];
var clusters = [];
var currentTheme = 'vintage';
var radius = 8.4, targetRadius = 8.4;
var rotX = 0.18, rotY = 2.10, targetRotX = rotX, targetRotY = rotY;
var isDragging = false, lastX = 0, lastY = 0;
var dragVec = null;
var dragMoved = false;
var urlParams = new URLSearchParams(window.location.search);
var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
var introRequested = !reduced && urlParams.get('intro') !== '0' && !urlParams.has('lat') && !urlParams.has('lon') && !urlParams.has('dist');
var userControlled = false;
var dockMode = true;   // Dock 磁吸:卡片默认收起,靠近屏幕中心才放大
var intro = {
  active: false,
  done: false,
  start: 0,
  photoLead: 1700,
  photoDuration: 820,
  settle: 760,
  total: 0,
  startRotX: rotX,
  startRotY: rotY,
  startRadius: radius
};
var ray = new THREE.Raycaster();
var pointer = new THREE.Vector2();
var cv = document.getElementById('gl');

var WORLD_POLYS = [
  [[-168,72],[-140,70],[-124,58],[-124,49],[-101,50],[-82,43],[-66,48],[-58,57],[-52,70],[-90,75],[-126,72]],
  [[-125,49],[-114,34],[-101,20],[-88,16],[-82,9],[-79,-1],[-73,-10],[-71,-28],[-64,-52],[-48,-55],[-36,-18],[-44,2],[-58,8],[-76,19],[-97,26]],
  [[-18,35],[-5,51],[25,57],[57,55],[82,68],[137,55],[156,46],[140,24],[116,18],[99,8],[78,21],[58,25],[43,13],[33,30],[16,33],[3,43]],
  [[-17,33],[10,36],[33,29],[45,12],[51,-5],[41,-17],[31,-35],[18,-34],[8,-18],[-6,-5],[-15,10]],
  [[112,-12],[138,-10],[154,-28],[145,-43],[119,-37],[110,-24]],
  [[43,13],[56,24],[65,20],[58,8],[48,7]],
  [[-51,70],[-30,76],[-18,68],[-28,61],[-46,60]],
  [[166,-35],[178,-38],[174,-46],[165,-44]]
];

var IS_USER = !!(ITEMS[0] && ITEMS[0].custom);
var PAGE_TITLE = (function(){ try { return new URLSearchParams(window.location.search).get('title') || ''; } catch(e){ return ''; } })() || (IS_SHOWCASE ? '我的旅行地球' : (IS_USER ? '我的旅行地球' : '世界相册'));
function distinctCountries(){ var s = {}; ITEMS.forEach(function(it){ if (it.country) s[it.country] = 1; }); return Object.keys(s).length; }
document.getElementById('countLabel').textContent = IS_USER ? (ITEMS.length + ' 座城市') : (ITEMS.length + ' photos');
document.getElementById('statusTitle').textContent = PAGE_TITLE;
document.getElementById('statusSub').textContent = IS_USER ? (ITEMS.length + ' 城 · ' + distinctCountries() + ' 国/地区' + (IS_SHOWCASE ? ' · 示例' : '')) : ('0 groups / ' + ITEMS.length + ' photos');
// 动作栏:真用户=保存+改城市;示例=创建(主)+保存;相册demo=保存+创建(次)
(function(){
  var cta = document.getElementById('ctaCreate'), exp = document.getElementById('exportImg'), edit = document.getElementById('editCities');
  if (IS_SHOWCASE) { cta.style.display = 'inline-block'; exp.style.display = 'inline-block'; exp.classList.add('mini'); exp.textContent = '⬇ 保存'; }
  else if (IS_USER) {
    exp.style.display = 'inline-block'; edit.style.display = 'inline-block';
    // 把当前城市带给编辑页:分享链接打开/换设备的用户(localStorage 为空)也不丢城市
    try { edit.href = 'create.html?cities=' + encodeURIComponent(ITEMS.map(function(it){ return it.place; }).join(',')); } catch(e){}
  }
  else { exp.style.display = 'inline-block'; cta.style.display = 'inline-block'; cta.classList.remove('primary'); cta.classList.add('mini'); cta.textContent = '🌍 创建我的 →'; }
})();
if (TOUR) document.body.classList.add('tour');

try {
  renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: false, preserveDrawingBuffer: true });
} catch (e) {
  showFallback();
  return;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.7));
renderer.outputColorSpace = THREE.SRGBColorSpace;
scene = new THREE.Scene();
scene.fog = new THREE.Fog(0x071017, 7.5, 13.5);
camera = new THREE.PerspectiveCamera(42, 1, 0.1, 80);

var hemi = new THREE.HemisphereLight(0xf1ddb3, 0x17110b, 1.55);
scene.add(hemi);
var ambient = new THREE.AmbientLight(0xc09a65, .46);
scene.add(ambient);
var key = new THREE.DirectionalLight(0xffedc9, 2.45);
key.position.set(4.5, 3.2, 5.2);
scene.add(key);
var rim = new THREE.DirectionalLight(0x9d7149, .82);
rim.position.set(-5.0, 1.4, -4.0);
scene.add(rim);

var vintageTexture = new THREE.TextureLoader().load(VINTAGE_MAP_URL);
vintageTexture.colorSpace = THREE.SRGBColorSpace;
vintageTexture.anisotropy = renderer.capabilities.getMaxAnisotropy ? Math.min(8, renderer.capabilities.getMaxAnisotropy()) : 1;
var nightTexture = new THREE.TextureLoader().load(BLACK_MARBLE_URL);
nightTexture.colorSpace = THREE.SRGBColorSpace;
nightTexture.anisotropy = renderer.capabilities.getMaxAnisotropy ? Math.min(8, renderer.capabilities.getMaxAnisotropy()) : 1;
vintageMat = new THREE.MeshStandardMaterial({
  map: vintageTexture,
  color: 0xfff0ca,
  emissive: 0x2a1c10,
  emissiveIntensity: .22,
  roughness: .94,
  metalness: .02
});
dataMat = new THREE.MeshStandardMaterial({
  color: 0x020912,
  emissive: 0x021622,
  emissiveIntensity: .42,
  roughness: .92,
  metalness: .0
});
nightMat = new THREE.MeshStandardMaterial({
  map: nightTexture,
  emissiveMap: nightTexture,
  color: 0xbfd7ff,
  emissive: 0x8ab9ff,
  emissiveIntensity: 1.18,
  roughness: .78,
  metalness: .0
});
nightMat.onBeforeCompile = function(shader){
  shader.uniforms.uTime = { value: 0 };
  shader.uniforms.uSunDir = { value: new THREE.Vector3(1, 0, 0) };
  // pass world-space normal to the fragment shader
  shader.vertexShader = 'varying vec3 vWNormal;\n' + shader.vertexShader.replace(
    '#include <beginnormal_vertex>',
    '#include <beginnormal_vertex>\n  vWNormal = mat3(modelMatrix) * objectNormal;'
  );
  // gate city lights to the night side; tint the day side ocean-blue; soft terminator band
  shader.fragmentShader = 'uniform float uTime;\nuniform vec3 uSunDir;\nvarying vec3 vWNormal;\n' +
    shader.fragmentShader.replace(
      '#include <emissivemap_fragment>',
      '#include <emissivemap_fragment>\n' +
      '  float sunDot = dot(normalize(vWNormal), normalize(uSunDir));\n' +
      '  float nightF = smoothstep(0.10, -0.22, sunDot);\n' +
      '  totalEmissiveRadiance *= nightF * (0.9 + 0.1 * sin(uTime * 1.7 + vWNormal.x * 40.0));\n' +
      '  float dayF = smoothstep(-0.08, 0.55, sunDot);\n' +
      '  float twilight = smoothstep(0.18, -0.02, abs(sunDot)) ;\n' +
      '  totalEmissiveRadiance += vec3(0.045, 0.115, 0.235) * dayF;\n' +
      '  totalEmissiveRadiance += vec3(0.22, 0.12, 0.05) * twilight * 0.5;\n'
    );
  nightMat.userData.shader = shader;
};
earth = new THREE.Mesh(new THREE.SphereGeometry(R, 96, 64), vintageMat);
scene.add(earth);

var cloudTex = (function(){
  var c = document.createElement('canvas'); c.width = 1024; c.height = 512;
  var ctx = c.getContext('2d'); var id = ctx.createImageData(1024, 512); var d = id.data;
  function rnd(x, y){ var n = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453; return n - Math.floor(n); }
  function smooth(x, y){ var xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
    var tl = rnd(xi, yi), tr = rnd(xi + 1, yi), bl = rnd(xi, yi + 1), br = rnd(xi + 1, yi + 1);
    var u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    return tl * (1 - u) * (1 - v) + tr * u * (1 - v) + bl * (1 - u) * v + br * u * v; }
  function fbm(x, y){ var s = 0, a = .5, f = 1; for (var i = 0; i < 5; i++){ s += a * smooth(x * f, y * f); f *= 2; a *= .5; } return s; }
  for (var y = 0; y < 512; y++) for (var x = 0; x < 1024; x++){
    var v = fbm(x / 70, y / 70); v = Math.max(0, (v - .48) / .52); v = v * v;
    var i = (y * 1024 + x) * 4; d[i] = d[i + 1] = d[i + 2] = 255; d[i + 3] = Math.min(255, v * 255); }
  ctx.putImageData(id, 0, 0);
  var t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
})();
var cloudMesh = new THREE.Mesh(new THREE.SphereGeometry(R * 1.015, 64, 48),
  new THREE.MeshStandardMaterial({ alphaMap: cloudTex, transparent: true, opacity: .5, color: 0xdbe7ff, emissive: 0x3a5a90, emissiveIntensity: .25, depthWrite: false, roughness: 1, metalness: 0 }));
cloudMesh.visible = false; scene.add(cloudMesh);

// soft radial glow sprite — gives stars/constellation nodes a bloom-like halo (no post-processing needed)
var glowTex = (function(){
  var c = document.createElement('canvas'); c.width = c.height = 64;
  var g = c.getContext('2d');
  var grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grd.addColorStop(0, 'rgba(255,255,255,1)');
  grd.addColorStop(.25, 'rgba(255,250,235,.85)');
  grd.addColorStop(.5, 'rgba(255,240,200,.25)');
  grd.addColorStop(1, 'rgba(255,235,190,0)');
  g.fillStyle = grd; g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
})();

var starGeo = new THREE.BufferGeometry();
var starN = 3000; var starPos = new Float32Array(starN * 3); var starCol = new Float32Array(starN * 3);
for (var si = 0; si < starN; si++){
  var sr = 32 + Math.random() * 14, st = Math.acos(2 * Math.random() - 1), sp = 2 * Math.PI * Math.random();
  starPos[si*3] = sr*Math.sin(st)*Math.cos(sp); starPos[si*3+1] = sr*Math.cos(st); starPos[si*3+2] = sr*Math.sin(st)*Math.sin(sp);
  var w = .35 + Math.random() * Math.random() * .65; starCol[si*3] = w; starCol[si*3+1] = w * .95; starCol[si*3+2] = w * .82;
}
starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
starGeo.setAttribute('color', new THREE.BufferAttribute(starCol, 3));
var starField = new THREE.Points(starGeo, new THREE.PointsMaterial({ size: 4.2, map: glowTex, sizeAttenuation: false, vertexColors: true, transparent: true, opacity: .95, depthWrite: false, fog: false, blending: THREE.AdditiveBlending }));
scene.add(starField);

var conPts = [];
for (var ci = 0; ci < 78; ci++){
  var a = Math.floor(Math.random() * starN), bestj = -1, bestd = 1e9;
  for (var jj = 0; jj < 60; jj++){
    var cand = Math.floor(Math.random() * starN); if (cand === a) continue;
    var dx = starPos[a*3]-starPos[cand*3], dy = starPos[a*3+1]-starPos[cand*3+1], dz = starPos[a*3+2]-starPos[cand*3+2];
    var d2 = dx*dx + dy*dy + dz*dz; if (d2 < bestd && d2 > 6){ bestd = d2; bestj = cand; }
  }
  if (bestj >= 0 && bestd < 72) conPts.push(starPos[a*3],starPos[a*3+1],starPos[a*3+2], starPos[bestj*3],starPos[bestj*3+1],starPos[bestj*3+2]);
}
var conGeo = new THREE.BufferGeometry(); conGeo.setAttribute('position', new THREE.Float32BufferAttribute(conPts, 3));
var constellation = new THREE.LineSegments(conGeo, new THREE.LineBasicMaterial({ color: 0xf0c255, transparent: true, opacity: .72, depthWrite: false, fog: false, blending: THREE.AdditiveBlending }));
constellation.visible = false; scene.add(constellation);

// glowing gold nodes at the constellation joints
var nodeGeo = new THREE.BufferGeometry(); nodeGeo.setAttribute('position', new THREE.Float32BufferAttribute(conPts.slice(), 3));
var conNodes = new THREE.Points(nodeGeo, new THREE.PointsMaterial({ size: 7, map: glowTex, color: 0xf3cf78, sizeAttenuation: false, transparent: true, opacity: .9, depthWrite: false, fog: false, blending: THREE.AdditiveBlending }));
conNodes.visible = false; scene.add(conNodes);

vintageAtmosphereMat = new THREE.MeshBasicMaterial({ color: 0x627597, transparent: true, opacity: .18, side: THREE.BackSide });
dataAtmosphereMat = new THREE.ShaderMaterial({
  transparent: true,
  depthWrite: false,
  side: THREE.BackSide,
  uniforms: {
    glowColor: { value: new THREE.Color(0x37d6ff) },
    opacity: { value: .46 },
    power: { value: 2.35 }
  },
  vertexShader: 'varying vec3 vNormal; void main(){ vNormal = normalize(normalMatrix * normal); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: 'uniform vec3 glowColor; uniform float opacity; uniform float power; varying vec3 vNormal; void main(){ float rim = pow(1.0 - abs(dot(normalize(vNormal), vec3(0.0, 0.0, 1.0))), power); gl_FragColor = vec4(glowColor, rim * opacity); }'
});
nightAtmosphereMat = new THREE.ShaderMaterial({
  transparent: true,
  depthWrite: false,
  side: THREE.BackSide,
  blending: THREE.AdditiveBlending,
  uniforms: {
    glowColor: { value: new THREE.Color(0x5ecbff) },
    lowColor: { value: new THREE.Color(0x123dff) },
    opacity: { value: .72 },
    power: { value: 1.78 }
  },
  vertexShader: 'varying vec3 vNormal; varying vec3 vWorld; void main(){ vNormal = normalize(normalMatrix * normal); vec4 world = modelMatrix * vec4(position, 1.0); vWorld = world.xyz; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: 'uniform vec3 glowColor; uniform vec3 lowColor; uniform float opacity; uniform float power; varying vec3 vNormal; varying vec3 vWorld; void main(){ float rim = pow(1.0 - abs(dot(normalize(vNormal), vec3(0.0, 0.0, 1.0))), power); float polar = smoothstep(0.10, 1.0, normalize(vWorld).y); vec3 col = mix(lowColor, glowColor, clamp(rim + polar * .35, 0.0, 1.0)); gl_FragColor = vec4(col, rim * opacity); }'
});
atmosphere = new THREE.Mesh(
  new THREE.SphereGeometry(R * 1.018, 96, 64),
  vintageAtmosphereMat
);
scene.add(atmosphere);

scene.add(graticuleGroup);
scene.add(coastlineGroup);
scene.add(decorGroup);
scene.add(dataDots);
scene.add(auroraGroup);
buildGraticule();
buildCoastlines();
buildDecor();
buildDataDots();
buildAurora();
clusters = buildClusters(ITEMS);
buildRoutes();
buildPins();
buildClustersSprites();
switchTheme('vintage');
resize();

window.addEventListener('resize', resize);
cv.addEventListener('pointerdown', onPointerDown);
window.addEventListener('pointermove', onPointerMove, { passive: false });
window.addEventListener('pointerup', onPointerUp);
window.addEventListener('pointercancel', onPointerUp);
cv.addEventListener('wheel', onWheel, { passive: false });
cv.addEventListener('click', onClick);
document.getElementById('zoomIn').onclick = function(){ takeControl(); targetRadius = Math.max(3.6, targetRadius - .62); };
document.getElementById('zoomOut').onclick = function(){ takeControl(); targetRadius = Math.min(10.8, targetRadius + .62); };
document.getElementById('resetView').onclick = function(){
  targetRadius = 8.4;          // 默认停留距离
  targetRotX = 0.18;           // 默认倾角
  targetRotY = rotY;           // 经度保持当前,避免猛地倒转
  userControlled = false;      // 恢复轻柔自动旋转
  setStatus('视角已复位', IS_USER ? (ITEMS.length + ' 座城市') : (ITEMS.length + ' 张照片'));
};
(function(){ var b = document.getElementById('exportImg'); if (b) b.onclick = exportGlobeImage; })();
document.querySelectorAll('button.theme').forEach(function(btn){
  btn.onclick = function(){ takeControl(); transitionTheme(btn.getAttribute('data-theme')); };
});
// 主题切换:用一层溶解过渡盖住硬切
function transitionTheme(key){
  if (key === currentTheme || !THEMES[key] || THEMES[key].locked) return;
  if (reduced) { switchTheme(key); return; }
  var fade = document.getElementById('themeFade');
  fade.classList.add('on');
  setTimeout(function(){ switchTheme(key); }, 240);
  setTimeout(function(){ fade.classList.remove('on'); }, 320);
}

// 内容优先:静止数秒后 chrome 淡隐,一动即回;开场后浮一行轻提示
var idleTimer = null;
function wakeChrome(){
  document.body.classList.remove('idle');
  if (idleTimer) clearTimeout(idleTimer);
  idleTimer = setTimeout(function(){
    if (!intro.active && !document.getElementById('lightbox').classList.contains('open'))
      document.body.classList.add('idle');
  }, 3800);
}
function hideHint(){ var h = document.getElementById('hint'); if (h) h.classList.remove('show'); }
function showHint(){
  if (reduced) return;
  var h = document.getElementById('hint'); if (!h) return;
  h.classList.add('show');
  setTimeout(hideHint, 3600);
}
['pointermove', 'pointerdown', 'wheel', 'keydown', 'touchstart'].forEach(function(ev){
  window.addEventListener(ev, function(){ wakeChrome(); hideHint(); }, { passive: true });
});
wakeChrome();
var lastFocusBeforeLightbox = null;
var lightboxOrigin = { x: 0, y: 0 };
function closeLightbox(){
  var lb = document.getElementById('lightbox');
  if (!lb.classList.contains('open')) return;
  var fig = lb.querySelector('figure');
  if (reduced || !fig) {
    lb.classList.remove('open');
  } else {
    // 缩回照片在地球上的位置
    fig.style.transition = '';
    fig.style.transform = 'translate(' + lightboxOrigin.x + 'px,' + lightboxOrigin.y + 'px) scale(.16)';
    fig.style.opacity = '0';
    setTimeout(function(){
      lb.classList.remove('open');
      fig.style.transition = 'none'; fig.style.transform = ''; fig.style.opacity = '';
    }, 380);
  }
  if (lastFocusBeforeLightbox && lastFocusBeforeLightbox.focus) lastFocusBeforeLightbox.focus();
}
document.getElementById('lightbox').onclick = function(e){ if (e.target === this) closeLightbox(); };
document.getElementById('lightboxClose').onclick = function(e){ e.stopPropagation(); closeLightbox(); };
window.addEventListener('keydown', function(e){ if (e.key === 'Escape') closeLightbox(); });
var requestedTheme = urlParams.get('theme');
if (THEMES[requestedTheme] && !THEMES[requestedTheme].locked) switchTheme(requestedTheme);
var viewLat = parseFloat(urlParams.get('lat'));
var viewLon = parseFloat(urlParams.get('lon'));
var viewDist = parseFloat(urlParams.get('dist'));
if (isFinite(viewLat) && isFinite(viewLon)) {
  focusLatLon(viewLat, viewLon);
  targetRadius = isFinite(viewDist) ? viewDist : 5.15;
  rotX = targetRotX;
  rotY = targetRotY;
  radius = targetRadius;
}
setupIntro();
window.TravelGlobeTest = {
  switchTheme: switchTheme,
  skipIntro: function(){ completeIntro(true); },
  forceView: function(index){
    completeIntro(true);
    var item = ITEMS[index || 0];
    focusLatLon(item.lat, item.lon);
    targetRadius = 4.55;
    rotX = targetRotX;
    rotY = targetRotY;
    radius = targetRadius;
  },
  setView: function(lat, lon, distance){
    completeIntro(true);
    focusLatLon(lat, lon);
    targetRadius = distance || 5.15;
    rotX = targetRotX;
    rotY = targetRotY;
    radius = targetRadius;
  },
  projectPhoto: function(index){
    var group = photoGroups[index || 0];
    camera.updateMatrixWorld();
    scene.updateMatrixWorld(true);
    var p = group.position.clone().project(camera);
    return {
      visible: group.visible,
      x: (p.x * .5 + .5) * window.innerWidth,
      y: (-p.y * .5 + .5) * window.innerHeight
    };
  },
  hitAt: function(x, y){
    camera.updateMatrixWorld();
    scene.updateMatrixWorld(true);
    pointer.x = (x / window.innerWidth) * 2 - 1;
    pointer.y = -(y / window.innerHeight) * 2 + 1;
    ray.setFromCamera(pointer, camera);
    return ray.intersectObjects([].concat(photoGroups, clusterSprites), true).filter(isVisibleHit).slice(0, 4).map(function(hit){
      var obj = hit.object;
      while (obj && !obj.userData.kind) obj = obj.parent;
      return obj ? { kind: obj.userData.kind, place: obj.userData.item ? obj.userData.item.place : obj.userData.place } : { kind: 'unknown' };
    });
  },
  state: function(){
    return { theme: currentTheme, radius: radius, photos: photoGroups.length, clusters: clusterSprites.length, intro: { active: intro.active, done: intro.done, userControlled: userControlled }, showcase: IS_SHOWCASE, tour: { on: TOUR, idx: tour.idx } };
  },
  tourStep: function(){ updateTour(tour.nextAt + 1); return { idx: tour.idx, rotX: targetRotX, rotY: targetRotY, radius: targetRadius }; },
  focus: function(lat, lon, dist){ focusLatLon(lat, lon); if (dist) targetRadius = dist; return { rotX: targetRotX, rotY: targetRotY, radius: targetRadius }; },
  pins: function(){
    return photoGroups.map(function(g){
      var item = g.userData.item, mesh = g.children[0];
      return {
        place: item.place, country: item.country, lat: item.lat, lon: item.lon,
        custom: !!item.custom,
        painted: !!(mesh && mesh.material && mesh.material.map),
        isHome: !!(HOME_PORT && item.place === HOME_PORT.name),
        visible: g.visible
      };
    });
  },
  renderOnce: function(){
    if (intro.active) completeIntro(false);
    rotX = targetRotX; rotY = targetRotY; radius = targetRadius; // 快进易动参数,单帧收敛
    frame(performance.now());
    return true;
  },
  exportProbe: function(){
    if (intro.active) completeIntro(false);
    var o = buildExportCanvas();
    var ctx = o.getContext('2d');
    var d = ctx.getImageData(0, 0, o.width, o.height).data;
    var samples = 0, sum = 0, bright = 0;
    for (var i = 0; i < d.length; i += 160) { var lum = (d[i] + d[i+1] + d[i+2]) / 3; sum += lum; bright += lum > 140 ? 1 : 0; samples++; }
    return { w: o.width, h: o.height, home: HOME_PORT ? HOME_PORT.name : null, cities: ITEMS.length, countries: distinctCountries(), mileage: totalMileage(), avgLum: +(sum/samples).toFixed(1), brightFrac: +(bright/samples).toFixed(3) };
  }
};
requestAnimationFrame(tick);

function haversine(a, b){
  var Re = 6371, toR = Math.PI / 180;
  var dLat = (b.lat - a.lat) * toR, dLon = (b.lon - a.lon) * toR;
  var la1 = a.lat * toR, la2 = b.lat * toR;
  var h = Math.sin(dLat/2)*Math.sin(dLat/2) + Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)*Math.sin(dLon/2);
  return 2 * Re * Math.asin(Math.min(1, Math.sqrt(h)));
}
function totalMileage(){
  var path = (HOME_PORT ? [HOME_PORT] : []).concat(ITEMS);
  var sum = 0;
  for (var i = 1; i < path.length; i++) sum += haversine(path[i-1], path[i]);
  return Math.round(sum);
}
function commaNum(n){ return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
function hex6(c){ return '#' + ('000000' + c.toString(16)).slice(-6); }

// 竖屏分享图(1080×1920):地球 + 旅行身份卡(本命城/城数/国数/里程/水印)
function buildExportCanvas(){
  if (intro.active) completeIntro(false);
  rotX = targetRotX; rotY = targetRotY; radius = targetRadius;
  frame(performance.now());
  var serif = (currentTheme === 'vintage');
  var bgHex = hex6(THEMES[currentTheme].bg);
  var ink = currentTheme === 'night' ? '#dff1ff' : (currentTheme === 'data' ? '#a7f0e6' : '#ecdcae');
  var gold = currentTheme === 'night' ? '#ffe08a' : (currentTheme === 'data' ? '#7ef7d4' : '#d6a957');
  var muted = currentTheme === 'night' ? 'rgba(190,220,245,.72)' : (currentTheme === 'data' ? 'rgba(150,230,222,.72)' : 'rgba(220,200,160,.68)');
  var W = 1080, H = 1920;
  var o = document.createElement('canvas'); o.width = W; o.height = H;
  var ctx = o.getContext('2d');
  ctx.fillStyle = bgHex; ctx.fillRect(0, 0, W, H);
  var gl = document.getElementById('gl');
  var glw = gl.width || 1, glh = gl.height || 1;
  var side = Math.min(glw, glh);
  var sx = (glw - side) / 2, sy = (glh - side) / 2;
  var gTop = 196;
  try { ctx.drawImage(gl, sx, sy, side, side, 0, gTop, W, W); } catch (e) {}
  var fade = ctx.createLinearGradient(0, gTop + W - 360, 0, gTop + W + 40);
  fade.addColorStop(0, 'rgba(0,0,0,0)'); fade.addColorStop(1, bgHex);
  ctx.fillStyle = fade; ctx.fillRect(0, gTop + W - 360, W, 400);
  var topf = ctx.createLinearGradient(0, gTop, 0, gTop + 170);
  topf.addColorStop(0, bgHex); topf.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = topf; ctx.fillRect(0, gTop, W, 170);
  ctx.textAlign = 'center';
  ctx.fillStyle = ink;
  ctx.font = serif ? '700 60px Georgia, serif' : '700 58px "Segoe UI", Arial';
  ctx.fillText(PAGE_TITLE || '我的旅行地球', W/2, 122);
  ctx.fillStyle = gold;
  ctx.font = '600 38px ' + (serif ? 'Georgia, serif' : '"Segoe UI", Arial');
  if (HOME_PORT) ctx.fillText('★ 本命城市 · ' + HOME_PORT.name, W/2, 1502);
  ctx.fillStyle = ink;
  ctx.font = '700 78px ' + (serif ? 'Georgia, serif' : '"Segoe UI", Arial');
  ctx.fillText(ITEMS.length + ' 城 · ' + distinctCountries() + ' 国/地区', W/2, 1612);
  ctx.fillStyle = muted;
  ctx.font = '500 44px "Segoe UI", Arial';
  ctx.fillText('总里程约 ' + commaNum(totalMileage()) + ' km', W/2, 1686);
  ctx.strokeStyle = gold; ctx.globalAlpha = .5; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(W/2 - 90, 1740); ctx.lineTo(W/2 + 90, 1740); ctx.stroke(); ctx.globalAlpha = 1;
  ctx.fillStyle = muted;
  ctx.font = '500 30px "Segoe UI", Arial';
  ctx.fillText('✦ 我的旅行地球', W/2, 1818);
  return o;
}
function exportGlobeImage(){
  var o = buildExportCanvas();
  var url = o.toDataURL('image/png');
  var a = document.createElement('a');
  a.download = (PAGE_TITLE || '我的旅行地球') + '.png';
  a.href = url; document.body.appendChild(a); a.click(); a.remove();
}

function showFallback(){
  var node = document.getElementById('fallback');
  var list = document.getElementById('fallbackList');
  list.innerHTML = ITEMS.map(function(item){
    return '<figure>' + (item.thumb ? ('<img src="' + item.thumb + '" alt="">') : '') + '<figcaption>' + item.place + '</figcaption></figure>';
  }).join('');
  node.classList.add('visible');
}

function resize(){
  renderer.setSize(window.innerWidth, window.innerHeight);
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.fov = window.innerWidth < 600 ? 52 : 42;
  if (window.innerWidth < 600 && radius < 10.2) {
    radius = 10.2;
    targetRadius = Math.max(targetRadius, 10.2);
  }
  camera.updateProjectionMatrix();
}

function setupIntro(){
  if (!introRequested) {
    completeIntro(true);
    return;
  }
  intro.active = true;
  intro.done = false;
  intro.start = 0;
  intro.startRotX = Math.max(-.32, targetRotX - .10);
  intro.startRotY = targetRotY - 1.36;
  intro.startRadius = Math.max(11.35, targetRadius + 4.35);
  rotX = targetRotX = intro.startRotX;
  rotY = targetRotY = intro.startRotY;
  radius = targetRadius = intro.startRadius;
  var cursor = 0;
  photoGroups.forEach(function(group, i){
    if (i) cursor += 115 + (i % 5) * 14;
    group.userData.flyStartMs = intro.photoLead + cursor;
    group.userData.flyDuration = intro.photoDuration;
    group.userData.flyStartPosition = makePhotoFlyStart(group, i);
    group.userData.introProgress = 0;
    group.userData.introScale = 0;
    group.position.copy(group.userData.flyStartPosition);
    group.visible = false;
    if (group.userData.trail) group.userData.trail.visible = false;
    if (group.userData.anchorLine) group.userData.anchorLine.visible = false;
    if (group.userData.anchorBeam) group.userData.anchorBeam.visible = false;
  });
  intro.total = intro.photoLead + cursor + intro.photoDuration + intro.settle;
  clusterSprites.forEach(function(spr){ spr.visible = false; });
  anchorLines.forEach(function(line){
    line.visible = false;
    line.material.opacity = 0;
  });
  setStatus(IS_USER ? '开场' : 'Cinematic intro', IS_USER ? '穿越星海' : 'Deep-space push-in');
}

function takeControl(){
  userControlled = true;
  if (intro.active) completeIntro(false);
}

function completeIntro(jumpCamera){
  intro.active = false;
  intro.done = true;
  photoGroups.forEach(function(group){
    if (group.userData.finalPosition) group.position.copy(group.userData.finalPosition);
    group.userData.introProgress = 1;
    group.userData.introScale = 1;
    if (group.userData.trail) group.userData.trail.visible = false;
    group.visible = true;
  });
  anchorLines.forEach(function(line){
    line.visible = currentTheme === 'vintage' || currentTheme === 'night';
    line.material.opacity = currentTheme === 'night' ? .58 : (line.userData.baseOpacity || .42);
  });
  anchorBeams.forEach(function(beam){
    beam.visible = currentTheme === 'night';
    beam.material.opacity = beam.userData.baseOpacity || .48;
  });
  if (jumpCamera) {
    radius = targetRadius;
    rotX = targetRotX;
    rotY = targetRotY;
  }
  applyClusterVisibility();
  if (typeof showHint === 'function') showHint();
}

function updateIntro(now){
  if (!intro.start) intro.start = now || performance.now();
  var elapsed = (now || performance.now()) - intro.start;
  var zoomP = smoothstep(clamp01(elapsed / 1550));
  var spinP = smoothstep(clamp01((elapsed - 420) / 2440));
  radius = targetRadius = lerp(intro.startRadius, 8.4, zoomP);
  rotX = targetRotX = lerp(intro.startRotX, .18, zoomP);
  rotY = targetRotY = intro.startRotY + .42 * zoomP + 2.05 * spinP + Math.sin(spinP * Math.PI) * .26;
  if (elapsed > 760 && elapsed < intro.photoLead) setStatus(IS_USER ? '开场' : 'Cinematic intro', IS_USER ? '地球加速旋转' : 'Accelerated globe spin');
  if (elapsed >= intro.photoLead) setStatus(IS_USER ? '开场' : 'Cinematic intro', IS_USER ? '城市归位' : 'Photos flying home');
  updateIntroPhotos(elapsed);
  if (elapsed >= intro.total) {
    targetRotX = rotX;
    targetRotY = rotY;
    targetRadius = radius;
    completeIntro(false);
    setStatus(IS_USER ? '轻转地球' : 'Idle orbit', IS_USER ? (ITEMS.length + ' 城 · ' + distinctCountries() + ' 国/地区') : (ITEMS.length + ' photos ready'));
  }
}

function updateIntroPhotos(elapsed){
  photoGroups.forEach(function(group){
    var start = group.userData.flyStartMs || 0;
    var duration = group.userData.flyDuration || intro.photoDuration;
    var raw = (elapsed - start) / duration;
    if (raw <= 0) {
      group.visible = false;
      if (group.userData.trail) group.userData.trail.visible = false;
      return;
    }
    var p = clamp01(raw);
    var eased = smoothstep(p);
    group.visible = true;
    group.userData.introProgress = eased;
    group.userData.introScale = Math.max(.12, .28 + eased * .72);
    group.position.copy(photoFlyPosition(group, eased));
    updatePhotoTrail(group, p);
    var anchor = group.userData.anchorLine;
    if (anchor) {
      anchor.visible = p > .82 && (currentTheme === 'vintage' || currentTheme === 'night');
      var anchorFade = clamp01((p - .82) / .18);
      anchor.material.opacity = (currentTheme === 'night' ? .58 : (anchor.userData.baseOpacity || .42)) * anchorFade;
    }
    var beam = group.userData.anchorBeam;
    if (beam) {
      beam.visible = p > .82 && currentTheme === 'night';
      beam.material.opacity = (beam.userData.baseOpacity || .48) * clamp01((p - .82) / .18);
    }
  });
}

function makePhotoFlyStart(group, index){
  var endDir = group.userData.finalPosition.clone().normalize();
  var tangent = new THREE.Vector3(-endDir.z, .18 + (index % 3) * .05, endDir.x).normalize();
  var cross = new THREE.Vector3().crossVectors(endDir, tangent).normalize();
  var side = index % 2 ? 1 : -1;
  return endDir.clone().multiplyScalar(R + 3.05 + (index % 4) * .10)
    .add(tangent.multiplyScalar(side * (1.05 + (index % 5) * .09)))
    .add(cross.multiplyScalar(.38 + (index % 4) * .07));
}

function photoFlyPosition(group, p){
  var start = group.userData.flyStartPosition || group.position;
  var end = group.userData.finalPosition;
  var pos = new THREE.Vector3().lerpVectors(start, end, p);
  var dir = pos.clone().normalize();
  var lift = Math.sin(p * Math.PI) * (.34 + (group.userData.index % 4) * .045);
  return dir.multiplyScalar(pos.length() + lift);
}

function updatePhotoTrail(group, p){
  var trail = group.userData.trail;
  if (!trail) return;
  if (p >= 1) {
    trail.visible = false;
    return;
  }
  trail.visible = true;
  trail.material.opacity = .12 + (1 - p) * .34;
  var attr = trail.geometry.attributes.position;
  for (var i=0; i<6; i++) {
    var tp = clamp01(p - i * .045);
    var point = photoFlyPosition(group, smoothstep(tp));
    attr.setXYZ(i, point.x, point.y, point.z);
  }
  attr.needsUpdate = true;
  trail.geometry.computeBoundingSphere();
}

function clamp01(v){ return Math.max(0, Math.min(1, v)); }
function smoothstep(v){ v = clamp01(v); return v * v * (3 - 2 * v); }
function lerp(a, b, t){ return a + (b - a) * t; }

function onPointerDown(e){
  var wasIntro = intro.active;
  takeControl();
  isDragging = true;
  dragMoved = wasIntro;
  lastX = e.clientX;
  lastY = e.clientY;
  dragVec = pointerToTrackball(e.clientX, e.clientY);
  cv.setPointerCapture && cv.setPointerCapture(e.pointerId);
}

function onPointerMove(e){
  if (!isDragging) return;
  e.preventDefault();
  var dx = e.clientX - lastX;
  var dy = e.clientY - lastY;
  if (Math.abs(dx) + Math.abs(dy) > 3) dragMoved = true;
  lastX = e.clientX;
  lastY = e.clientY;
  var nextVec = pointerToTrackball(e.clientX, e.clientY);
  if (dragVec && nextVec) {
    var q = new THREE.Quaternion().setFromUnitVectors(dragVec, nextVec).invert();
    var eye = new THREE.Vector3(
      Math.cos(targetRotX) * Math.sin(targetRotY),
      Math.sin(targetRotX),
      Math.cos(targetRotX) * Math.cos(targetRotY)
    );
    eye.applyQuaternion(q).normalize();
    targetRotX = Math.max(-1.24, Math.min(1.24, Math.asin(eye.y)));
    targetRotY = Math.atan2(eye.x, eye.z);
    dragVec = nextVec;
  }
}

function onPointerUp(){ isDragging = false; dragVec = null; }

function pointerToTrackball(x, y){
  var nx = (x / window.innerWidth) * 2 - 1;
  var ny = 1 - (y / window.innerHeight) * 2;
  var d = nx * nx + ny * ny;
  var z = d > 1 ? 0 : Math.sqrt(1 - d);
  return new THREE.Vector3(nx, ny, z).normalize();
}

function onWheel(e){
  e.preventDefault();
  takeControl();
  targetRadius += e.deltaY * .0024;
  targetRadius = Math.max(3.6, Math.min(10.8, targetRadius));
}

function onClick(e){
  if (dragMoved) return;
  dragMoved = false;
  camera.updateMatrixWorld();
  scene.updateMatrixWorld(true);
  pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
  pointer.y = -(e.clientY / window.innerHeight) * 2 + 1;
  ray.setFromCamera(pointer, camera);
  var hits = ray.intersectObjects([].concat(photoGroups, clusterSprites), true).filter(isVisibleHit);
  if (!hits.length) return;
  var obj = hits[0].object;
  while (obj && !obj.userData.kind) obj = obj.parent;
  if (!obj) return;
  if (obj.userData.kind === 'cluster') {
    focusLatLon(obj.userData.lat, obj.userData.lon);
    targetRadius = 4.65;
    setStatus(obj.userData.place, obj.userData.count + ' photos');
    return;
  }
  if (obj.userData.kind === 'photo') openLightbox(obj.userData.item);
}

function isVisibleHit(hit){
  var obj = hit.object;
  while (obj) {
    if (obj.visible === false) return false;
    obj = obj.parent;
  }
  return true;
}

function openLightbox(item){
  if (!item.full) return; // 无照片的城市钉:暂不开大图(后续刀做城市卡)
  document.getElementById('lightboxImg').src = item.full;
  document.getElementById('lightboxImg').alt = item.place + (item.country ? ' · ' + item.country : '');
  document.getElementById('lightboxCap').textContent = item.place + (item.country ? ' · ' + item.country : '');
  var lb = document.getElementById('lightbox');
  var fig = lb.querySelector('figure');
  // 空间连续性:从照片在屏幕上的位置放大铺开
  if (fig && !reduced) {
    var g = null;
    for (var i = 0; i < photoGroups.length; i++) { if (photoGroups[i].userData.item === item) { g = photoGroups[i]; break; } }
    var ox = 0, oy = 0;
    if (g) {
      camera.updateMatrixWorld();
      var p = g.position.clone().project(camera);
      ox = (p.x * .5 + .5) * window.innerWidth - window.innerWidth / 2;
      oy = (-p.y * .5 + .5) * window.innerHeight - window.innerHeight / 2;
    }
    lightboxOrigin.x = ox; lightboxOrigin.y = oy;
    lb.classList.add('open');
    fig.style.transition = 'none';
    fig.style.transform = 'translate(' + ox + 'px,' + oy + 'px) scale(.16)';
    fig.style.opacity = '0';
    requestAnimationFrame(function(){ requestAnimationFrame(function(){
      fig.style.transition = '';
      fig.style.transform = '';
      fig.style.opacity = '1';
    }); });
  } else {
    lb.classList.add('open');
  }
  lastFocusBeforeLightbox = document.activeElement;
  var cb = document.getElementById('lightboxClose'); if (cb && cb.focus) cb.focus();
  setStatus(item.place, item.country || item.file);
}

function setStatus(title, sub){
  document.getElementById('statusTitle').textContent = title;
  document.getElementById('statusSub').textContent = sub;
}

function focusLatLon(lat, lon){
  var phi = lat * Math.PI / 180;
  var theta = lon * Math.PI / 180;
  targetRotX = Math.max(-1.18, Math.min(1.18, phi));
  targetRotY = Math.PI * .5 + theta;
}

// 录屏运镜模式(?tour=1):沿城市航点自动巡游,±交替推拉镜头;?switch=1 每半圈做一次主题溶解。
// ?dwell=毫秒 调每城停留(默认 4200;短视频建议 2200-2800)。用户任何拖拽/点击(takeControl)即接管,巡航停止。
var tour = { idx: -1, nextAt: 0, DWELL: (function(){
  try { var d = parseInt(new URLSearchParams(window.location.search).get('dwell'), 10); if (d >= 800 && d <= 20000) return d; } catch(e){}
  return 4200;
})() };
function updateTour(now){
  if (!ITEMS.length) return;
  if (now < tour.nextAt) return;
  tour.nextAt = now + tour.DWELL;
  tour.idx++;
  var i = tour.idx % ITEMS.length;
  var half = Math.max(1, Math.ceil(ITEMS.length / 2));
  if (TOUR_SWITCH && tour.idx > 0 && tour.idx % half === 0) {
    var next = currentTheme === 'vintage' ? 'night' : 'vintage';
    transitionTheme(next);
  }
  var it = ITEMS[i];
  focusLatLon(it.lat, it.lon);
  // 竖屏(9:16)下地球要更远才装得下,推拉半径按屏幕取向自适应
  var portrait = window.innerHeight > window.innerWidth;
  targetRadius = (tour.idx % 2 === 0) ? (portrait ? 10.6 : 7.4) : (portrait ? 12.2 : 8.8);
}

function latLonToVec(lat, lon, rr){
  var p = lat * Math.PI / 180;
  var l = lon * Math.PI / 180;
  return new THREE.Vector3(
    rr * Math.cos(p) * Math.cos(l),
    rr * Math.sin(p),
    -rr * Math.cos(p) * Math.sin(l)
  );
}

// subsolar point from the real current UTC time -> unit vector earth-center -> sun
function computeSunDir(){
  var d = new Date();
  var h = d.getUTCHours() + d.getUTCMinutes() / 60 + d.getUTCSeconds() / 3600;
  var lonSun = -15 * (h - 12);                       // east-positive longitude under the sun
  var start = Date.UTC(d.getUTCFullYear(), 0, 0);
  var dayOfYear = Math.floor((d - start) / 86400000);
  var decl = 23.44 * Math.sin(2 * Math.PI * (dayOfYear - 81) / 365); // solar declination
  return latLonToVec(decl, lonSun, 1).normalize();
}
var sunDir = computeSunDir();
var lastSunUpdate = -1e9;

function makeVintageMapTexture(){
  var c = document.createElement('canvas');
  c.width = 2048; c.height = 1024;
  var ctx = c.getContext('2d');
  ctx.fillStyle = '#f0e6ce';
  ctx.fillRect(0,0,c.width,c.height);
  var img = ctx.getImageData(0,0,c.width,c.height);
  for (var i=0; i<img.data.length; i+=4) {
    var x = (i/4) % c.width, y = Math.floor((i/4) / c.width);
    var n = Math.sin(x*12.9898 + y*78.233) * 43758.5453;
    var grain = (n - Math.floor(n)) * 22 - 10;
    img.data[i] = Math.max(0, Math.min(255, img.data[i] + grain));
    img.data[i+1] = Math.max(0, Math.min(255, img.data[i+1] + grain * .82));
    img.data[i+2] = Math.max(0, Math.min(255, img.data[i+2] + grain * .55));
  }
  ctx.putImageData(img,0,0);
  ctx.strokeStyle = 'rgba(107,64,38,.25)';
  ctx.lineWidth = 1;
  for (var lon=-180; lon<=180; lon+=15) {
    var x1 = mapX(lon,c.width);
    ctx.beginPath(); ctx.moveTo(x1,0); ctx.lineTo(x1,c.height); ctx.stroke();
  }
  for (var lat=-75; lat<=75; lat+=15) {
    var y1 = mapY(lat,c.height);
    ctx.beginPath(); ctx.moveTo(0,y1); ctx.lineTo(c.width,y1); ctx.stroke();
  }
  WORLD_POLYS.forEach(function(poly){
    ctx.beginPath();
    poly.forEach(function(p,i){
      var x = mapX(p[0], c.width), y = mapY(p[1], c.height);
      if (i) ctx.lineTo(x,y); else ctx.moveTo(x,y);
    });
    ctx.closePath();
    ctx.fillStyle = 'rgba(176,123,70,.26)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(88,52,31,.82)';
    ctx.lineWidth = 4;
    ctx.stroke();
    ctx.strokeStyle = 'rgba(255,248,219,.32)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
  });
  for (var k=0; k<90; k++) {
    var sx = Math.random() * c.width, sy = Math.random() * c.height, r = 6 + Math.random() * 36;
    ctx.beginPath();
    ctx.arc(sx, sy, r, 0, Math.PI*2);
    ctx.fillStyle = 'rgba(95,52,31,' + (.018 + Math.random()*.035) + ')';
    ctx.fill();
  }
  return c;
}

function mapX(lon,w){ return (lon + 180) / 360 * w; }
function mapY(lat,h){ return (90 - lat) / 180 * h; }

function buildGraticule(){
  var centers = [[-28,36],[12,36],[42,31],[-76,22],[112,2]];
  centers.forEach(function(center, ci){
    for (var i=0; i<32; i++) {
      var color = i % 3 === 0 ? 0xa62f20 : (i % 3 === 1 ? 0x208454 : 0x5c4023);
      var mat = new THREE.LineBasicMaterial({ color: color, transparent:true, opacity: ci < 3 ? .27 : .18 });
      graticuleGroup.add(makeRhumbLine(center[0], center[1], i * 11.25, mat));
    }
  });
}

function makeRhumbLine(lon0, lat0, angleDeg, mat){
  var angle = angleDeg * Math.PI / 180;
  var dx = Math.sin(angle);
  var dy = Math.cos(angle) * .56;
  var latMin = -72, latMax = 72;
  var candidates = [];
  if (Math.abs(dx) > .0001) candidates.push((-180 - lon0) / dx, (180 - lon0) / dx);
  if (Math.abs(dy) > .0001) candidates.push((latMin - lat0) / dy, (latMax - lat0) / dy);
  var valid = candidates.filter(function(t){
    var lon = lon0 + dx * t, lat = lat0 + dy * t;
    return lon >= -180 && lon <= 180 && lat >= latMin && lat <= latMax;
  });
  var t0 = Math.min.apply(null, valid), t1 = Math.max.apply(null, valid);
  var pts = [];
  for (var s=0; s<=42; s++) {
    var t = t0 + (t1 - t0) * s / 42;
    pts.push(latLonToVec(lat0 + dy * t, lon0 + dx * t, R + .019));
  }
  return new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat);
}

function buildCoastlines(){
  var mat = new THREE.LineBasicMaterial({ color: 0x5c4023, transparent:true, opacity:.52 });
  COAST_LINES.forEach(function(line){
    var pts = [];
    var previous = null;
    line.forEach(function(p){
      if (previous && Math.abs(p[0] - previous[0]) > 120) {
        if (pts.length > 3) coastlineGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
        pts = [];
      }
      pts.push(latLonToVec(p[1], p[0], R + .024));
      previous = p;
    });
    if (pts.length > 3) coastlineGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
  });
}

function buildDecor(){
  decorGroup.add(makeCompassRoseSprite(-20, 8, .56));
  decorGroup.add(makeSeaSprite(-10, -18, 'kraken', .48));
  decorGroup.add(makeSeaSprite(155, 2, 'serpent', .50));
  if (HOME_PORT) {
    // 把母港标记挪到城市外海一点,避免被密集照片簇盖住;航线仍从城市本体起航
    var dlon = (HOME_PORT.lon || 0) + (HOME_PORT.dlon != null ? HOME_PORT.dlon : 3.2);
    var dlat = (HOME_PORT.lat || 0) + (HOME_PORT.dlat != null ? HOME_PORT.dlat : -1.6);
    decorGroup.add(makeHomeStain(dlon, dlat));
    decorGroup.add(makeHomePortSprite(dlon, dlat, HOME_PORT.name));
  }
}

// 母港摩挲痕:一片半透明深色,叠在海图上让这块颜色加深
function makeHomeStain(lon, lat){
  var c = document.createElement('canvas'); c.width = c.height = 256;
  var g = c.getContext('2d');
  var grd = g.createRadialGradient(128, 128, 10, 128, 128, 128);
  grd.addColorStop(0, 'rgba(48,28,14,.62)');
  grd.addColorStop(.55, 'rgba(60,36,18,.34)');
  grd.addColorStop(1, 'rgba(70,44,22,0)');
  g.fillStyle = grd; g.beginPath(); g.arc(128, 128, 128, 0, Math.PI * 2); g.fill();
  var t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  var spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, opacity: .9, depthWrite: false }));
  spr.position.copy(latLonToVec(lat, lon, R + .03));
  spr.scale.set(1.15, 1.15, 1.15);
  return spr;
}

// 母港标记:金墨锚 + 港名小旗
function makeHomePortSprite(lon, lat, name){
  var c = document.createElement('canvas'); c.width = c.height = 256;
  var g = c.getContext('2d');
  g.translate(128, 116);
  g.strokeStyle = 'rgba(196,150,72,.96)'; g.fillStyle = 'rgba(196,150,72,.96)';
  g.lineWidth = 7; g.lineCap = 'round'; g.lineJoin = 'round';
  // anchor (锚)
  g.beginPath(); g.arc(0, -46, 11, 0, Math.PI * 2); g.stroke();          // ring
  g.beginPath(); g.moveTo(0, -35); g.lineTo(0, 44); g.stroke();          // shank
  g.beginPath(); g.moveTo(-26, 6); g.lineTo(26, 6); g.stroke();          // stock
  g.beginPath();                                                          // arms
  g.moveTo(-38, 30); g.quadraticCurveTo(-30, 56, 0, 56);
  g.quadraticCurveTo(30, 56, 38, 30); g.stroke();
  g.beginPath(); g.moveTo(-38, 30); g.lineTo(-46, 18); g.moveTo(38, 30); g.lineTo(46, 18); g.stroke();
  // name banner (港名小旗)
  g.font = '700 30px Georgia, serif'; g.textAlign = 'center';
  var tw = g.measureText(name).width;
  g.fillStyle = 'rgba(30,18,9,.78)';
  g.fillRect(-tw / 2 - 16, 70, tw + 32, 40);
  g.strokeStyle = 'rgba(196,150,72,.9)'; g.lineWidth = 2;
  g.strokeRect(-tw / 2 - 16, 70, tw + 32, 40);
  g.fillStyle = 'rgba(238,214,160,.98)';
  g.fillText(name, 0, 99);
  g.font = 'italic 16px Georgia, serif'; g.fillStyle = 'rgba(196,150,72,.9)';
  g.fillText('母 港', 0, -78);
  var t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  var spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, opacity: .95, depthWrite: false }));
  spr.position.copy(latLonToVec(lat, lon, R + .05));
  spr.scale.set(.62, .62, .62);
  return spr;
}

function makeCompassRoseSprite(lon, lat, scale){
  var c = document.createElement('canvas');
  c.width = 512; c.height = 512;
  var ctx = c.getContext('2d');
  ctx.translate(256,256);
  ctx.strokeStyle = 'rgba(92,64,35,.86)';
  ctx.fillStyle = 'rgba(138,44,32,.64)';
  ctx.lineWidth = 4;
  for (var i=0; i<32; i++) {
    var a = i * Math.PI / 16;
    var outer = i % 2 === 0 ? 214 : 158;
    var inner = i % 2 === 0 ? 42 : 68;
    ctx.beginPath();
    ctx.moveTo(Math.sin(a - .045) * inner, -Math.cos(a - .045) * inner);
    ctx.lineTo(Math.sin(a) * outer, -Math.cos(a) * outer);
    ctx.lineTo(Math.sin(a + .045) * inner, -Math.cos(a + .045) * inner);
    ctx.closePath();
    ctx.fillStyle = i % 4 === 0 ? 'rgba(138,44,32,.70)' : 'rgba(40,112,82,.50)';
    ctx.fill();
    ctx.stroke();
  }
  ctx.beginPath(); ctx.arc(0,0,218,0,Math.PI*2); ctx.stroke();
  ctx.beginPath(); ctx.arc(0,0,86,0,Math.PI*2); ctx.stroke();
  ctx.fillStyle = 'rgba(60,33,22,.86)';
  ctx.font = '700 46px Georgia, serif';
  ctx.textAlign = 'center';
  ctx.fillText('N', 0, -128);
  var t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  var spr = new THREE.Sprite(new THREE.SpriteMaterial({ map:t, transparent:true, opacity:.82, depthWrite:false }));
  spr.position.copy(latLonToVec(lat, lon, R + .045));
  var s = scale || .72;
  spr.scale.set(s,s,s);
  return spr;
}

function makeSeaSprite(lon, lat, type, scale){
  var c = document.createElement('canvas');
  c.width = 256; c.height = 256;
  var ctx = c.getContext('2d');
  ctx.strokeStyle = 'rgba(101,49,31,.82)';
  ctx.fillStyle = 'rgba(101,49,31,.18)';
  ctx.lineWidth = 7;
  ctx.lineCap = 'round';
  if (type === 'kraken') {
    ctx.beginPath(); ctx.arc(128,102,42,0,Math.PI*2); ctx.fill(); ctx.stroke();
    for (var i=0;i<7;i++) {
      var a = -2.8 + i*.9;
      ctx.beginPath(); ctx.moveTo(128,136); ctx.bezierCurveTo(128+Math.cos(a)*55,150+Math.sin(a)*22,128+Math.cos(a)*72,192,128+Math.cos(a)*96,218); ctx.stroke();
    }
    for (var h=0; h<8; h++) {
      ctx.beginPath(); ctx.moveTo(92+h*10,76); ctx.lineTo(72+h*13,116); ctx.stroke();
    }
  } else {
    ctx.beginPath(); ctx.moveTo(42,145); ctx.bezierCurveTo(84,62,140,218,210,102); ctx.stroke();
    ctx.beginPath(); ctx.arc(205,94,18,0,Math.PI*2); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(190,74); ctx.lineTo(222,48); ctx.lineTo(216,88); ctx.stroke();
  }
  var t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  var spr = new THREE.Sprite(new THREE.SpriteMaterial({ map:t, transparent:true, opacity:.88, depthWrite:false }));
  spr.position.copy(latLonToVec(lat, lon, R + .05));
  var s = scale || .46;
  spr.scale.set(s,s,s);
  return spr;
}

function buildDataDots(){
  var positions = new Float32Array(DATA_DOTS.length * 3);
  var colors = new Float32Array(DATA_DOTS.length * 3);
  var c1 = new THREE.Color(0x38d9ff);
  var c2 = new THREE.Color(0x7ef7d4);
  var c3 = new THREE.Color(0x9b7cff);
  DATA_DOTS.forEach(function(dot, i){
    var p = latLonToVec(dot[1], dot[0], R + .026 + dot[2] * .45);
    positions[i*3] = p.x;
    positions[i*3+1] = p.y;
    positions[i*3+2] = p.z;
    var mix = dot[4] ? c3 : c1.clone().lerp(c2, Math.max(0, Math.min(1, (dot[3] - .58) / .34)));
    colors[i*3] = mix.r;
    colors[i*3+1] = mix.g;
    colors[i*3+2] = mix.b;
  });
  var geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  var mat = new THREE.PointsMaterial({
    size:.021,
    vertexColors:true,
    transparent:true,
    opacity:.88,
    depthWrite:false,
    blending:THREE.AdditiveBlending
  });
  dataDots.add(new THREE.Points(geo, mat));
}

function buildAurora(){
  auroraGroup.add(makeAuroraRibbon(0.0, 70.5, -168, 315, 2.9, 0x56ffba, .34));
  auroraGroup.add(makeAuroraRibbon(1.8, 73.6, -118, 260, 2.2, 0x63dfff, .28));
  auroraGroup.add(makeAuroraRibbon(3.4, 67.4, -42, 210, 1.8, 0xb08cff, .18));
  auroraGroup.visible = false;
}

function makeAuroraRibbon(seed, baseLat, lonStart, lonSpan, width, color, opacity){
  var segments = 96;
  var positions = [];
  var indices = [];
  for (var i=0; i<=segments; i++) {
    var t = i / segments;
    var lon = lonStart + lonSpan * t;
    var wave = Math.sin(t * Math.PI * 5.2 + seed) * 2.5 + Math.sin(t * Math.PI * 11.0 + seed * .7) * .85;
    var center = baseLat + wave;
    var lift = .21 + Math.sin(t * Math.PI * 3.0 + seed) * .035;
    var a = latLonToVec(center - width, lon, R + lift);
    var b = latLonToVec(center + width * .65, lon + Math.sin(t * Math.PI * 2.0 + seed) * 1.8, R + lift + .045);
    positions.push(a.x, a.y, a.z, b.x, b.y, b.z);
    if (i < segments) {
      var k = i * 2;
      indices.push(k, k + 1, k + 2, k + 1, k + 3, k + 2);
    }
  }
  var geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setIndex(indices);
  geo.computeVertexNormals();
  var mat = new THREE.MeshBasicMaterial({
    color: color,
    transparent: true,
    opacity: opacity,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  var mesh = new THREE.Mesh(geo, mat);
  mesh.frustumCulled = false;
  mesh.userData.baseOpacity = opacity;
  mesh.userData.seed = seed;
  return mesh;
}

function isLandApprox(lon, lat){
  for (var i=0;i<WORLD_POLYS.length;i++) if (pointInPoly([lon,lat], WORLD_POLYS[i])) return true;
  return false;
}

function pointInPoly(p, poly){
  var x=p[0], y=p[1], inside=false;
  for (var i=0,j=poly.length-1; i<poly.length; j=i++) {
    var xi=poly[i][0], yi=poly[i][1], xj=poly[j][0], yj=poly[j][1];
    var hit=((yi>y)!=(yj>y)) && (x < (xj-xi)*(y-yi)/(yj-yi)+xi);
    if (hit) inside=!inside;
  }
  return inside;
}

function buildRoutes(){
  var pts = [];
  var dataPts = [];
  var dataColors = [];
  var pulsePts = [];
  var pulseColors = [];
  var startColor = new THREE.Color(0x36d9ff);
  var midColor = new THREE.Color(0x7ef7d4);
  var endColor = new THREE.Color(0x9b7cff);
  // 航线从母港起航,再串起各张照片
  var nodes = HOME_PORT ? [HOME_PORT].concat(ITEMS) : ITEMS;
  for (var i=0; i<nodes.length-1; i++) {
    var a = latLonToVec(nodes[i].lat, nodes[i].lon, 1).normalize();
    var b = latLonToVec(nodes[i+1].lat, nodes[i+1].lon, 1).normalize();
    for (var s=0; s<=34; s++) {
      var t = s / 34;
      var curve = new THREE.Vector3().lerpVectors(a,b,t).normalize().multiplyScalar(R + .06 + Math.sin(t*Math.PI)*.16);
      pts.push(curve.clone());
      dataPts.push(curve.clone().multiplyScalar(1.006));
      var color = t < .5 ? startColor.clone().lerp(midColor, t * 2) : midColor.clone().lerp(endColor, (t - .5) * 2);
      dataColors.push(color.r, color.g, color.b);
      if (s % 5 === 0) {
        pulsePts.push(curve.clone().multiplyScalar(1.01));
        pulseColors.push(color.r, color.g, color.b);
      }
    }
  }
  var geo = new THREE.BufferGeometry().setFromPoints(pts);
  var mat = new THREE.LineBasicMaterial({ color:0x8f3f28, transparent:true, opacity:.48 });
  routeLine = new THREE.Line(geo, mat);
  scene.add(routeLine);

  var dataGeo = new THREE.BufferGeometry().setFromPoints(dataPts);
  dataGeo.setAttribute('color', new THREE.Float32BufferAttribute(dataColors, 3));
  dataRouteLine = new THREE.Line(dataGeo, new THREE.LineBasicMaterial({
    vertexColors:true,
    transparent:true,
    opacity:.82,
    blending:THREE.AdditiveBlending,
    depthWrite:false
  }));
  scene.add(dataRouteLine);

  var pulseGeo = new THREE.BufferGeometry().setFromPoints(pulsePts);
  pulseGeo.setAttribute('color', new THREE.Float32BufferAttribute(pulseColors, 3));
  dataRoutePoints = new THREE.Points(pulseGeo, new THREE.PointsMaterial({
    size:.012,
    vertexColors:true,
    transparent:true,
    opacity:.22,
    blending:THREE.AdditiveBlending,
    depthWrite:false
  }));
  scene.add(dataRoutePoints);

  routeCurvePts = pts;
  buildVoyageShip();
}

function buildVoyageShip(){
  if (!routeCurvePts || routeCurvePts.length < 2) return;
  var cv = document.createElement('canvas'); cv.width = 128; cv.height = 128;
  var g = cv.getContext('2d');
  g.translate(64, 70);
  g.strokeStyle = 'rgba(228,196,128,.95)';
  g.fillStyle = 'rgba(228,196,128,.92)';
  g.lineWidth = 4; g.lineJoin = 'round'; g.lineCap = 'round';
  // hull (船身)
  g.beginPath();
  g.moveTo(-30, 8); g.quadraticCurveTo(0, 34, 30, 8);
  g.lineTo(22, 16); g.quadraticCurveTo(0, 26, -22, 16); g.closePath();
  g.fill();
  // mast (桅杆)
  g.beginPath(); g.moveTo(0, 6); g.lineTo(0, -46); g.stroke();
  // sails (帆) — two billowing triangles
  g.beginPath();
  g.moveTo(2, -42); g.quadraticCurveTo(26, -30, 6, -8); g.lineTo(2, -8); g.closePath();
  g.moveTo(-2, -34); g.quadraticCurveTo(-22, -24, -6, -6); g.lineTo(-2, -6); g.closePath();
  g.fillStyle = 'rgba(244,228,188,.9)'; g.fill();
  g.strokeStyle = 'rgba(228,196,128,.95)'; g.lineWidth = 2.4; g.stroke();
  // pennant (旗)
  g.beginPath(); g.moveTo(0, -46); g.lineTo(16, -42); g.lineTo(0, -38); g.closePath();
  g.fillStyle = 'rgba(220,140,90,.95)'; g.fill();
  var tex = new THREE.CanvasTexture(cv);
  tex.anisotropy = 4;
  voyageShip = new THREE.Sprite(new THREE.SpriteMaterial({
    map: tex, transparent: true, opacity: .92, depthWrite: false,
    depthTest: false
  }));
  voyageShip.scale.set(.42, .42, .42);
  voyageShip.renderOrder = 6;
  voyageShip.visible = false;
  scene.add(voyageShip);
}

function buildPins(){
  ITEMS.forEach(function(item, index){
    var group = new THREE.Group();
    group.userData.kind = 'photo';
    group.userData.item = item;
    group.userData.index = index;
    group.userData.clusterKey = clusterKey(item);
    group.userData.finalPosition = latLonToVec(item.lat, item.lon, R + .24);
    group.position.copy(group.userData.finalPosition);
    var mat = new THREE.MeshBasicMaterial({ transparent:true, side:THREE.DoubleSide, opacity:0 });
    var mesh = new THREE.Mesh(new THREE.PlaneGeometry(.58, .72), mat);
    mesh.userData.kind = 'photo';
    mesh.userData.item = item;
    group.add(mesh);
    var anchor = makeAnchorLine(item);
    anchor.userData.baseOpacity = .42;
    group.userData.anchorLine = anchor;
    scene.add(anchor);
    anchorLines.push(anchor);
    var beam = makeAnchorBeam(item);
    group.userData.anchorBeam = beam;
    scene.add(beam);
    anchorBeams.push(beam);
    var trail = makePhotoTrail(index);
    group.userData.trail = trail;
    scene.add(trail);
    scene.add(group);
    photoGroups.push(group);
    updatePhotoTexture(group);
  });
}

function makeAnchorLine(item){
  var pts = [
    latLonToVec(item.lat, item.lon, R + .035),
    latLonToVec(item.lat, item.lon, R + .235)
  ];
  var mat = new THREE.LineBasicMaterial({ color:0x5c4023, transparent:true, opacity:.42, depthWrite:false });
  var line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat);
  line.frustumCulled = false;
  return line;
}

function makeAnchorBeam(item){
  var start = latLonToVec(item.lat, item.lon, R + .030);
  var end = latLonToVec(item.lat, item.lon, R + .255);
  var dir = new THREE.Vector3().subVectors(end, start);
  var len = dir.length();
  var geo = new THREE.CylinderGeometry(.010, .024, len, 18, 1, true);
  var mat = new THREE.MeshBasicMaterial({
    color: 0x79e6ff,
    transparent: true,
    opacity: 0,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  var beam = new THREE.Mesh(geo, mat);
  beam.position.copy(start).add(end).multiplyScalar(.5);
  beam.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
  beam.visible = false;
  beam.frustumCulled = false;
  beam.userData.baseOpacity = .48;
  return beam;
}

function makePhotoTrail(index){
  var geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(18), 3));
  var mat = new THREE.LineBasicMaterial({
    color: THEMES[currentTheme].glow,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  var line = new THREE.Line(geo, mat);
  line.visible = false;
  line.frustumCulled = false;
  line.userData.index = index;
  return line;
}

function fmtCoord(lat, lon){
  var a = (lat >= 0 ? 'N' : 'S') + Math.abs(lat).toFixed(1) + '°';
  var b = (lon >= 0 ? 'E' : 'W') + Math.abs(lon).toFixed(1) + '°';
  return a + '   ' + b;
}

// 无照片城市的徽记:复古=罗盘星 / 夜景=辉光点 / 数据=坐标十字
function drawEmblem(ctx, x, y){
  var dataMode = currentTheme === 'data', nightMode = currentTheme === 'night';
  ctx.save();
  ctx.translate(x, y);
  if (nightMode) {
    var g = ctx.createRadialGradient(0, 0, 2, 0, 0, 70);
    g.addColorStop(0, 'rgba(150,228,255,.95)');
    g.addColorStop(.42, 'rgba(104,216,255,.5)');
    g.addColorStop(1, 'rgba(104,216,255,0)');
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(0, 0, 70, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#e6f6ff';
    ctx.beginPath(); ctx.arc(0, 0, 7, 0, Math.PI * 2); ctx.fill();
  } else if (dataMode) {
    ctx.strokeStyle = 'rgba(55,214,255,.7)'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(0, 0, 54, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, 32, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-70, 0); ctx.lineTo(70, 0); ctx.moveTo(0, -70); ctx.lineTo(0, 70); ctx.stroke();
    ctx.fillStyle = '#7ef7d4';
    ctx.beginPath(); ctx.arc(0, 0, 5, 0, Math.PI * 2); ctx.fill();
  } else {
    // 复古罗盘星
    ctx.strokeStyle = 'rgba(120,80,44,.5)'; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.arc(0, 0, 60, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, 46, 0, Math.PI * 2); ctx.stroke();
    for (var k = 0; k < 8; k++) {
      var longRay = (k % 2 === 0), rr = longRay ? 58 : 36;
      ctx.save(); ctx.rotate(k * Math.PI / 4);
      ctx.fillStyle = longRay ? 'rgba(122,74,38,.85)' : 'rgba(150,110,66,.7)';
      ctx.beginPath(); ctx.moveTo(0, -rr); ctx.lineTo(7, 0); ctx.lineTo(0, 8); ctx.lineTo(-7, 0); ctx.closePath(); ctx.fill();
      ctx.restore();
    }
    ctx.fillStyle = 'rgba(122,74,38,.9)';
    ctx.beginPath(); ctx.arc(0, 0, 5, 0, Math.PI * 2); ctx.fill();
  }
  ctx.restore();
}

// 城市铭牌(无照片):同步绘制,钉子立即可见,不依赖 Image().onload
function paintNameplate(group){
  var item = group.userData.item;
  var idx = group.userData.index || 0;
  var theme = THEMES[currentTheme];
  var dataMode = currentTheme === 'data', nightMode = currentTheme === 'night';
  var glassMode = dataMode || nightMode;
  var c = document.createElement('canvas');
  c.width = 384; c.height = 480;
  var ctx = c.getContext('2d');
  ctx.clearRect(0, 0, 384, 480);
  // 卡片底
  ctx.save();
  ctx.shadowColor = nightMode ? 'rgba(104,216,255,.5)' : (dataMode ? 'rgba(55,214,255,.36)' : 'rgba(56,34,17,.34)');
  ctx.shadowBlur = nightMode ? 30 : (dataMode ? 24 : 14);
  ctx.shadowOffsetY = glassMode ? 0 : 9;
  roundRect(ctx, 22, 18, 340, 444, glassMode ? 10 : 6);
  if (dataMode) {
    var dg = ctx.createLinearGradient(22, 18, 362, 462);
    dg.addColorStop(0, '#0b1d2c'); dg.addColorStop(.6, '#06111b'); dg.addColorStop(1, '#03080f');
    ctx.fillStyle = dg;
  } else if (nightMode) {
    var ng = ctx.createLinearGradient(22, 18, 362, 462);
    ng.addColorStop(0, 'rgba(13,34,58,.96)'); ng.addColorStop(.55, 'rgba(4,14,28,.94)'); ng.addColorStop(1, 'rgba(2,6,13,.98)');
    ctx.fillStyle = ng;
  } else {
    ctx.fillStyle = theme.pinPaper;
  }
  ctx.fill();
  ctx.restore();
  ctx.strokeStyle = theme.pinBorder; ctx.lineWidth = 2; ctx.stroke();
  if (currentTheme === 'vintage') {
    for (var s = 0; s < 90; s++) {
      var sx = 30 + (s * 71 % 324), sy = 26 + (s * 47 % 420);
      ctx.fillStyle = 'rgba(92,58,28,' + (.025 + (s % 5) * .008) + ')';
      ctx.fillRect(sx, sy, 1.4, 1.4);
    }
    ctx.strokeStyle = 'rgba(92,64,35,.22)'; ctx.lineWidth = 1.4;
    ctx.strokeRect(34, 30, 316, 420);
  }
  // 徽记
  drawEmblem(ctx, 192, 178);
  // 本命城市徽章
  var isHome = (typeof HOME_PORT !== 'undefined' && HOME_PORT && item.place === HOME_PORT.name);
  if (isHome) {
    ctx.textAlign = 'center';
    ctx.fillStyle = nightMode ? '#ffe08a' : (dataMode ? '#7ef7d4' : '#9a5a2a');
    ctx.font = glassMode ? '700 20px Segoe UI, Arial' : '700 20px Georgia, serif';
    ctx.fillText('★ 本命城市', 192, 80);
  }
  // 城市名(主角)
  ctx.textAlign = 'center';
  ctx.fillStyle = theme.pinText;
  var name = item.place || '';
  var nameSize = name.length > 5 ? 38 : (name.length > 3 ? 46 : 54);
  ctx.font = '600 ' + nameSize + 'px ' + (glassMode ? 'Segoe UI, Arial' : 'Georgia, serif');
  ctx.fillText(name, 192, 332);
  // 国家/地区(与城市同名时不重复,如"新加坡")
  if (item.country && item.country !== item.place) {
    ctx.font = glassMode ? '20px Segoe UI, Arial' : 'italic 22px Georgia, serif';
    ctx.fillStyle = nightMode ? '#9bdcff' : (dataMode ? '#8fd9ee' : '#7b5a39');
    ctx.fillText(item.country, 192, 368);
  }
  // 坐标
  ctx.font = '700 15px Segoe UI, Arial';
  ctx.fillStyle = nightMode ? 'rgba(247,215,131,.8)' : (dataMode ? 'rgba(126,247,212,.8)' : 'rgba(120,86,52,.72)');
  ctx.fillText(fmtCoord(item.lat, item.lon), 192, 406);
  if (currentTheme === 'vintage') {
    ctx.strokeStyle = 'rgba(100,58,35,.3)'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(100, 422); ctx.lineTo(284, 422); ctx.stroke();
  }
  var tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  var mesh = group.children[0];
  if (mesh.material.map) mesh.material.map.dispose();
  mesh.material.dispose();
  mesh.material = new THREE.MeshBasicMaterial({ map: tex, transparent: true, side: THREE.DoubleSide });
  group.rotation.z = ((idx % 5) - 2) * (glassMode ? .012 : .046);
}

function updatePhotoTexture(group){
  var item = group.userData.item;
  if (!item.thumb) { paintNameplate(group); return; }
  var img = new Image();
  img.onload = function(){
    var c = document.createElement('canvas');
    c.width = 384; c.height = 480;
    var ctx = c.getContext('2d');
    var theme = THEMES[currentTheme];
    var dataMode = currentTheme === 'data';
    var nightMode = currentTheme === 'night';
    var glassMode = dataMode || nightMode;
    ctx.clearRect(0,0,c.width,c.height);
    ctx.save();
    ctx.shadowColor = nightMode ? 'rgba(104,216,255,.54)' : (dataMode ? 'rgba(55,214,255,.38)' : 'rgba(56,34,17,.34)');
    ctx.shadowBlur = nightMode ? 30 : (dataMode ? 24 : 14);
    ctx.shadowOffsetY = glassMode ? 0 : 9;
    roundRect(ctx, 22, 18, 340, 428, glassMode ? 10 : 5);
    if (dataMode) {
      var cardGrad = ctx.createLinearGradient(22, 18, 362, 446);
      cardGrad.addColorStop(0, '#0b1d2c');
      cardGrad.addColorStop(.58, '#06111b');
      cardGrad.addColorStop(1, '#03080f');
      ctx.fillStyle = cardGrad;
    } else if (nightMode) {
      var nightGrad = ctx.createLinearGradient(22, 18, 362, 446);
      nightGrad.addColorStop(0, 'rgba(13,34,58,.96)');
      nightGrad.addColorStop(.52, 'rgba(4,14,28,.94)');
      nightGrad.addColorStop(1, 'rgba(2,6,13,.98)');
      ctx.fillStyle = nightGrad;
    } else {
      ctx.fillStyle = theme.pinPaper;
    }
    ctx.fill();
    ctx.restore();
    ctx.strokeStyle = theme.pinBorder;
    ctx.lineWidth = 2;
    ctx.stroke();
    if (dataMode) {
      ctx.strokeStyle = 'rgba(126,247,212,.32)';
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(42, 34); ctx.lineTo(176, 34); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(344, 312); ctx.lineTo(344, 424); ctx.stroke();
      ctx.fillStyle = 'rgba(55,214,255,.16)';
      for (var gy=70; gy<322; gy+=34) {
        ctx.fillRect(42, gy, 300, 1);
      }
    } else if (nightMode) {
      ctx.strokeStyle = 'rgba(247,215,131,.38)';
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(46, 34); ctx.lineTo(160, 34); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(340, 352); ctx.lineTo(340, 424); ctx.stroke();
      var halo = ctx.createRadialGradient(312, 76, 8, 312, 76, 128);
      halo.addColorStop(0, 'rgba(104,216,255,.26)');
      halo.addColorStop(1, 'rgba(104,216,255,0)');
      ctx.fillStyle = halo;
      ctx.fillRect(184, 18, 178, 164);
    }
    if (currentTheme === 'vintage') {
      for (var speck=0; speck<95; speck++) {
        var sx = 30 + (speck * 71 % 324), sy = 26 + (speck * 47 % 406);
        ctx.fillStyle = 'rgba(92,58,28,' + (.025 + (speck % 5) * .008) + ')';
        ctx.fillRect(sx, sy, 1.4, 1.4);
      }
    }
    var boxW = 300, boxH = dataMode ? 292 : (nightMode ? 300 : 278), bx = 42, by = dataMode ? 46 : 42;
    ctx.save();
    roundRect(ctx, bx, by, boxW, boxH, glassMode ? 6 : 2);
    ctx.clip();
    var ar = img.width / img.height;
    var dw = boxW, dh = boxW / ar;
    if (dh < boxH) { dh = boxH; dw = boxH * ar; }
    ctx.drawImage(img, bx + (boxW-dw)/2, by + (boxH-dh)/2, dw, dh);
    if (glassMode) {
      var fade = ctx.createLinearGradient(0, by, 0, by + boxH);
      fade.addColorStop(.62, 'rgba(0,0,0,0)');
      fade.addColorStop(1, nightMode ? 'rgba(1,8,18,.42)' : 'rgba(1,9,16,.34)');
      ctx.fillStyle = fade;
      ctx.fillRect(bx, by, boxW, boxH);
    }
    ctx.restore();
    if (dataMode) {
      ctx.strokeStyle = 'rgba(55,214,255,.72)';
      ctx.lineWidth = 2;
      roundRect(ctx, bx, by, boxW, boxH, 6);
      ctx.stroke();
    } else if (nightMode) {
      ctx.strokeStyle = 'rgba(106,216,255,.78)';
      ctx.lineWidth = 2;
      roundRect(ctx, bx, by, boxW, boxH, 6);
      ctx.stroke();
      ctx.strokeStyle = 'rgba(247,215,131,.38)';
      ctx.lineWidth = 1;
      ctx.strokeRect(bx + 5, by + 5, boxW - 10, boxH - 10);
    }
    if (currentTheme === 'vintage') {
      ctx.strokeStyle = 'rgba(92,64,35,.18)';
      ctx.lineWidth = 2;
      ctx.strokeRect(bx + 1, by + 1, boxW - 2, boxH - 2);
    }
    ctx.fillStyle = theme.pinText;
    ctx.font = dataMode ? '700 28px Segoe UI, Arial' : (nightMode ? '700 28px Segoe UI, Arial' : 'italic 30px Georgia, serif');
    ctx.fillText(item.place, 42, nightMode ? 382 : 376);
    ctx.font = glassMode ? '18px Segoe UI, Arial' : '18px Georgia, serif';
    ctx.fillStyle = nightMode ? '#9bdcff' : (dataMode ? '#8fd9ee' : '#7b5a39');
    ctx.fillText(item.country || item.file, 42, nightMode ? 415 : 411);
    if (dataMode) {
      ctx.fillStyle = 'rgba(126,247,212,.82)';
      ctx.font = '700 13px Segoe UI, Arial';
      ctx.fillText(('LAT ' + item.lat.toFixed(2) + '  LON ' + item.lon.toFixed(2)).toUpperCase(), 42, 436);
    } else if (nightMode) {
      ctx.fillStyle = 'rgba(247,215,131,.78)';
      ctx.font = '700 12px Segoe UI, Arial';
      ctx.fillText((item.lat.toFixed(2) + ' / ' + item.lon.toFixed(2)), 42, 438);
    }
    if (currentTheme === 'vintage') {
      ctx.strokeStyle = 'rgba(100,58,35,.22)';
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(42,394); ctx.lineTo(338,391); ctx.stroke();
      ctx.beginPath(); ctx.arc(192,24,7,0,Math.PI*2); ctx.fillStyle = 'rgba(92,64,35,.36)'; ctx.fill();
    }
    var tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    var mesh = group.children[0];
    if (mesh.material.map) mesh.material.map.dispose();
    mesh.material.dispose();
    mesh.material = new THREE.MeshBasicMaterial({ map:tex, transparent:true, side:THREE.DoubleSide });
    group.rotation.z = ((group.userData.index % 5) - 2) * (glassMode ? .012 : .062);
  };
  img.src = item.thumb;
}

function roundRect(ctx, x, y, w, h, r){
  ctx.beginPath();
  ctx.moveTo(x+r,y);
  ctx.arcTo(x+w,y,x+w,y+h,r);
  ctx.arcTo(x+w,y+h,x,y+h,r);
  ctx.arcTo(x,y+h,x,y,r);
  ctx.arcTo(x,y,x+w,y,r);
  ctx.closePath();
}

function buildClusters(items){
  var map = {};
  items.forEach(function(item){
    var key = clusterKey(item);
    if (!map[key]) map[key] = { key:key, place:item.place, country:item.country, items:[], lat:0, lon:0 };
    map[key].items.push(item);
    map[key].lat += item.lat;
    map[key].lon += item.lon;
  });
  return Object.keys(map).map(function(k){
    var c = map[k];
    c.count = c.items.length;
    c.lat /= c.count;
    c.lon /= c.count;
    return c;
  });
}

function clusterKey(item){ return String(item.place || item.file).toLowerCase(); }

function buildClustersSprites(){
  clusters.forEach(function(cluster){
    var spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: makeClusterTexture(cluster), transparent:true }));
    spr.position.copy(latLonToVec(cluster.lat, cluster.lon, R + .31));
    spr.scale.set(.54,.28,.28);
    spr.userData.kind = 'cluster';
    spr.userData.place = cluster.place;
    spr.userData.count = cluster.count;
    spr.userData.lat = cluster.lat;
    spr.userData.lon = cluster.lon;
    scene.add(spr);
    clusterSprites.push(spr);
  });
}

function makeClusterTexture(cluster){
  var c = document.createElement('canvas');
  c.width = 512; c.height = 256;
  var ctx = c.getContext('2d');
  var theme = THEMES[currentTheme];
  var dataMode = currentTheme === 'data';
  var nightMode = currentTheme === 'night';
  var glassMode = dataMode || nightMode;
  ctx.save();
  ctx.shadowColor = nightMode ? 'rgba(104,216,255,.48)' : (dataMode ? 'rgba(55,214,255,.34)' : 'rgba(0,0,0,0)');
  ctx.shadowBlur = glassMode ? 20 : 0;
  ctx.fillStyle = nightMode ? 'rgba(4,13,26,.92)' : (dataMode ? 'rgba(3,12,22,.90)' : 'rgba(245,231,198,.92)');
  roundRect(ctx, 24, 54, 464, 140, glassMode ? 24 : 28);
  ctx.fill();
  ctx.restore();
  ctx.strokeStyle = theme.cluster;
  ctx.lineWidth = glassMode ? 3 : 8;
  ctx.stroke();
  if (glassMode) {
    ctx.strokeStyle = nightMode ? 'rgba(247,215,131,.30)' : 'rgba(126,247,212,.28)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(52,82); ctx.lineTo(460,82); ctx.stroke();
  }
  ctx.fillStyle = theme.pinText;
  ctx.font = glassMode ? '700 42px Segoe UI, Arial' : '700 44px Georgia, serif';
  ctx.textAlign = 'center';
  ctx.fillText(cluster.place + ' ×' + cluster.count, 256, 133);
  ctx.font = glassMode ? '22px Segoe UI, Arial' : '22px Georgia, serif';
  ctx.fillStyle = nightMode ? '#9bdcff' : (dataMode ? '#8fd9ee' : '#76583c');
  ctx.fillText(cluster.country || 'group', 256, 168);
  var tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function refreshClusterTextures(){
  clusterSprites.forEach(function(spr, i){
    if (spr.material.map) spr.material.map.dispose();
    spr.material.map = makeClusterTexture(clusters[i]);
    spr.material.needsUpdate = true;
  });
}

function applyClusterVisibility(){
  var close = radius < 5.18;
  var hidden = 0;
  photoGroups.forEach(function(group){
    var c = clusters.find(function(x){ return x.key === group.userData.clusterKey; });
    var isGrouped = c && c.count > 1;
    group.visible = close || !isGrouped;
    if (!group.visible) hidden++;
  });
  clusterSprites.forEach(function(spr){
    spr.visible = spr.userData.count > 1 && !close;
  });
  var visibleGroups = clusterSprites.filter(function(s){ return s.visible; }).length;
  setStatus(visibleGroups ? '聚合视图' : (IS_USER ? '城市视图' : '照片视图'), IS_USER ? (ITEMS.length + ' 城 · ' + distinctCountries() + ' 国/地区') : (visibleGroups + ' groups / ' + ITEMS.length + ' photos'));
}

function switchTheme(key){
  if (!THEMES[key] || THEMES[key].locked) return;
  currentTheme = key;
  // keep the address bar in sync so refresh / share / back preserve the theme
  try {
    var u = new URL(window.location.href);
    u.searchParams.set('theme', key);
    window.history.replaceState(null, '', u);
  } catch (err) {}
  var theme = THEMES[key];
  document.body.className = theme.body + (typeof TOUR !== 'undefined' && TOUR ? ' tour' : '');
  scene.background = new THREE.Color(theme.bg);
  scene.fog.color = new THREE.Color(theme.fog);
  earth.material = key === 'vintage' ? vintageMat : (key === 'night' ? nightMat : dataMat);
  routeLine.visible = key === 'vintage';
  routeLine.material.color.setHex(theme.route);
  routeLine.material.opacity = .74;
  if (voyageShip) voyageShip.visible = false;
  if (dataRouteLine) {
    dataRouteLine.visible = key === 'data' || key === 'night';
    dataRouteLine.material.opacity = key === 'night' ? .56 : .82;
  }
  if (dataRoutePoints) {
    dataRoutePoints.visible = key === 'data' || key === 'night';
    dataRoutePoints.material.opacity = key === 'night' ? .38 : .22;
  }
  atmosphere.material = key === 'vintage' ? vintageAtmosphereMat : (key === 'night' ? nightAtmosphereMat : dataAtmosphereMat);
  atmosphere.scale.setScalar(key === 'night' ? 1.035 : 1.0);
  if (key === 'vintage') {
    vintageAtmosphereMat.color.setHex(theme.atmosphere);
    vintageAtmosphereMat.opacity = .11;
  } else if (key === 'night') {
    nightAtmosphereMat.uniforms.glowColor.value.setHex(theme.atmosphere);
  } else {
    dataAtmosphereMat.uniforms.glowColor.value.setHex(theme.atmosphere);
  }
  graticuleGroup.visible = key === 'vintage';
  coastlineGroup.visible = key === 'vintage';
  decorGroup.visible = key === 'vintage';
  dataDots.visible = key === 'data';
  auroraGroup.visible = key === 'night';
  anchorLines.forEach(function(line){
    line.visible = key === 'vintage' || key === 'night';
    line.material.color.setHex(key === 'night' ? theme.anchor : 0x5c4023);
    line.material.opacity = key === 'night' ? .58 : (line.userData.baseOpacity || .42);
    line.material.blending = key === 'night' ? THREE.AdditiveBlending : THREE.NormalBlending;
    line.material.needsUpdate = true;
  });
  anchorBeams.forEach(function(beam){
    beam.visible = key === 'night';
    beam.material.color.setHex(theme.anchor || theme.glow);
    beam.material.opacity = key === 'night' ? (beam.userData.baseOpacity || .48) : 0;
  });
  photoGroups.forEach(function(group){
    if (group.userData.trail) group.userData.trail.material.color.setHex(theme.glow);
  });
  document.querySelectorAll('button.theme').forEach(function(btn){
    var on = btn.getAttribute('data-theme') === key;
    btn.classList.toggle('active', on);
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
  photoGroups.forEach(updatePhotoTexture);
  refreshClusterTextures();
  constellation.visible = (key === 'vintage');
  conNodes.visible = (key === 'vintage');
  cloudMesh.visible = (key === 'night' || key === 'vintage');
  cloudMesh.material.opacity = key === 'night' ? .16 : .12;
  cloudMesh.material.color.setHex(key === 'night' ? 0xc8d6f0 : 0xe8dcc2);
  cloudMesh.material.emissiveIntensity = key === 'night' ? .12 : .04;
  applyThemeLighting(key);
}

function applyThemeLighting(themeKey){
  if (themeKey === 'night') {
    sunDir = computeSunDir();
    hemi.color.setHex(0x5e9cff);
    hemi.groundColor.setHex(0x01030a);
    hemi.intensity = .22;
    ambient.color.setHex(0x0a1f38);
    ambient.intensity = .12;
    key.color.setHex(0xfff0d8);          // the sun: warm white, from the real subsolar direction
    key.position.copy(sunDir).multiplyScalar(8);
    key.intensity = 1.65;
    rim.color.setHex(0x8adfff);
    rim.intensity = .9;
    return;
  }
  hemi.color.setHex(0xf1ddb3);
  hemi.groundColor.setHex(0x17110b);
  hemi.intensity = 1.55;
  ambient.color.setHex(0xc09a65);
  ambient.intensity = .46;
  key.color.setHex(0xffedc9);
  key.position.set(4.5, 3.2, 5.2);
  key.intensity = 2.45;
  rim.color.setHex(0x9d7149);
  rim.intensity = .82;
}

function tick(now){
  frame(now || performance.now());
  requestAnimationFrame(tick);
}

// 单帧全流程(相机摆位/Dock缩放/晨昏线uniform/渲染)。tick 逐帧调;renderOnce/导出在 rAF 挂起环境直接调。
function frame(now){
  if (intro.active) {
    updateIntro(now);
  } else {
    if (TOUR && !userControlled) updateTour(now);
    var ease = reduced ? 1 : .09;
    rotX += (targetRotX - rotX) * ease;
    rotY += (targetRotY - rotY) * ease;
    radius += (targetRadius - radius) * ease;
    if (!reduced && !isDragging && !userControlled) targetRotY += .00055;
  }
  var cx = radius * Math.cos(rotX) * Math.sin(rotY);
  var cy = radius * Math.sin(rotX);
  var cz = radius * Math.cos(rotX) * Math.cos(rotY);
  camera.position.set(cx, cy, cz);
  camera.lookAt(0,0,0);
  earth.rotation.y = 0;
  cloudMesh.rotation.y += currentTheme === 'night' ? .00009 : .00005;
  graticuleGroup.rotation.y = 0;
  decorGroup.rotation.y = 0;
  dataDots.rotation.y = 0;
  atmosphere.rotation.y += reduced ? 0 : .00035;
  if (auroraGroup.visible && !reduced) {
    auroraGroup.rotation.y += .00075;
    auroraGroup.children.forEach(function(mesh, i){
      mesh.material.opacity = (mesh.userData.baseOpacity || .24) * (.72 + Math.sin(now * .0011 + i * 1.7) * .18);
    });
  }
  if (currentTheme === 'vintage') {
    var candle = Math.sin(now * .00052) * .28 + Math.sin(now * .0015) * .07;
    key.intensity = 2.45 + candle;
    ambient.intensity = .46 + candle * .10;
    vintageMat.emissiveIntensity = .22 + candle * .07;
    if (vintageAtmosphereMat) vintageAtmosphereMat.opacity = .11 + Math.sin(now * .0008) * .05;
    if (voyageShip && routeCurvePts && !reduced) {
      shipT += .000018;
      if (shipT >= 1) shipT -= 1;
      var fpos = shipT * (routeCurvePts.length - 1);
      var i0 = Math.floor(fpos), fr = fpos - i0;
      var pa = routeCurvePts[i0], pb = routeCurvePts[Math.min(i0 + 1, routeCurvePts.length - 1)];
      var sp = pa.clone().lerp(pb, fr).normalize().multiplyScalar(R + .22);
      var bobS = Math.sin(now * .0016) * .015;
      voyageShip.position.copy(sp).multiplyScalar(1 + bobS / sp.length());
      // hide when on the far side of the globe (occluded)
      var facing = sp.clone().normalize().dot(camera.position.clone().normalize());
      voyageShip.visible = facing > -.05;
    } else if (voyageShip) {
      voyageShip.visible = false;
    }
  } else if (currentTheme === 'night') {
    if (now - lastSunUpdate > 5000) { lastSunUpdate = now; sunDir = computeSunDir(); key.position.copy(sunDir).multiplyScalar(8); }
    if (nightMat.userData.shader) {
      nightMat.userData.shader.uniforms.uTime.value = now * .001;
      nightMat.userData.shader.uniforms.uSunDir.value.copy(sunDir);
    }
  }
  routeLine.rotation.y = 0;
  var scalePhoto = radius < 4.8 ? .96 : .68;
  var camDir = camera.position.clone().normalize();
  // Dock 磁吸:默认卡片收成小钉,靠近屏幕中心的卡片平滑放大(像 macOS Dock)
  photoGroups.forEach(function(group, i){
    group.lookAt(camera.position);
    var bob = reduced ? 0 : Math.sin(now*.0012 + i) * .015;
    var introScale = intro.active ? (group.userData.introScale || 0) : 1;
    var mag = 1;
    if (!intro.active && dockMode) {
      var d = group.position.clone().normalize().dot(camDir);   // 1=正中, 0=边缘
      mag = smoothstep((d - .86) / .12);                        // <=.86 收起, >=.98 全开
    }
    group.userData.mag = mag;
    var collapsed = .14;
    group.scale.setScalar((collapsed + (scalePhoto - collapsed) * mag + bob * mag) * introScale);
    var mesh = group.children[0];
    if (mesh && mesh.material && mesh.material.map) mesh.material.opacity = .40 + .60 * mag;
  });
  clusterSprites.forEach(function(spr, i){
    var s = radius > 6.2 ? 1.1 : .92;
    var mag = 1;
    if (!intro.active && dockMode) {
      var dc = spr.position.clone().normalize().dot(camDir);
      mag = smoothstep((dc - .86) / .12);
    }
    var cs = .26 + (s - .26) * mag;
    spr.scale.set(.58*cs, .30*cs, .30*cs);
    if (spr.material) spr.material.opacity = .30 + .70 * mag;
    spr.userData.mag = mag;
  });
  if (!intro.active) applyClusterVisibility();
  document.getElementById('compassNeedle').style.transformOrigin = '50px 50px';
  document.getElementById('compassNeedle').style.transform = 'rotate(' + (-rotY) + 'rad)';
  renderer.render(scene, camera);
}
})();
</script>
</body>
</html>
"""


def build(photo_dir: Path) -> Tuple[int, int]:
    if not THREE.exists():
        raise SystemExit("Missing three.min.js next to build_globe.py")
    default_demo_dir = (ROOT / "demo_photos").resolve()
    if photo_dir.resolve() == default_demo_dir:
        ensure_demo_photos(photo_dir)
    elif not photo_dir.exists():
        raise SystemExit("Photo directory does not exist: %s" % photo_dir)
    three_js = THREE.read_text(encoding="utf-8")
    land_parts = read_shapefile_parts(NE_LAND_ZIP)
    coast_parts = read_shapefile_parts(NE_COAST_ZIP)
    vintage_map_url = make_vintage_map_data_url(land_parts, coast_parts)
    black_marble_url = make_black_marble_data_url()
    coast_lines = compact_lines_for_js(coast_parts, 4)
    data_dots = make_data_dot_samples(land_parts)
    city_coords = build_city_coords()
    # 导出合并后的坐标表,供入口页(create.html)做完整城市候选
    coords_json = json.dumps(city_coords, ensure_ascii=False, separators=(",", ":"))
    (ROOT / "persona-core" / "city_coords.json").write_text(coords_json, encoding="utf-8")

    def render(items: List[Dict[str, object]], dots=None, title: str = "我的旅行地球 · Travel Globe",
               og_desc: str = "勾选去过的城市,生成专属的复古航海图 3D 地球——单文件、无账号、数据不出浏览器。",
               force_demo: bool = False) -> str:
        return (
            HTML.replace("@@THREE@@", three_js)
            .replace("@@ITEMS@@", json.dumps(items, ensure_ascii=False, separators=(",", ":")))
            .replace("@@CITY_COORDS@@", coords_json)
            .replace("@@VINTAGE_MAP_URL@@", json.dumps(vintage_map_url, separators=(",", ":")))
            .replace("@@BLACK_MARBLE_URL@@", json.dumps(black_marble_url, separators=(",", ":")))
            .replace("@@COAST_LINES@@", json.dumps(coast_lines, separators=(",", ":")))
            .replace("@@DATA_DOTS@@", json.dumps(data_dots if dots is None else dots, separators=(",", ":")))
            .replace("@@PAGE_TITLE@@", title)
            .replace("@@OG_DESC@@", og_desc)
            .replace("@@OG_IMAGE@@", PAGES_BASE + "assets/hero-vintage.jpg")
            .replace("@@FORCE_DEMO@@", "true" if force_demo else "false")
        )

    docs = ROOT / "docs"
    (docs / "persona-core").mkdir(parents=True, exist_ok=True)

    # 相册版(内嵌demo照片,锁定演示数据不被本地数据劫持):root 遗留路径 + docs/album.html
    last_size = 0
    last_count = 0
    for quality in (86, 78, 70, 62, 54, 48):
        items = collect_items(photo_dir, quality)
        out = render(items, title="Travel Globe · Photo Album Demo",
                     og_desc="Photos pinned on a vintage nautical 3D globe by their EXIF GPS — single-file, offline-ready.",
                     force_demo=True)
        OUT.write_text(out, encoding="utf-8")
        last_size = OUT.stat().st_size
        last_count = len(items)
        if last_size <= MAX_HTML_BYTES:
            break
    else:
        raise SystemExit("Travel_Globe.html is still over 15MB after compression: %.2f MB" % (last_size / 1048576))
    (docs / "album.html").write_text(OUT.read_text(encoding="utf-8"), encoding="utf-8")

    # 轻量版(无内嵌照片,运行时城市铭牌;无数据时回退精选名城示例):docs/index.html = GitHub Pages 落地页
    # data 主题无 UI 入口(付费预留),其点阵数据是死重 → 轻量版裁掉
    lite = render([], dots=[])
    (docs / "index.html").write_text(lite, encoding="utf-8")
    lite_size = (docs / "index.html").stat().st_size

    # 入口页与坐标表进 docs(Pages 自包含)
    entry_src = ROOT / "create.html"
    if entry_src.exists():
        (docs / "create.html").write_text(entry_src.read_text(encoding="utf-8"), encoding="utf-8")
    (docs / "persona-core" / "city_coords.json").write_text(coords_json, encoding="utf-8")

    print("lite_mb: %.2f (docs/index.html)" % (lite_size / 1048576))
    return last_count, last_size


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the offline Travel Globe single HTML.")
    parser.add_argument("photo_dir", nargs="?", default=str(ROOT / "demo_photos"))
    args = parser.parse_args()
    count, size = build(Path(args.photo_dir).resolve())
    print("written:", OUT)
    print("photos:", count)
    print("size_mb: %.2f" % (size / 1048576))


if __name__ == "__main__":
    main()
