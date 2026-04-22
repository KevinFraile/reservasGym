import traceback
from datetime import datetime, timedelta
import pandas as pd
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, set_access_cookies, unset_jwt_cookies
from werkzeug.security import generate_password_hash, check_password_hash

# 1. IMPORTAMOS CORS
from flask_cors import CORS 

from api.reservas import reservas_bp
from api.udec import udec_bp 

app = Flask(__name__)

# 2. HABILITAMOS CORS (Súper importante para los puertos de Ionic/Angular)
# supports_credentials=True es obligatorio para que funcionen las cookies del JWT
CORS(app, supports_credentials=True, origins=["http://localhost:8100", "http://127.0.0.1:8100", "http://localhost:4200", "https://berracodev.com", "http://localhost", "ionic://localhost"])
# --- CONFIGURACIÓN DE SEGURIDAD (JWT) ---
app.config["JWT_SECRET_KEY"] = "NSEQPNER817N84H**f.DSF45W--ASAFF-SD4234FIRMA:KEVINFC"
app.config["JWT_TOKEN_LOCATION"] = ["headers"]   # ← cambio clave: lee el header
app.config["JWT_COOKIE_CSRF_PROTECT"] = False
jwt = JWTManager(app)

# ... (el resto de tu código de las bases de datos y registros sigue exactamente igual hacia abajo)

# --- CONFIGURACIÓN DE MONGODB ATLAS (DOBLE CONEXIÓN) ---

# Conexión 1: Sebas Gym (y Reservas)
app.config["MONGO_URI_GYM"] = "mongodb+srv://gymSebas:YupRj1PBDYgMvoCP@cluster0.qwhsnns.mongodb.net/sebas_gym_db?appName=Cluster0"
mongo_gym = PyMongo(app, uri=app.config["MONGO_URI_GYM"])
app.config['MONGO_DB'] = mongo_gym.db  # Reservas y Gym usarán esta

# Conexión 2: UDEC Eventos
app.config["MONGO_URI_UDEC"] = "mongodb+srv://gymSebas:YupRj1PBDYgMvoCP@cluster0.qwhsnns.mongodb.net/udec_eventos?appName=Cluster0"
mongo_udec = PyMongo(app, uri=app.config["MONGO_URI_UDEC"])
app.config['MONGO_UDEC'] = mongo_udec.db # UDEC usará esta

# --- REGISTRO DE BLUEPRINTS ---
app.register_blueprint(reservas_bp)
app.register_blueprint(udec_bp)

# --- SISTEMA DE LOGIN (SEBAS GYM) ---
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json
    usuario_recibido = data.get("username")
    password_recibida = data.get("password")

    if not usuario_recibido or not password_recibida:
        return jsonify({"error": "Faltan datos"}), 400

    db = app.config['MONGO_DB']
    usuario_bd = db.usuarios.find_one({"username": usuario_recibido})

    if usuario_bd and check_password_hash(usuario_bd["password"], password_recibida):
        access_token = create_access_token(identity=usuario_recibido, expires_delta=timedelta(hours=8))
        resp = jsonify({"mensaje": "Login exitoso"})
        set_access_cookies(resp, access_token)
        return resp, 200
    
    return jsonify({"error": "Credenciales inválidas"}), 401

@app.route("/api/logout", methods=["POST"])
def api_logout():
    resp = jsonify({"mensaje": "Logout exitoso"})
    unset_jwt_cookies(resp)
    return resp, 200

# --- RUTAS DE VISTAS ---
@app.route("/")
def index(): 
    return render_template("index.html")

@app.route('/inventario')
@jwt_required()
def inventario():
    return render_template('inventario.html')

