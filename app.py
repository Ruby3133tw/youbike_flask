from flask import Flask, request, render_template_string
import requests
from collections import defaultdict

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>YouBike 2.0 查詢系統</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h2 { margin-top: 40px; border-bottom: 2px solid #333; padding-bottom: 5px; }
        table { border-collapse: collapse; width: 100%; margin-top: 10px; }
        th, td { border: 1px solid #ccc; padding: 8px; text-align: center; }
        th { cursor: pointer; background-color: #f2f2f2; }
        th:hover { background-color: #ddd; }
        form { margin-bottom: 15px; }
        input[type=text], select { padding: 5px; margin-right: 5px; }
        input[type=submit] { padding: 5px 10px; }
        .asc::after { content: " ▲"; }
        .desc::after { content: " ▼"; }
        #map { height: 500px; margin-top: 20px; border: 2px solid #ccc; }
    </style>
    <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
</head>
<body>
    <h1>🚲 台北 YouBike 2.0 站點查詢</h1>
    <form method="get" action="/">
        <label>行政區：</label>
        <select name="district">
            <option value="">-- 全部行政區 --</option>
            {% for d in districts %}
                <option value="{{ d }}" {% if d == selected_district %}selected{% endif %}>{{ d }}</option>
            {% endfor %}
        </select>
        <label>站點名稱或所在道路：</label>
        <input type="text" name="q" placeholder="例如 捷運科技大樓" value="{{ q|default('') }}">
        <input type="submit" value="搜尋">
        <input type="submit" name="clear" value="清除">
    </form>

    <div id="map"></div>

    {% if grouped_stations %}
        {% for area, stations in grouped_stations.items() %}
            <h2>{{ area }} (共 {{ stations|length }} 站)</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        {% for col, label in [('sna', '站點名稱'), ('sarea', '行政區'), ('available_rent_bikes', '可借車輛數'), ('available_return_bikes', '可還空位數')] %}
                            {% set cls = '' %}
                            {% if sort_by == col %}
                                {% set cls = 'asc' if order == 'asc' else 'desc' %}
                            {% endif %}
                            <th class="{{ cls }}">
                                <a href="?q={{ q|urlencode }}&district={{ selected_district|urlencode }}&sort_by={{ col }}&order={% if sort_by == col and order == 'asc' %}desc{% else %}asc{% endif %}">{{ label }}</a>
                            </th>
                        {% endfor %}
                        <th>地址</th>
                        <th>更新時間</th>
                    </tr>
                </thead>
                <tbody>
                    {% for i, s in stations %}
                    <tr>
                        <td>{{ i + 1 }}</td>
                        <td>{{ s.sna }}</td>
                        <td>{{ s.sarea }}</td>
                        <td style="color: {% if s.available_rent_bikes == 0 %}red{% elif s.available_rent_bikes <= 3 %}orange{% else %}black{% endif %}; font-weight: bold;">
                            {{ s.available_rent_bikes }}
                        </td>
                        <td>{{ s.available_return_bikes }}</td>
                        <td>{{ s.ar }}</td>
                        <td>{{ s.mday }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% endfor %}
    {% else %}
        <p>🔍 沒有找到符合條件的站點。</p>
    {% endif %}
    <p>📊 資料來源：台北市政府公開資料平台（YouBike 2.0 即時資料）</p>

    <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
    <script>
        const map = L.map('map').setView([25.0330, 121.5654], 13);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap',
        }).addTo(map);

        const stations = {{ map_stations | tojson }};
        const bounds = [];

        stations.forEach(s => {
            if (s.latitude && s.longitude) {
                const marker = L.marker([s.latitude, s.longitude]).addTo(map);
                marker.bindPopup(`<strong>${s.sna}</strong><br>📍 ${s.ar}<br>🚲 可借：${s.available_rent_bikes}，可還：${s.available_return_bikes}`);
                bounds.push([s.latitude, s.longitude]);
            }
        });

        if (bounds.length) {
            map.fitBounds(bounds);
        }
    </script>
</body>
</html>
'''


class Obj:
    def __init__(self, d): self.__dict__ = d

def sort_stations(data, key, order):
    return sorted(data, key=lambda x: x.get(key, ""), reverse=(order == 'desc'))

@app.route('/')
def index():
    q = request.args.get('q', '').strip()
    district = request.args.get('district', '').strip()
    sort_by = request.args.get('sort_by', 'sna')
    order = request.args.get('order', 'asc')

    url = "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json"
    resp = requests.get(url)
    stations = resp.json() if resp.status_code == 200 else []

    districts = sorted(set([s.get('sarea') for s in stations]))

    # 過濾條件
    if q:
        stations = [s for s in stations if
                    q.lower() in s.get('sna', '').lower() or
                    q.lower() in s.get('ar', '').lower()]

    if district:
        stations = [s for s in stations if s.get('sarea') == district]


    stations = sort_stations(stations, sort_by, order)

    grouped = defaultdict(list)
    for s in stations:
        grouped[s.get('sarea', '未知區')].append(s)

    grouped_stations = {}
    for area, items in grouped.items():
        grouped_stations[area] = list(enumerate([Obj(s) for s in items]))

    return render_template_string(
        HTML_TEMPLATE,
        grouped_stations=grouped_stations,
        map_stations=stations,
        q=q,
        districts=districts,
        selected_district=district,
        sort_by=sort_by,
        order=order
    )

import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
