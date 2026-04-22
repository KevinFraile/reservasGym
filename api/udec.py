import traceback
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies, jwt_required
from werkzeug.security import check_password_hash

udec_bp = Blueprint('udec', __name__)

# Función auxiliar para llamar a la BD de UDEC
def get_udec_db():
    return current_app.config['MONGO_UDEC']

# ==========================================
# 1. SISTEMA DE AUTENTICACIÓN (ADMIN)
# ==========================================

@udec_bp.route("/api/udec/login", methods=["POST"])
def udec_login():
    try:
        data = request.json
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"error": "Faltan credenciales"}), 400

        db = get_udec_db()
        usuario = db.usuarios.find_one({"username": username})

        if usuario and check_password_hash(usuario["password"], password):
            access_token = create_access_token(
                identity=username,
                additional_claims={"db": "udec"},
                expires_delta=timedelta(hours=8)
            )
            # ← ya no usamos cookies, devolvemos el token en el body
            return jsonify({
                "mensaje": "Login exitoso",
                "usuario": username,
                "rol": usuario.get("rol", "admin"),
                "access_token": access_token        # ← nuevo
            }), 200

        return jsonify({"error": "Usuario o contraseña incorrectos"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@udec_bp.route("/api/udec/logout", methods=["POST"])
def udec_logout():
    # Con headers el logout es solo del lado del cliente (borra el token)
    return jsonify({"mensaje": "Sesión cerrada"}), 200


# ==========================================
# 2. CRUD DE EVENTOS
# ==========================================

@udec_bp.route("/api/udec/eventos", methods=["GET"])
def obtener_eventos():
    try:
        db = get_udec_db()
        eventos = list(db.eventos.find({}, {"_id": 0}).sort("id", -1))
        return jsonify(eventos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@udec_bp.route("/api/udec/eventos", methods=["POST"])
@jwt_required() 
def guardar_evento():
    try:
        db = get_udec_db()
        data = request.json
        
        if not data.get("id"):
            data["id"] = int(datetime.now().timestamp())
        else:
            data["id"] = int(data["id"])

        db.eventos.update_one({"id": data["id"]}, {"$set": data}, upsert=True)
        return jsonify({"mensaje": "Evento guardado", "id": data["id"]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@udec_bp.route("/api/udec/eventos/<int:evento_id>", methods=["DELETE"])
@jwt_required()
def borrar_evento(evento_id):
    try:
        db = get_udec_db()
        resultado = db.eventos.delete_one({"id": evento_id})
        if resultado.deleted_count > 0:
            db.inscritos.delete_many({"evento_id": evento_id})
            return jsonify({"mensaje": "Evento eliminado"}), 200
        return jsonify({"error": "Evento no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 3. GESTIÓN DEL AVISO PRINCIPAL
# ==========================================

@udec_bp.route("/api/udec/aviso", methods=["GET"])
def obtener_aviso():
    try:
        db = get_udec_db()
        aviso = db.avisos.find_one({"identificador": "aviso_inicio"}, {"_id": 0})
        if not aviso:
            aviso = {"titulo": "Bienvenido", "desc": "Avisos importantes."}
        return jsonify(aviso), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@udec_bp.route("/api/udec/aviso", methods=["POST"])
@jwt_required()
def actualizar_aviso():
    try:
        db = get_udec_db()
        data = request.json
        nuevo_aviso = {
            "titulo": data.get("titulo", ""),
            "desc": data.get("desc", ""),
            "identificador": "aviso_inicio"
        }
        db.avisos.update_one({"identificador": "aviso_inicio"}, {"$set": nuevo_aviso}, upsert=True)
        return jsonify({"mensaje": "Aviso actualizado"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 4. INSCRIPCIONES
# ==========================================

@udec_bp.route("/api/udec/eventos/<int:evento_id>/inscribir", methods=["POST"])
def inscribir_usuario(evento_id):
    try:
        db = get_udec_db()
        data = request.json
        
        cedula = str(data.get("cedula"))
        
        existe = db.inscritos.find_one({"evento_id": evento_id, "cedula": cedula})
        if existe:
            return jsonify({"error": "Esta cédula ya está registrada para este evento."}), 400

        nueva_inscripcion = {
            "evento_id": evento_id,
            "rol": data.get("rol"),
            "cedula": cedula,
            "nombre": data.get("nombre"),
            "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        db.inscritos.insert_one(nueva_inscripcion)
        return jsonify({"mensaje": "¡Inscripción exitosa!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@udec_bp.route("/api/udec/inscripciones/buscar/<string:cedula>", methods=["GET"])
def buscar_mis_inscripciones(cedula):
    try:
        db = get_udec_db()
        mis_registros = list(db.inscritos.find({"cedula": cedula}, {"_id": 0, "evento_id": 1}))
        
        if not mis_registros:
            return jsonify([]), 200 
            
        eventos_ids = [reg["evento_id"] for reg in mis_registros]
        mis_eventos = list(db.eventos.find({"id": {"$in": eventos_ids}}, {"_id": 0}))
        
        return jsonify(mis_eventos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@udec_bp.route("/api/udec/eventos/<int:evento_id>/inscritos", methods=["GET"])
@jwt_required()
def obtener_inscritos_admin(evento_id):
    try:
        db = get_udec_db()
        inscritos = list(db.inscritos.find({"evento_id": evento_id}, {"_id": 0}))
        return jsonify(inscritos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
    
    
    
    
# ==========================================
# RUTA TEMPORAL: CREAR PRIMER ADMIN
# ¡Ojo: Comenta esta ruta después de usarla!
# ==========================================
from werkzeug.security import generate_password_hash

@udec_bp.route("/api/udec/crear_admin_secreto", methods=["GET"])
def crear_admin_udec():
    try:
        db = get_udec_db()
        
        # Verificamos si ya existe el nuevo usuario
        if db.usuarios.find_one({"username": "admin_simposio"}):
            return jsonify({"mensaje": "El usuario 'admin_simposio' ya existe en UDEC."}), 200

        # Creamos el usuario con la nueva clave robusta
        nuevo_usuario = {
            "username": "admin_simposio",
            "password": generate_password_hash("Udec@Simp0si0_2026*"), 
            "rol": "admin"
        }
        
        db.usuarios.insert_one(nuevo_usuario)
        return jsonify({"mensaje": "Usuario admin_simposio creado con éxito."}), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500