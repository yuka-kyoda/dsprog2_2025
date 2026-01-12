# 使用fletバージョン：0.28.3

import flet as ft
import requests
import time
import re as _re
import sqlite3
import os
from datetime import datetime, timedelta
from collections import defaultdict

# ---------------------------------------------
# データベース設計と初期化
# ---------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(CURRENT_DIR, "weather_forecast.db")

def init_database():
    """データベースの初期化と必要なテーブルの作成"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # エリアテーブル
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS areas (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        region TEXT NOT NULL
    )
    ''')
    
    # 天気予報テーブル
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area_code TEXT NOT NULL,
        forecast_date TEXT NOT NULL,
        report_datetime TEXT NOT NULL,
        weather_code TEXT,
        telop TEXT,
        temp_min TEXT,
        temp_max TEXT,
        publishing_office TEXT,
        UNIQUE(area_code, forecast_date, report_datetime)
    )
    ''')
    
    conn.commit()
    conn.close()

# ---------------------------------------------
# 気象庁 JSON
# ---------------------------------------------
AREA_JSON_URL = "https://www.jma.go.jp/bosai/common/const/area.json"
FORECAST_BASE = "https://www.jma.go.jp/bosai/forecast/data/forecast/"  # {code}.json

# ---------------------------------------------
# リトライ（指数バックオフ）
# ---------------------------------------------
def get_json(url: str, tries: int = 3, timeout: int = 10):
    last_err = None
    for i in range(tries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code} for {url}")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            if i < tries - 1:
                time.sleep(2 ** i)
            else:
                raise last_err

# ---------------------------------------------
# TELOPS（天気コード→日本語テロップ）
# ---------------------------------------------
TELOPS: dict[int, str] = {
    100:"晴",101:"晴時々曇",102:"晴一時雨",103:"晴時々雨",104:"晴一時雪",105:"晴時々雪",
    106:"晴一時雨か雪",107:"晴時々雨か雪",108:"晴一時雨か雷雨",
    110:"晴後時々曇",111:"晴後曇",112:"晴後一時雨",113:"晴後時々雨",114:"晴後雨",
    115:"晴後一時雪",116:"晴後時々雪",117:"晴後雪",118:"晴後雨か雪",119:"晴後雨か雷雨",
    120:"晴朝夕一時雨",121:"晴朝の内一時雨",122:"晴夕方一時雨",
    123:"晴山沿い雷雨",124:"晴山沿い雪",125:"晴午後は雷雨",
    126:"晴昼頃から雨",127:"晴夕方から雨",128:"晴夜は雨",
    130:"朝の内霧後晴",131:"晴明け方霧",132:"晴朝夕曇",
    140:"晴時々雨で雷を伴う",160:"晴一時雪か雨",170:"晴時々雪か雨",181:"晴後雪か雨",
    200:"曇",201:"曇時々晴",202:"曇一時雨",203:"曇時々雨",204:"曇一時雪",205:"曇時々雪",
    206:"曇一時雨か雪",207:"曇時々雨か雪",208:"曇一時雨か雷雨",209:"霧",
    210:"曇後時々晴",211:"曇後晴",212:"曇後一時雨",213:"曇後時々雨",214:"曇後雨",
    215:"曇後一時雪",216:"曇後時々雪",217:"曇後雪",218:"曇後雨か雪",219:"曇後雨か雷雨",
    220:"曇朝夕一時雨",221:"曇朝の内一時雨",222:"曇夕方一時雨",
    223:"曇日中時々晴",224:"曇昼頃から雨",225:"曇夕方から雨",226:"曇夜は雨",
    228:"曇昼頃から雪",229:"曇夕方から雪",230:"曇夜は雪",231:"曇海上海岸は霧か霧雨",
    240:"曇時々雨で雷を伴う",250:"曇時々雪で雷を伴う",
    260:"曇一時雪か雨",270:"曇時々雪か雨",281:"曇後雪か雨",
    300:"雨",301:"雨時々晴",302:"雨時々止む",303:"雨時々雪",304:"雨か雪",
    306:"大雨",308:"雨で暴風を伴う",309:"雨一時雪",
    311:"雨後晴",313:"雨後曇",314:"雨後時々雪",315:"雨後雪",
    316:"雨か雪後晴",317:"雨か雪後曇",
    320:"朝の内雨後晴",321:"朝の内雨後曇",
    322:"雨朝晩一時雪",323:"雨昼頃から晴",324:"雨夕方から晴",325:"雨夜は晴",
    326:"雨夕方から雪",327:"雨夜は雪",
    328:"雨一時強く降る",329:"雨一時みぞれ",
    340:"雪か雨",350:"雨で雷を伴う",
    361:"雪か雨後晴",371:"雪か雨後曇",
    400:"雪",401:"雪時々晴",402:"雪時々止む",403:"雪時々雨",
    405:"大雪",406:"風雪強い",407:"暴風雪",409:"雪一時雨",
    411:"雪後晴",413:"雪後曇",414:"雪後雨",
    420:"朝の内雪後晴",421:"朝の内雪後曇",
    422:"雪昼頃から雨",423:"雪夕方から雨",
    425:"雪一時強く降る",426:"雪後みぞれ",427:"雪一時みぞれ",
    450:"雪で雷を伴う",
    500:"快晴",
}
WEEKDAYS_JP = ["月","火","水","木","金","土","日"]

def keyword_to_emoji(word: str) -> str:
    if not word: return "⛅"
    w = word
    if "快晴" in w or "晴" in w: return "☀️"
    if "曇" in w or "くもり" in w: return "☁️"
    if "雷雨" in w: return "⚡️"
    if "雨" in w or "霧雨" in w or "大雨" in w: return "☂️"
    if "雪" in w or "みぞれ" in w or "風雪" in w or "暴風雪" in w: return "❄️"
    if "霧" in w: return "🌫️"
    return "☁️"

def stack_center_with_corner(primary_word: str, secondary_word: str, corner: str = "top_right") -> ft.Control:
    e_pri = keyword_to_emoji(primary_word)
    e_sec = keyword_to_emoji(secondary_word)
    if e_pri == e_sec:
        return ft.Text(e_pri, size=28, text_align=ft.TextAlign.CENTER)
    big = ft.Container(content=ft.Text(e_pri, size=30), alignment=ft.alignment.center, expand=True)
    small_align = {"top_right": ft.alignment.top_right, "bottom_right": ft.alignment.bottom_right,
                   "top_left": ft.alignment.top_left, "bottom_left": ft.alignment.bottom_left}.get(corner, ft.alignment.top_right)
    small = ft.Container(content=ft.Text(e_sec, size=18), alignment=small_align, padding=4, expand=True)
    return ft.Stack(controls=[big, small], width=80, height=50)

def row_left_right(primary_word: str, secondary_word: str) -> ft.Control:
    e_pri = keyword_to_emoji(primary_word)
    e_sec = keyword_to_emoji(secondary_word)
    if e_pri == e_sec:
        return ft.Text(e_pri, size=28, text_align=ft.TextAlign.CENTER)
    return ft.Row(controls=[ft.Text(e_pri, size=26), ft.Text(e_sec, size=26)],
                  alignment=ft.MainAxisAlignment.CENTER, spacing=8)

def compose_icon_from_telop(telop: str) -> ft.Control:
    if not telop:
        return ft.Text("⛅", size=28, text_align=ft.TextAlign.CENTER)
    m伴う = _re.search(r"(.+?)で(.+?)を伴う", telop)
    if m伴う:
        return ft.Text(keyword_to_emoji(m伴う.group(2)), size=28, text_align=ft.TextAlign.CENTER)
    m時々 = _re.search(r"(.+?)時々(.+)", telop)
    if m時々:
        return stack_center_with_corner(m時々.group(1), m時々.group(2), corner="top_right")
    m一時 = _re.search(r"(.+?)一時(.+)", telop)
    if m一時:
        return stack_center_with_corner(m一時.group(1), m一時.group(2), corner="bottom_right")
    m後 = _re.search(r"(.+?)後(.+)", telop)
    if m後:
        return row_left_right(m後.group(1), m後.group(2))
    mか = _re.search(r"(.+?)か(.+)", telop)
    if mか:
        return ft.Text(keyword_to_emoji(mか.group(1)), size=28, text_align=ft.TextAlign.CENTER)
    return ft.Text(keyword_to_emoji(telop), size=28, text_align=ft.TextAlign.CENTER)

def to_date_label_with_weekday(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime(f"%Y-%m-%d（{WEEKDAYS_JP[dt.weekday()]}）")
    except Exception:
        return iso

# ---------------------------------------------
# データベース操作関数
# ---------------------------------------------
def save_areas_to_db(areas: list):
    """地域情報をデータベースに保存する"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for area in areas:
        prefix = area["code"][:2]
        region = region_name_for_prefix(prefix)
        cursor.execute(
            "INSERT OR REPLACE INTO areas (code, name, region) VALUES (?, ?, ?)",
            (area["code"], area["name"], region)
        )
    
    conn.commit()
    conn.close()

