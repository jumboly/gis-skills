#!/usr/bin/env python3
"""GIS ファイル情報検出スクリプト: ファイルのフォーマットやメタデータを調査する"""

import argparse
import json
import os
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="GIS ファイルのフォーマット・メタデータを検出して JSON で出力する"
    )
    parser.add_argument("--input", required=True, help="調査対象のファイルパス")
    return parser.parse_args()


def detect_format_from_extension(path):
    """拡張子からフォーマットを推定する"""
    ext = os.path.splitext(path)[1].lower()
    format_map = {
        ".geojson": "GeoJSON",
        ".json": "GeoJSON",
        ".shp": "ESRI Shapefile",
        ".kml": "KML",
        ".gpkg": "GeoPackage",
        ".csv": "CSV",
        ".tsv": "TSV",
        ".gml": "GML",
        ".gpx": "GPX",
    }
    return format_map.get(ext, f"Unknown ({ext})")


def detect_shapefile_encoding(shp_path):
    """Shapefile の .cpg ファイルからエンコーディングを検出する"""
    base = os.path.splitext(shp_path)[0]
    cpg_path = base + ".cpg"
    try:
        with open(cpg_path, "r") as f:
            return f.read().strip()
    except (FileNotFoundError, OSError):
        pass

    # .dbf ファイルの LDID バイトからの検出は省略し、推定値を返す
    return None


