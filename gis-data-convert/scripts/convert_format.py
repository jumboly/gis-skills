#!/usr/bin/env python3
"""GIS データフォーマット変換スクリプト"""

import argparse
import json
import os
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="GIS データのフォーマット変換を行う")
    parser.add_argument("--input", required=True, help="入力ファイルパス")
    parser.add_argument("--output", required=True, help="出力ファイルパス")
    parser.add_argument(
        "--input-encoding",
        default=None,
        help="入力ファイルのエンコーディング（省略時は自動検出）",
    )
    parser.add_argument(
        "--output-crs",
        default=None,
        help="出力の座標参照系（EPSG コード、例: 4326）",
    )
    parser.add_argument(
        "--csv-lat", default=None, help="CSV の緯度カラム名"
    )
    parser.add_argument(
        "--csv-lon", default=None, help="CSV の経度カラム名"
    )
    parser.add_argument(
        "--csv-crs",
        default="EPSG:4326",
        help="CSV 座標の CRS（デフォルト: EPSG:4326）",
    )
    parser.add_argument(
        "--layer",
        default=None,
        help="GeoPackage のレイヤ名（入力・出力で使用）",
    )
    return parser.parse_args()


def detect_format(path):
    """拡張子からフォーマットを推定する"""
    ext = os.path.splitext(path)[1].lower()
    format_map = {
        ".geojson": "GeoJSON",
        ".json": "GeoJSON",
        ".shp": "ESRI Shapefile",
        ".kml": "KML",
        ".gpkg": "GPKG",
        ".csv": "CSV",
    }
    fmt = format_map.get(ext)
    if fmt is None:
        print(
            json.dumps(
                {"error": f"未対応の拡張子です: {ext}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)
    return fmt


def detect_shapefile_encoding(shp_path):
    """Shapefile のエンコーディングを検出する"""
    base = os.path.splitext(shp_path)[0]
    cpg_path = base + ".cpg"

    try:
        with open(cpg_path, "r") as f:
            encoding = f.read().strip()
        if encoding:
            return encoding
    except (FileNotFoundError, OSError):
        pass

    # .cpg がない場合は utf-8 を先に試し、失敗時に cp932 にフォールバック
    return None


def read_csv_as_geodataframe(path, lat_col, lon_col, csv_crs, encoding=None):
    """CSV を GeoDataFrame として読み込む"""
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import Point

    if lat_col is None or lon_col is None:
        print(
            json.dumps(
                {"error": "CSV 入力には --csv-lat と --csv-lon の指定が必要です。"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        df = pd.read_csv(path, encoding=encoding)
    except UnicodeDecodeError:
        # エンコーディング自動検出: utf-8 → cp932 の順に試行
        for enc in ["utf-8", "cp932", "shift_jis", "euc-jp"]:
            try:
                df = pd.read_csv(path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            print(
                json.dumps(
                    {"error": "CSV ファイルのエンコーディングを検出できませんでした。--input-encoding を指定してください。"},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            sys.exit(1)

    if lat_col not in df.columns or lon_col not in df.columns:
        print(
            json.dumps(
                {
                    "error": f"指定されたカラムが見つかりません。利用可能なカラム: {list(df.columns)}",
                    "csv_lat": lat_col,
                    "csv_lon": lon_col,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    geometry = [Point(xy) for xy in zip(df[lon_col], df[lat_col])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=csv_crs)
    return gdf


def main():
    args = parse_args()

    try:
        import geopandas as gpd
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
        import geopandas as gpd

    input_format = detect_format(args.input)
    output_format = detect_format(args.output)

    # --- 入力読み込み ---
    encoding = args.input_encoding

    if input_format == "CSV":
        gdf = read_csv_as_geodataframe(
            args.input, args.csv_lat, args.csv_lon, args.csv_crs, encoding
        )
    elif input_format == "ESRI Shapefile":
        if encoding is None:
            encoding = detect_shapefile_encoding(args.input)
        # エンコーディング候補を順に試行
        encodings_to_try = [encoding] if encoding else ["utf-8", "cp932"]
        gdf = None
        last_error = None
        for enc in encodings_to_try:
            try:
                gdf = gpd.read_file(args.input, encoding=enc)
                break
            except Exception as e:
                last_error = e
                continue
        if gdf is None:
            # 全エンコーディングで失敗
            try:
                gdf = gpd.read_file(args.input)
            except Exception as e:
                print(
                    json.dumps(
                        {"error": f"Shapefile の読み込みに失敗しました: {e}"},
                        ensure_ascii=False,
                    ),
                    file=sys.stderr,
                )
                sys.exit(1)
    elif input_format == "GPKG" and args.layer:
        try:
            gdf = gpd.read_file(args.input, layer=args.layer)
        except Exception as e:
            print(
                json.dumps(
                    {"error": f"GeoPackage の読み込みに失敗しました（レイヤ: {args.layer}）: {e}"},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        try:
            kwargs = {}
            if input_format == "KML":
                # KML は fiona の KML ドライバが必要
                kwargs["driver"] = "KML"
            gdf = gpd.read_file(args.input, **kwargs)
        except Exception as e:
            print(
                json.dumps(
                    {"error": f"入力ファイルの読み込みに失敗しました: {e}"},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            sys.exit(1)

    # --- CRS 変換 ---
    if args.output_crs:
        try:
            epsg = int(args.output_crs)
            gdf = gdf.to_crs(epsg=epsg)
        except ValueError:
            # EPSG:4326 のような文字列も受け付ける
            gdf = gdf.to_crs(args.output_crs)
        except Exception as e:
            print(
                json.dumps(
                    {"error": f"CRS 変換に失敗しました: {e}"},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            sys.exit(1)

    # --- 出力書き込み ---
    try:
        write_kwargs = {}
        if output_format == "GPKG":
            write_kwargs["driver"] = "GPKG"
            if args.layer:
                write_kwargs["layer"] = args.layer
        elif output_format == "KML":
            write_kwargs["driver"] = "KML"
        elif output_format == "ESRI Shapefile":
            write_kwargs["driver"] = "ESRI Shapefile"
        elif output_format == "GeoJSON":
            write_kwargs["driver"] = "GeoJSON"
        elif output_format == "CSV":
            # CSV 出力: ジオメトリを WKT に変換して保存
            import pandas as pd

            df = pd.DataFrame(gdf.drop(columns="geometry"))
            df["geometry_wkt"] = gdf.geometry.to_wkt()
            df.to_csv(args.output, index=False, encoding="utf-8")
            geom_types = gdf.geometry.geom_type.value_counts().to_dict()
            summary = {
                "status": "success",
                "input_file": args.input,
                "input_format": input_format,
                "output_file": args.output,
                "output_format": "CSV",
                "feature_count": len(gdf),
                "geometry_types": geom_types,
                "crs": str(gdf.crs) if gdf.crs else None,
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return

        gdf.to_file(args.output, **write_kwargs)
    except Exception as e:
        print(
            json.dumps(
                {"error": f"出力ファイルの書き込みに失敗しました: {e}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    geom_types = gdf.geometry.geom_type.value_counts().to_dict()
    summary = {
        "status": "success",
        "input_file": args.input,
        "input_format": input_format,
        "output_file": args.output,
        "output_format": output_format,
        "feature_count": len(gdf),
        "geometry_types": geom_types,
        "crs": str(gdf.crs) if gdf.crs else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
