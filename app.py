import traceback
from datetime import datetime, timedelta
import pandas as pd
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, set_access_cookies, unset_jwt_cookies
from werkzeug.security import generate_password_hash, check_password_hash

# Importamos el Blueprint de reservas
from api.reservas import reservas_bp

app = Flask(__name__)

# --- CONFIGURACIÓN DE MONGODB ATLAS ---
# Tu URI corregida (Creará la BD 'sebas_gym_db' automáticamente)
app.config["MONGO_URI"] = "mongodb+srv://gymSebas:YupRj1PBDYgMvoCP@cluster0.qwhsnns.mongodb.net/sebas_gym_db?appName=Cluster0"
mongo = PyMongo(app)
app.config['MONGO_DB'] = mongo.db

# --- CONFIGURACIÓN DE SEGURIDAD (JWT) ---
app.config["JWT_SECRET_KEY"] = "super-secreta-sebas-gym-2026" # Cambia esto si lo subes a producción
app.config["JWT_TOKEN_LOCATION"] = ["cookies"] # Usamos cookies para mayor seguridad
app.config["JWT_COOKIE_CSRF_PROTECT"] = False # Apagado temporalmente para facilitar el desarrollo
jwt = JWTManager(app)

# Registramos el Blueprint
app.register_blueprint(reservas_bp)

# --- SISTEMA DE LOGIN SEGURO CON MONGODB ---

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json
    usuario_recibido = data.get("username")
    password_recibida = data.get("password")

    if not usuario_recibido or not password_recibida:
        return jsonify({"error": "Faltan datos"}), 400

    db = app.config['MONGO_DB']
    
    # Buscamos el usuario en la colección 'usuarios'
    usuario_bd = db.usuarios.find_one({"username": usuario_recibido})

    # Verificamos si existe y si la contraseña (hasheada) coincide
    if usuario_bd and check_password_hash(usuario_bd["password"], password_recibida):
        # Login exitoso
        access_token = create_access_token(identity=usuario_recibido, expires_delta=timedelta(hours=8))
        resp = jsonify({"mensaje": "Login exitoso"})
        set_access_cookies(resp, access_token)
        return resp, 200
    
    # Si algo falla
    return jsonify({"error": "Credenciales inválidas"}), 401

@app.route("/api/logout", methods=["POST"])
def api_logout():
    resp = jsonify({"mensaje": "Logout exitoso"})
    unset_jwt_cookies(resp) # Borra la cookie del navegador
    return resp, 200


# # --- RUTA TEMPORAL PARA CREAR EL PRIMER ADMIN ---
# # ¡OJO: Comenta esta ruta después de usarla una vez (con el símbolo # al inicio de cada línea)!
# @app.route("/api/crear_admin_secreto")
# def crear_admin_secreto():
#     db = app.config['MONGO_DB']
    
#     # Verificamos si ya existe para no duplicarlo
#     if db.usuarios.find_one({"username": "admin"}):
#         return "El usuario 'admin' ya existe."

#     # Creamos el usuario con la contraseña hasheada
#     nuevo_usuario = {
#         "username": "admin",
#         "password": generate_password_hash("sebas123"), # Aquí encriptamos la clave
#         "rol": "administrador"
#     }
    
#     db.usuarios.insert_one(nuevo_usuario)
#     return "Usuario admin creado con éxito en MongoDB."
# # ------------------------------------------------


# --- RUTAS DE VISTAS (HTML) ---
@app.route("/")
def index(): 
    return render_template("index.html")

@app.route('/inventario')
@jwt_required() # <-- BLOQUEA EL ACCESO SI NO ESTÁ LOGUEADO
def inventario():
    return render_template('inventario.html')

# --- API INVENTARIO (Ahora con MongoDB) ---
@app.route("/api/inventario", methods=["GET", "POST"])
@jwt_required()
def api_inventario():
    try:
        db = app.config['MONGO_DB']
        if request.method == "POST":
            data = request.json
            
            # 1. Asegurarnos de que el ID sea un entero
            if not data.get("ID"):
                data["ID"] = int(datetime.now().timestamp())
            else:
                data["ID"] = int(data["ID"])
            
            # 2. FIX: Convertir explícitamente a números (Float/Int) antes de guardar
            data["Cantidad"] = float(data.get("Cantidad", 0))
            data["Costo_Compra"] = float(data.get("Costo_Compra", 0))
            data["Precio_Venta_Sugerido"] = float(data.get("Precio_Venta_Sugerido", 0))
            
            # Actualiza si existe, si no, lo crea (upsert=True)
            db.productos.update_one({"ID": data["ID"]}, {"$set": data}, upsert=True)
            return jsonify({"mensaje": "Guardado"})
        
        # GET: Retornar lista de productos
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