def inspect_with_geopandas(path, detected_format):
    """geopandas/fiona を使って詳細情報を取得する"""
    import fiona
    import geopandas as gpd

    report = {
        "file": os.path.abspath(path),
        "format": detected_format,
    }

    read_kwargs = {}
    if detected_format == "KML":
        read_kwargs["driver"] = "KML"

    # fiona で低レベル情報を取得
    try:
        open_kwargs = {}
        if detected_format == "KML":
            open_kwargs["driver"] = "KML"

        with fiona.open(path, **open_kwargs) as src:
            report["crs"] = str(src.crs) if src.crs else None
            report["crs_wkt"] = src.crs_wkt if hasattr(src, "crs_wkt") and src.crs_wkt else None
            report["feature_count"] = len(src)
            report["driver"] = src.driver

            # フィールド情報
            schema = src.schema
            report["geometry_type_schema"] = schema.get("geometry", None)
            fields = {}
            for name, ftype in schema.get("properties", {}).items():
                fields[name] = ftype
            report["fields"] = fields

            # レイヤ情報（GeoPackage など）
            if hasattr(src, "listlayers"):
                try:
                    # fiona.listlayers はファイルパスに対して呼ぶ
                    layers = fiona.listlayers(path)
                    report["layers"] = layers
                except Exception:
                    pass
    except Exception as e:
        report["fiona_error"] = str(e)

    # geopandas で実際のジオメトリタイプを集計
    try:
        gdf = gpd.read_file(path, **read_kwargs)
        geom_types = gdf.geometry.geom_type.value_counts().to_dict()
        report["geometry_types_actual"] = geom_types
        report["feature_count"] = len(gdf)
        report["bounds"] = {
            "minx": round(gdf.total_bounds[0], 6),
            "miny": round(gdf.total_bounds[1], 6),
            "maxx": round(gdf.total_bounds[2], 6),
            "maxy": round(gdf.total_bounds[3], 6),
        }
    except Exception as e:
        report["geopandas_error"] = str(e)

    # Shapefile 固有: エンコーディング検出
    if detected_format == "ESRI Shapefile":
        enc = detect_shapefile_encoding(path)
        report["encoding_detected"] = enc

        # 関連ファイルの存在確認
        base = os.path.splitext(path)[0]
        related_exts = [".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".xml"]
        related = {}
        for ext in related_exts:
            related[ext] = os.path.exists(base + ext)
        report["related_files"] = related

    return report


def inspect_geojson_pure(path):
    """geopandas なしで GeoJSON を調査する（フォールバック）"""
    report = {
        "file": os.path.abspath(path),
        "format": "GeoJSON",
        "inspection_method": "pure_python",
    }

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except UnicodeDecodeError:
        # cp932 でリトライ
        try:
            with open(path, "r", encoding="cp932") as f:
                data = json.load(f)
            report["encoding"] = "cp932"
        except Exception as e:
            report["error"] = f"ファイルの読み込みに失敗しました: {e}"
            return report
    except json.JSONDecodeError as e:
        report["error"] = f"JSON パースに失敗しました: {e}"
        return report

    report["type"] = data.get("type", None)

    if data.get("type") == "FeatureCollection":
        features = data.get("features", [])
        report["feature_count"] = len(features)

        # ジオメトリタイプの集計
        geom_types = {}
        field_names = set()
        for feat in features:
            geom = feat.get("geometry")
            if geom:
                gt = geom.get("type", "Unknown")
                geom_types[gt] = geom_types.get(gt, 0) + 1

            props = feat.get("properties", {})
            if props:
                field_names.update(props.keys())

        report["geometry_types"] = geom_types
        report["fields"] = sorted(field_names)

        # フィールドの型を最初のフィーチャから推定
        if features:
            first_props = features[0].get("properties", {})
            field_types = {}
            for k, v in first_props.items():
                field_types[k] = type(v).__name__
            report["field_types_sample"] = field_types

        # CRS（GeoJSON 2008 仕様の crs プロパティ）
        crs = data.get("crs")
        if crs:
            report["crs"] = crs
        else:
            report["crs"] = "EPSG:4326 (GeoJSON default)"

    elif data.get("type") == "Feature":
        report["feature_count"] = 1
        geom = data.get("geometry")
        if geom:
            report["geometry_types"] = {geom.get("type", "Unknown"): 1}
        props = data.get("properties", {})
        report["fields"] = sorted(props.keys()) if props else []

    elif data.get("type") in (
        "Point", "MultiPoint", "LineString", "MultiLineString",
        "Polygon", "MultiPolygon", "GeometryCollection",
    ):
        report["feature_count"] = 1
        report["geometry_types"] = {data["type"]: 1}
        report["fields"] = []
    else:
        report["warning"] = f"不明な GeoJSON タイプ: {data.get('type')}"

    return report


def inspect_csv_pure(path):
    """CSV ファイルのカラム情報を取得する"""
    import csv as csv_mod

    report = {
        "file": os.path.abspath(path),
        "format": "CSV",
        "inspection_method": "pure_python",
    }

    # ヘッダーだけでエンコーディングを判定し、行数カウントは1回だけ行う
    encoding_used = None
    header = None
    for enc in ["utf-8", "cp932", "shift_jis", "euc-jp"]:
        try:
            with open(path, "r", encoding=enc) as f:
                reader = csv_mod.reader(f)
                header = next(reader, None)
            encoding_used = enc
            break
        except (UnicodeDecodeError, csv_mod.Error):
            continue

    row_count = 0
    if encoding_used is not None:
        with open(path, "r", encoding=encoding_used) as f:
            reader = csv_mod.reader(f)
            next(reader, None)  # ヘッダーをスキップ
            row_count = sum(1 for _ in reader)

    if encoding_used is None:
        report["error"] = "エンコーディングを検出できませんでした。"
        return report

    report["encoding"] = encoding_used
    report["columns"] = header
    report["row_count"] = row_count

    # 座標カラムの候補を検出
    lat_candidates = [c for c in (header or []) if c.lower() in ("lat", "latitude", "y", "緯度")]
    lon_candidates = [c for c in (header or []) if c.lower() in ("lon", "lng", "longitude", "x", "経度")]
    if lat_candidates or lon_candidates:
        report["coordinate_columns_hint"] = {
            "latitude_candidates": lat_candidates,
            "longitude_candidates": lon_candidates,
        }

    return report


def main():
    args = parse_args()

    if not os.path.exists(args.input):
        print(
            json.dumps(
                {"error": f"ファイルが見つかりません: {args.input}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    detected_format = detect_format_from_extension(args.input)

    # geopandas/fiona が利用可能か試す（未インストールなら自動インストールを試行）
    use_geopandas = True
    try:
        import fiona  # noqa: F401
        import geopandas  # noqa: F401
    except ImportError:
        import subprocess
        for pkg in ["fiona", "geopandas", "pyproj"]:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg, "-q"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError:
                pass
        try:
            import fiona  # noqa: F811, F401
            import geopandas  # noqa: F811, F401
        except ImportError:
            use_geopandas = False

    if use_geopandas and detected_format not in ("CSV", "TSV"):
        try:
            report = inspect_with_geopandas(args.input, detected_format)
        except Exception as e:
            # geopandas でエラーが出た場合はフォールバック
            report = {"error": f"geopandas での解析に失敗しました: {e}"}
            if detected_format == "GeoJSON":
                report = inspect_geojson_pure(args.input)
            elif detected_format == "CSV":
                report = inspect_csv_pure(args.input)
    else:
        # フォールバック: 純粋な Python で調査
        if detected_format == "GeoJSON":
            report = inspect_geojson_pure(args.input)
        elif detected_format in ("CSV", "TSV"):
            report = inspect_csv_pure(args.input)
        else:
            report = {
                "file": os.path.abspath(args.input),
                "format": detected_format,
                "warning": "geopandas/fiona がインストールされていないため、詳細情報を取得できません。",
                "file_size_bytes": os.path.getsize(args.input),
            }

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