# --- API INVENTARIO (SEBAS GYM) ---
@app.route("/api/inventario", methods=["GET", "POST"])
def api_inventario():
    try:
        db = app.config['MONGO_DB']
        if request.method == "POST":
            data = request.json
            data["ID"] = int(data.get("ID", datetime.now().timestamp()))
            data["Cantidad"] = float(data.get("Cantidad", 0))
            data["Costo_Compra"] = float(data.get("Costo_Compra", 0))
            data["Precio_Venta_Sugerido"] = float(data.get("Precio_Venta_Sugerido", 0))
            
            db.productos.update_one({"ID": data["ID"]}, {"$set": data}, upsert=True)
            return jsonify({"mensaje": "Guardado"})
        
        productos = list(db.productos.find({}, {"_id": 0}))
        return jsonify(productos)
    except Exception as e: 
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/borrar_producto", methods=["POST"])
@jwt_required()
def api_borrar_producto():
    try:
        pid = int(request.json.get("ID"))
        app.config['MONGO_DB'].productos.delete_one({"ID": pid})
        return jsonify({"mensaje": "Eliminado"})
    except Exception as e: return jsonify({"error": str(e)}), 500

# --- API VENTAS (SEBAS GYM) ---
@app.route("/api/ventas", methods=["GET"])
@jwt_required()
def api_ventas():
    try:
        ventas = list(app.config['MONGO_DB'].ventas.find({}, {"_id": 0}).sort("ID_Venta", -1))
        return jsonify(ventas)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/api/vender", methods=["POST"])
@jwt_required()
def api_vender():
    try:
        carrito = request.json.get('carrito', []) 
        cliente = request.json.get('cliente', '')
        direccion = request.json.get('direccion', '')
        if not carrito: return jsonify({"error": "El carrito está vacío"}), 400

        db = app.config['MONGO_DB']
        ticket_ref = int(datetime.now().timestamp()) 
        fecha_global = datetime.now().strftime("%Y-%m-%d %H:%M")
        nuevas_ventas = []

        for item in carrito:
            prod_bd = db.productos.find_one({"ID": int(item['ID_Producto'])})
            if not prod_bd: return jsonify({"error": f"Producto ID {item['ID_Producto']} no existe"}), 404
            if float(prod_bd.get('Cantidad', 0)) < float(item['Cantidad']):
                return jsonify({"error": f"Stock insuficiente para '{prod_bd['Producto']}'"}), 400

        for index, item in enumerate(carrito):
            prod_bd = db.productos.find_one({"ID": int(item['ID_Producto'])})
            cant = float(item['Cantidad'])
            precio_unit = float(item['Precio_Venta_Real'])
            costo = float(prod_bd.get('Costo_Compra', 0))
            
            db.productos.update_one({"ID": int(item['ID_Producto'])}, {"$inc": {"Cantidad": -cant}})
            
            nueva_venta = {
                "ID_Venta": int(datetime.now().timestamp() * 1000) + index,
                "Ticket_Ref": ticket_ref,
                "Fecha": fecha_global,
                "ID_Producto": int(item['ID_Producto']),
                "Producto": str(prod_bd['Producto']),
                "Cantidad": cant,
                "Precio_Venta_Real": precio_unit,
                "Total_Venta": precio_unit * cant,
                "Ganancia": (precio_unit - costo) * cant,
                "Cliente": str(cliente),
                "Direccion": str(direccion)
            }
            nuevas_ventas.append(nueva_venta)

        db.ventas.insert_many(nuevas_ventas)
        return jsonify({"mensaje": "Venta Exitosa", "ticket_ref": ticket_ref})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/reportes")
@jwt_required()
def reportes():
    try:
        db = app.config['MONGO_DB']
        productos = list(db.productos.find({}, {"_id": 0}))
        ventas = list(db.ventas.find({}, {"_id": 0}))
        
        df_p = pd.DataFrame(productos) if productos else pd.DataFrame()
        df_v = pd.DataFrame(ventas) if ventas else pd.DataFrame()
        
        res = { "total_ingresos": 0, "total_ganancia": 0, "ventas_totales": 0, "valor_inventario": 0 }
        
        if not df_p.empty:
            res["valor_inventario"] = float((df_p["Cantidad"].astype(float) * df_p["Costo_Compra"].astype(float)).sum())
            
        if not df_v.empty:
            res["total_ingresos"] = float(df_v["Total_Venta"].sum())
            res["total_ganancia"] = float(df_v["Ganancia"].sum())
            res["ventas_totales"] = int(len(df_v))
            
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=8080)