def get_areas_from_db():
    """データベースから地域情報を取得する"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT code, name, region FROM areas ORDER BY code")
    areas = [{"code": row[0], "name": row[1], "region": row[2]} for row in cursor.fetchall()]
    
    conn.close()
    return areas

def save_forecast_to_db(area_code: str, forecast_data: dict):
    """天気予報データをデータベースに保存する"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    publishing_office = forecast_data.get("publishingOffice", "")
    report_datetime = forecast_data.get("reportDatetime", "")
    
    # 週間予報データの保存
    for forecast in forecast_data.get("weekly", []):
        date_time = forecast.get("dateTime", "")
        weather_code = forecast.get("weatherCode", "")
        
        # テロップの取得
        telop = ""
        try:
            n = int(weather_code)
            telop = TELOPS.get(n, "")
        except:
            pass
        
        # 温度データの検索
        temp_min = ""
        temp_max = ""
        for temp_data in forecast_data.get("weekly_temps", []):
            if temp_data.get("dateTime") == date_time:
                temp_min = temp_data.get("min", "")
                temp_max = temp_data.get("max", "")
                break
        
        cursor.execute(
            """
            INSERT OR REPLACE INTO forecasts 
            (area_code, forecast_date, report_datetime, weather_code, telop, temp_min, temp_max, publishing_office)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (area_code, date_time, report_datetime, weather_code, telop, temp_min, temp_max, publishing_office)
        )
    
    conn.commit()
    conn.close()

def get_forecast_from_db(area_code: str, report_date: str = None):
    """
    データベースから特定エリアの天気予報データを取得する
    report_date が指定されていない場合は最新のデータを返す
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    result = {
        "publishingOffice": None,
        "reportDatetime": None,
        "weekly": [],
        "weekly_temps": []
    }
    
    if report_date:
        # 指定された日付の予報を取得
        cursor.execute(
            """
            SELECT report_datetime, publishing_office FROM forecasts 
            WHERE area_code = ? AND report_datetime LIKE ? 
            ORDER BY report_datetime DESC LIMIT 1
            """,
            (area_code, f"{report_date}%")
        )
    else:
        # 最新の予報を取得
        cursor.execute(
            """
            SELECT report_datetime, publishing_office FROM forecasts 
            WHERE area_code = ? 
            ORDER BY report_datetime DESC LIMIT 1
            """,
            (area_code,)
        )
    
    row = cursor.fetchone()
    if row:
        report_datetime, publishing_office = row
        result["reportDatetime"] = report_datetime
        result["publishingOffice"] = publishing_office
        
        # その日付の予報データを取得
        cursor.execute(
            """
            SELECT forecast_date, weather_code, telop, temp_min, temp_max 
            FROM forecasts 
            WHERE area_code = ? AND report_datetime = ?
            ORDER BY forecast_date
            """,
            (area_code, report_datetime)
        )
        
        for row in cursor.fetchall():
            forecast_date, weather_code, telop, temp_min, temp_max = row
            result["weekly"].append({
                "dateTime": forecast_date,
                "weatherCode": weather_code,
                "telop": telop
            })
            result["weekly_temps"].append({
                "dateTime": forecast_date,
                "min": temp_min,
                "max": temp_max
            })
    
    conn.close()
    return result

def get_forecast_dates_for_area(area_code: str):
    """特定のエリアコードで利用可能な予報日付のリストを取得する"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT DISTINCT substr(report_datetime, 1, 10) as report_date
        FROM forecasts 
        WHERE area_code = ?
        ORDER BY report_date DESC
        """,
        (area_code,)
    )
    
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    return dates

