from flask import Flask, render_template, jsonify, request, Response
import psycopg2
from functools import wraps  # Esto debe ir aquí arriba

app = Flask(__name__)

# Configuracion para conectarse a BD de PostgreSQL
conn = psycopg2.connect(
    dbname="park_uv",
    user="postgres",
    password="p",
    host="localhost",
    port="5432"
)

# === AUTENTICACIÓN BÁSICA ===
def check_auth(username, password):
    return username == 'admin' and password == '1234'

def authenticate():
    return Response(
        'No autorizado.\nNecesitas ingresar usuario y contraseña.', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    @wraps(f)  # evita el error "decorated"
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# === RUTAS ===
@app.route('/')
@requires_auth
def index():
    return render_template('index.html')

@app.route('/admin')
@requires_auth
def admin():
    return render_template('admin.html')

@app.route('/geojson')
@requires_auth
def geojson():
    cur = conn.cursor()
    query = """
        SELECT id, nombre AS "Nombre", capacidad AS "Capacidad", ocupacion AS "Ocupacion",
               ST_AsGeoJSON(geom)::json AS geometry
        FROM parqueadero_point_uv;
    """
    cur.execute(query)
    rows = cur.fetchall()

    features = []
    for row in rows:
        properties = {
            "id": row[0],
            "Nombre": row[1],
            "Capacidad": row[2],
            "Ocupacion": row[3]
        }
        geometry = row[4]
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": properties
        })

    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }

    return jsonify(geojson_data)

@app.route('/update', methods=['POST'])
@requires_auth
def guardar():
    try:
        data = request.get_json()

        cur = conn.cursor()

        for feature in data['features']:
            id_ = feature['properties']['id']
            ocupacion = feature['properties'].get('Ocupacion', 0)

            cur.execute("""
                UPDATE "parqueadero_point_uv"
                SET ocupacion = %s
                WHERE id = %s;
            """, (ocupacion, id_))

        conn.commit()
        return jsonify({"mensaje": "Datos actualizados correctamente."})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    
@app.route('/admin/data')
@requires_auth
def admin_data():
    cur = conn.cursor()
    cur.execute('SELECT id, nombre, capacidad, ocupacion FROM "parqueadero_point_uv";')
    rows = cur.fetchall()
    data = [{"id": r[0], "nombre": r[1], "capacidad": r[2], "ocupados": r[3], "lastUpdate": None} for r in rows]
    return jsonify(data)

@app.route('/admin/update', methods=['POST'])
@requires_auth
def update_parking():
    data = request.get_json()
    id = data.get('id')
    ocupados = data.get('ocupados')
    if id is None or ocupados is None:
        return jsonify({'status': 'error', 'message': 'Datos incompletos'}), 400
    try:
        cur = conn.cursor()
        cur.execute('UPDATE "parqueadero_point_uv" SET ocupacion = %s WHERE id = %s;', (ocupados, id))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