# --- API VENTAS (Ahora con MongoDB) ---
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

        # 1. Validación de Stock en BD
        for item in carrito:
            prod_bd = db.productos.find_one({"ID": int(item['ID_Producto'])})
            if not prod_bd: return jsonify({"error": f"Producto ID {item['ID_Producto']} no existe"}), 404
            if float(prod_bd.get('Cantidad', 0)) < float(item['Cantidad']):
                return jsonify({"error": f"Stock insuficiente para '{prod_bd['Producto']}'"}), 400

        # 2. Procesamiento y Resta de Stock
        for index, item in enumerate(carrito):
            prod_bd = db.productos.find_one({"ID": int(item['ID_Producto'])})
            cant = float(item['Cantidad'])
            precio_unit = float(item['Precio_Venta_Real'])
            costo = float(prod_bd.get('Costo_Compra', 0))
            
            # Restar stock
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

        # 3. Guardar ventas
        db.ventas.insert_many(nuevas_ventas)
        
        return jsonify({
            "mensaje": "Venta Exitosa", 
            "ticket_ref": ticket_ref,
            "items": nuevas_ventas,
            "total_global": sum(v['Total_Venta'] for v in nuevas_ventas)
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/borrar_venta", methods=["POST"])
@jwt_required()
def api_borrar_venta():
    try:
        vid = int(request.json.get("ID_Venta"))
        db = app.config['MONGO_DB']
        venta = db.ventas.find_one({"ID_Venta": vid})
        
        if venta:
            # Devolver stock
            db.productos.update_one({"ID": venta['ID_Producto']}, {"$inc": {"Cantidad": venta['Cantidad']}})
            # Borrar venta
            db.ventas.delete_one({"ID_Venta": vid})
            
        return jsonify({"mensaje": "Eliminada"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/api/reportes")
@jwt_required()
def reportes():
    try:
        db = app.config['MONGO_DB']
        fi = request.args.get('fecha_inicio')
        ff = request.args.get('fecha_fin')

        productos = list(db.productos.find({}, {"_id": 0}))
        ventas = list(db.ventas.find({}, {"_id": 0}))
        
        df_p = pd.DataFrame(productos) if productos else pd.DataFrame()
        df_v = pd.DataFrame(ventas) if ventas else pd.DataFrame()
        
        res = { 
            "total_ingresos": 0, "total_ganancia": 0, "ventas_totales": 0, 
            "top_productos": [], "valor_inventario": 0,
            "grafica_fechas": [], "grafica_valores": [] 
        }
        
        if not df_p.empty:
            df_p['Cantidad'] = pd.to_numeric(df_p['Cantidad'], errors='coerce').fillna(0)
            df_p['Costo_Compra'] = pd.to_numeric(df_p['Costo_Compra'], errors='coerce').fillna(0)
            res["valor_inventario"] = float((df_p["Cantidad"] * df_p["Costo_Compra"]).sum())
            
        if not df_v.empty:
            df_v['Total_Venta'] = pd.to_numeric(df_v['Total_Venta'], errors='coerce').fillna(0)
            df_v['Ganancia'] = pd.to_numeric(df_v['Ganancia'], errors='coerce').fillna(0)
            df_v['Cantidad'] = pd.to_numeric(df_v['Cantidad'], errors='coerce').fillna(0)
            df_v['Fecha_dt'] = pd.to_datetime(df_v['Fecha'], errors='coerce')
            
            if fi: df_v = df_v[df_v['Fecha_dt'] >= pd.to_datetime(fi)]
            if ff: df_v = df_v[df_v['Fecha_dt'] <= pd.to_datetime(ff) + timedelta(days=1) - timedelta(seconds=1)]

            res["total_ingresos"] = float(df_v["Total_Venta"].sum())
            res["total_ganancia"] = float(df_v["Ganancia"].sum())
            res["ventas_totales"] = int(len(df_v))
            
            df_v['Dia'] = df_v['Fecha_dt'].dt.strftime('%Y-%m-%d')
            ventas_por_dia = df_v.groupby('Dia')['Total_Venta'].sum().reset_index().sort_values('Dia')
            res["grafica_fechas"] = ventas_por_dia['Dia'].tolist()
            res["grafica_valores"] = ventas_por_dia['Total_Venta'].tolist()

            top = df_v.groupby("Producto")["Cantidad"].sum().sort_values(ascending=False).head(5).reset_index()
            top_dict = top.to_dict(orient="records")
            for item in top_dict:
                prod_row = df_p[df_p["Producto"] == item["Producto"]] if not df_p.empty else pd.DataFrame()
                item["Imagen"] = str(prod_row.iloc[0].get("Imagen", "")) if not prod_row.empty else ""
            res["top_productos"] = top_dict
            
        return jsonify(res)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=8000)