# ---------------------------------------------
# 取得
# ---------------------------------------------
def fetch_area_list():
    """APIから地域リストを取得し、DBにも保存する"""
    # まずDBから取得を試みる
    db_areas = get_areas_from_db()
    if db_areas:
        return db_areas
    
    # DBにない場合はAPIから取得
    data = get_json(AREA_JSON_URL)
    offices = data.get("offices", {})
    areas = [{"code": c, "name": info.get("name")} for c, info in offices.items()]
    areas.sort(key=lambda x: x["code"])
    
    # DBに保存
    save_areas_to_db(areas)
    return areas

def fetch_forecast(code: str):
    """APIから天気予報を取得し、DBにも保存する"""
    # APIからデータを取得
    payload = get_json(f"{FORECAST_BASE}{code}.json")
    result = {"publishingOffice": None, "reportDatetime": None, "weekly": [], "weekly_temps": []}
    
    if len(payload) > 0:
        result["publishingOffice"] = payload[0].get("publishingOffice")
        result["reportDatetime"] = payload[0].get("reportDatetime")
    
    if len(payload) > 1:
        tsw = payload[1].get("timeSeries", [])
        if len(tsw) > 0:
            tdefs = tsw[0].get("timeDefines", [])
            areas = tsw[0].get("areas", [])
            if areas:
                wcodes = areas[0].get("weatherCodes", [])
                for i, dt in enumerate(tdefs):
                    result["weekly"].append({"dateTime": dt, "weatherCode": wcodes[i] if i < len(wcodes) else ""})
        
        if len(tsw) > 1:
            tdefs = tsw[1].get("timeDefines", [])
            areas = tsw[1].get("areas", [])
            if areas:
                mins = areas[0].get("tempsMin", [])
                maxs = areas[0].get("tempsMax", [])
                for i, dt in enumerate(tdefs):
                    result["weekly_temps"].append({
                        "dateTime": dt,
                        "min": mins[i] if i < len(mins) else None,
                        "max": maxs[i] if i < len(maxs) else None
                    })
    
    # DBに保存
    save_forecast_to_db(code, result)
    return result

# ---------------------------------------------
# ローディング
# ---------------------------------------------
def show_loading(page: ft.Page):
    page.overlay.clear()
    page.overlay.append(
        ft.Container(
            content=ft.Column(controls=[ft.ProgressRing(color=ft.Colors.WHITE)],
                              alignment=ft.MainAxisAlignment.CENTER,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.BLACK),
            alignment=ft.alignment.center,
            expand=True,
        )
    )
    page.update()

def hide_loading(page: ft.Page):
    page.overlay.clear()
    page.update()

# ---------------------------------------------
# 日付選択ダイアログ
# ---------------------------------------------
def show_date_picker_dialog(page: ft.Page, on_select):
    """日付選択ダイアログを表示する"""
    date_picker = ft.DatePicker(
        first_date=datetime.now() - timedelta(days=365),  # 1年前から
        last_date=datetime.now(),                        # 今日まで
        on_change=lambda e: on_select(e.date.strftime("%Y-%m-%d")),
    )
    page.overlay.append(date_picker)
    date_picker.open = True
    page.update()

# ---------------------------------------------
# UI
# ---------------------------------------------
def make_week_card(date_text: str, icon_control: ft.Control, telop: str, min_temp: str = "", max_temp: str = "") -> ft.Container:
    temp_row = ft.Row(controls=[ft.Text(min_temp, color=ft.Colors.BLUE, weight=ft.FontWeight.BOLD),
                                ft.Text(" / "),
                                ft.Text(max_temp, color=ft.Colors.RED, weight=ft.FontWeight.BOLD)],
                      alignment=ft.MainAxisAlignment.CENTER)
    return ft.Container(
        bgcolor=ft.Colors.WHITE, border_radius=12, padding=12, margin=4,
        shadow=ft.BoxShadow(blur_radius=6, spread_radius=0, color=ft.Colors.with_opacity(0.20, ft.Colors.BLACK)),
        content=ft.Column(controls=[ft.Text(date_text, weight=ft.FontWeight.BOLD),
                                    ft.Container(content=icon_control, alignment=ft.alignment.center),
                                    ft.Text(telop, text_align=ft.TextAlign.CENTER),
                                    temp_row],
                         horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
        width=220, height=180
    )

# ---------------------------------------------
# 地方グループ（見出しを「〇〇地方」にする）
# ---------------------------------------------
# 先頭2桁コード -> 地方名
REGION_PREFIX_GROUPS = {
    "北海道地方": {"01"},
    "東北地方": {"02","03","04","05","06","07"},
    "関東甲信地方": {"08","09","10","11","12","13","14","19","20"},
    "北陸地方": {"16","17","18"},
    "東海地方": {"21","22","23"},
    "近畿地方": {"24","25","26","27","28","29","30"},
    "中国地方": {"31","32","33","34","35"},
    "四国地方": {"36","37","38","39"},
    "九州地方": {"40","41","42","43","44","45","46"},
    "沖縄地方": {"47"},
}
REGION_ORDER = [
    "北海道地方","東北地方","関東甲信地方","北陸地方","東海地方",
    "近畿地方","中国地方","四国地方","九州地方","沖縄地方"
]
def region_name_for_prefix(prefix: str) -> str:
    for region, prefixes in REGION_PREFIX_GROUPS.items():
        if prefix in prefixes:
            return region
    return f"その他（{prefix}xx）"

# ---------------------------------------------
# メイン
# ---------------------------------------------
def main(page: ft.Page):
    page.title = "天気予報アプリ"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window.width = 1100
    page.window.height = 700
    page.window.min_width = 1100
    page.window.min_height = 700
    page.window.center()
    page.update()
    page.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.BLUE_GREY)

    # データベース初期化
    init_database()

    # 現在選択中のエリアコードと名前
    current_area_code = None
    current_area_name = None
    
    appbar = ft.Container(
        bgcolor=ft.Colors.DEEP_PURPLE_800, padding=16,
        content=ft.Row(controls=[ft.Text("天気予報", color=ft.Colors.WHITE, size=20, weight=ft.FontWeight.BOLD)], spacing=8)
    )
    page.add(appbar)

    area_list_view = ft.ListView(expand=True, spacing=4, padding=8, auto_scroll=False)
    sidebar = ft.Container(
        bgcolor=ft.Colors.BLUE_GREY_700, width=300, padding=12,
        content=ft.Column(controls=[ft.Text("地域を選択", color=ft.Colors.WHITE, size=16, weight=ft.FontWeight.BOLD),
                                    ft.Divider(color=ft.Colors.BLUE_GREY_400),
                                    area_list_view],
                         spacing=8, expand=True)
    )

    cards_grid = ft.GridView(runs_count=4, spacing=16, run_spacing=16, expand=True)
    subtitle = ft.Text("", color=ft.Colors.BLUE_GREY_700, size=12)
    
    # 日付選択ボタン
    date_button = ft.ElevatedButton(
        text="日付を選択",
        icon=ft.Icons.CALENDAR_TODAY,
        visible=False
    )
    
    # 現在表示中の日付テキスト
    current_date_text = ft.Text("", size=14, color=ft.Colors.BLUE_GREY_700)
    
    # 最新データ取得ボタン
    refresh_button = ft.ElevatedButton(
        text="最新の天気を取得",
        visible=False
    )
    
    # 過去1週間分のデータ表示ボタン
    last_week_button = ft.ElevatedButton(
        text="過去1週間の予報履歴",
        visible=False
    )
    
    # コントロール行
    controls_row = ft.Row([
        date_button,
        current_date_text,
        refresh_button,
        last_week_button
    ], alignment=ft.MainAxisAlignment.START, spacing=10)
    
    right_panel = ft.Container(
        expand=True, padding=16, bgcolor=ft.Colors.BLUE_GREY_100,
        content=ft.Column(controls=[
            ft.Text("週間予報", size=18, weight=ft.FontWeight.BOLD),
            subtitle,
            controls_row,
            ft.Container(content=cards_grid, expand=True)
        ], spacing=10, expand=True)
    )

    root = ft.Row(controls=[sidebar, right_panel], expand=True)
    page.add(root)

    def on_date_selected(selected_date):
        """カレンダーから日付が選択されたときのハンドラ"""
        if not current_area_code or not current_area_name:
            return
            
        # 選択された日付の予報を表示
        render_week_from_db(current_area_code, current_area_name, selected_date)
        
        # 選択された日付を表示
        try:
            dt = datetime.fromisoformat(selected_date)
            display_date = dt.strftime(f"%Y年%m月%d日（{WEEKDAYS_JP[dt.weekday()]}）の予報")
        except:
            display_date = f"{selected_date}の予報"
        
        current_date_text.value = display_date
        page.update()
    
    def show_last_week_forecasts(e):
        """過去1週間の予報履歴を表示するハンドラ"""
        if not current_area_code or not current_area_name:
            return
            
        show_loading(page)
        
        # 過去1週間の日付リスト
        dates = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7, 0, -1)]
        
        # 予報データを格納するリスト
        forecasts = []
        
        # 各日付についてDBから予報データを取得
        for date in dates:
            data = get_forecast_from_db(current_area_code, date)
            if data["reportDatetime"]:
                try:
                    display_date = datetime.fromisoformat(date).strftime(f"%m/%d（{WEEKDAYS_JP[datetime.fromisoformat(date).weekday()]}）")
                except:
                    display_date = date
                    
                forecasts.append({
                    "date": display_date,
                    "data": data
                })
        
        hide_loading(page)
        
        if not forecasts:
            page.snack_bar = ft.SnackBar(ft.Text("過去1週間の予報データがありません"))
            page.snack_bar.open = True
            page.update()
            return
            
        # 過去1週間の予報を表示するダイアログ
        dlg = ft.AlertDialog(
            title=ft.Text(f"{current_area_name}の過去1週間の予報履歴"),
            content=ft.ListView(
                controls=[
                    ft.ListTile(
                        title=ft.Text(f"{forecast['date']}"),
                        subtitle=ft.Text(
                            f"発表: {datetime.fromisoformat(forecast['data']['reportDatetime'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')}"
                        ),
                        on_click=lambda e, date=forecast['data']['reportDatetime'][:10]: on_date_selected(date)
                    )
                    for forecast in forecasts
                ],
                height=300,
                width=400
            ),
            actions=[
                ft.TextButton("閉じる", on_click=lambda e: close_dialog())
            ]
        )
        
        def close_dialog():
            dlg.open = False
            page.update()
        
        page.dialog = dlg
        dlg.open = True
        page.update()

    def render_week_from_db(code, name, report_date=None):
        """DBから天気予報データを取得して表示する"""
        nonlocal current_area_code, current_area_name
        
        if not code:
            return
        
        show_loading(page)
        current_area_code = code
        current_area_name = name
        
        try:
            # DBからデータを取得
            data = get_forecast_from_db(code, report_date)
            
            # データがない場合はAPIから取得
            if not data["reportDatetime"]:
                data = fetch_forecast(code)
        except Exception as e:
            hide_loading(page)
            page.snack_bar = ft.SnackBar(ft.Text(f"取得エラー: {e}"))
            page.snack_bar.open = True
            page.update()
            return
        
        # カードグリッドを更新
        update_forecast_cards(data, name, code)
        hide_loading(page)
        
        # 日付選択ボタンと過去1週間ボタンを更新
        update_date_controls(code)

    def render_week_from_api(code, name):
        """APIから最新の天気予報データを取得して表示する"""
        nonlocal current_area_code, current_area_name
        
        if not code:
            return
        
        show_loading(page)
        current_area_code = code
        current_area_name = name
        
        try:
            # APIから最新データを取得
            data = fetch_forecast(code)
        except Exception as e:
            hide_loading(page)
            page.snack_bar = ft.SnackBar(ft.Text(f"取得エラー: {e}"))
            page.snack_bar.open = True
            page.update()
            return
        
        # カードグリッドを更新
        update_forecast_cards(data, name, code)
        hide_loading(page)
        
        # 日付選択ボタンと過去1週間ボタンを更新
        update_date_controls(code)

    def update_forecast_cards(data, name, code):
        """天気予報カードを更新する"""
        cards_grid.controls.clear()
        
        head_dt = ""
        if data["reportDatetime"]:
            try:
                head_dt = datetime.fromisoformat(data["reportDatetime"].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M発表")
            except Exception:
                head_dt = data["reportDatetime"]
        
        right_panel.content.controls[0] = ft.Text(f"{name}（{code}）の週間予報", size=18, weight=ft.FontWeight.BOLD)
        subtitle.value = head_dt
        
        # 表示中の日付を更新
        if data["reportDatetime"]:
            try:
                dt = datetime.fromisoformat(data["reportDatetime"][:10])
                display_date = dt.strftime(f"%Y年%m月%d日（{WEEKDAYS_JP[dt.weekday()]}）の予報")
                current_date_text.value = display_date
            except:
                current_date_text.value = data["reportDatetime"][:10] + "の予報"
        
        # 温度データのマッピング
        temp_map = {t["dateTime"]: (t["min"], t["max"]) for t in data["weekly_temps"]}
        
        for d in data["weekly"]:
            date_label = to_date_label_with_weekday(d["dateTime"])
            telop = d.get("telop", "")
            
            # telopがない場合は天気コードから取得
            if not telop and "weatherCode" in d:
                try:
                    n = int(d["weatherCode"])
                    telop = TELOPS.get(n, "")
                except Exception:
                    telop = ""
            
            icon_ctrl = compose_icon_from_telop(telop)
            mn, mx = temp_map.get(d["dateTime"], (None, None))
            min_txt = f"{mn}°C" if mn is not None and mn != "" else ""
            max_txt = f"{mx}°C" if mx is not None and mx != "" else ""
            
            cards_grid.controls.append(make_week_card(date_label, icon_ctrl, telop, min_txt, max_txt))
        
        page.update()

    def update_date_controls(area_code):
        """日付選択の表示・非表示を切り替える"""
        # 利用可能な日付を取得
        dates = get_forecast_dates_for_area(area_code)
        
        if dates:
            date_button.visible = True
            last_week_button.visible = True
        else:
            date_button.visible = False
            last_week_button.visible = False
            current_date_text.value = ""
        
        # 更新ボタンを表示
        refresh_button.visible = True
        page.update()

    def load_areas():
        area_list_view.controls.clear()
        show_loading(page)
        
        try:
            # 地域一覧を取得（DBから→なければAPI）
            areas = fetch_area_list()
        except Exception as e:
            hide_loading(page)
            area_list_view.controls.append(ft.Text(f"地域一覧取得エラー: {e}", color=ft.Colors.RED_700))
            page.update()
            return

        # --- 〇〇地方でまとめる ---
        by_region = defaultdict(list)
        for a in areas:
            prefix = a["code"][:2]
            region = region_name_for_prefix(prefix)
            by_region[region].append(a)

        tiles = []
        for region in REGION_ORDER:
            items = sorted(by_region.get(region, []), key=lambda x: x["code"])
            if not items:
                continue
            buttons = [
                ft.TextButton(
                    text=f"{a['name']}  {a['code']}",
                    on_click=lambda e, c=a['code'], n=a['name']: render_week_from_db(c, n),
                    style=ft.ButtonStyle(color=ft.Colors.WHITE),
                )
                for a in items
            ]
            tiles.append(
                ft.ExpansionTile(
                    title=ft.Text(region, color=ft.Colors.WHITE),
                    subtitle=ft.Text("タップで展開", color=ft.Colors.BLUE_GREY_200),
                    controls=buttons
                )
            )

        area_list_view.controls.extend(tiles)
        page.update()
        hide_loading(page)

        # 初期表示は東京都（130000）
        render_week_from_db("130000", "東京都")

    # イベントハンドラの設定
    date_button.on_click = lambda e: show_date_picker_dialog(page, on_date_selected)
    refresh_button.on_click = lambda e: render_week_from_api(current_area_code, current_area_name)
    last_week_button.on_click = show_last_week_forecasts

    # アプリ起動
    load_areas()

ft.app(target=main)