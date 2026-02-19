from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import traceback

reservas_bp = Blueprint('reservas', __name__)

def get_db():
    return current_app.config['MONGO_DB']

@reservas_bp.route("/api/reservar", methods=["POST"])
def api_reservar():
    try:
        data = request.json
        db = get_db()
        
        # Validación de Fecha y Hora
        fecha_str = data.get("fecha")
        hora_str = data.get("hora") 
        if fecha_str and hora_str:
            try:
                fecha_hora_reserva_str = f"{fecha_str} {hora_str}"
                fecha_hora_reserva = datetime.strptime(fecha_hora_reserva_str, "%m/%d/%Y %I:%M %p")
                if fecha_hora_reserva < datetime.now():
                    return jsonify({"error": "No puedes reservar en el pasado."}), 400
            except ValueError:
                pass 

        id_reserva = int(datetime.now().timestamp())
        nueva_reserva = {
            "ID_Reserva": id_reserva,
            "Nombre": data.get("nombre", ""),
            "Conjunto": data.get("conjunto", ""),
            "Torre_Apto": data.get("torre_apto", ""),
            "Documento": data.get("documento", ""),
            "Celular": data.get("celular", ""),
            "Email": data.get("email", ""),
            "Servicio": data.get("servicio", ""),
            "Fecha_Reserva": data.get("fecha", ""),
            "Hora": data.get("hora", ""),
            "Fecha_Registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        db.reservas.insert_one(nueva_reserva)
        return jsonify({"mensaje": "Reserva Exitosa", "id": id_reserva})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@reservas_bp.route("/api/reservas", methods=["GET"])
def api_obtener_reservas():
    try:
        fecha_filtro = request.args.get('fecha')
        db = get_db()
        query = {}
        
        if fecha_filtro:
            try:
                dt_obj = datetime.strptime(fecha_filtro, '%Y-%m-%d')
                query['Fecha_Reserva'] = dt_obj.strftime('%m/%d/%Y')
            except ValueError:
                pass
        
        reservas_lista = list(db.reservas.find(query, {'_id': 0}))
        
        def parse_datetime(row):
            try:
                str_dt = f"{row.get('Fecha_Reserva', '')} {row.get('Hora', '')}"
                return datetime.strptime(str_dt, "%m/%d/%Y %I:%M %p")
            except:
                return datetime.max 
                
        reservas_lista.sort(key=parse_datetime)
        return jsonify(reservas_lista)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@reservas_bp.route("/api/editar_reserva", methods=["POST"])
def api_editar_reserva():
    try:
        data = request.json
        res_id = int(data.get("ID_Reserva"))
        db = get_db()
        
        campos = ["Nombre", "Conjunto", "Torre_Apto", "Documento", "Celular", "Email", "Servicio", "Fecha_Reserva", "Hora"]
        campos_a_actualizar = {c: data[c] for c in campos if c in data}
        
        resultado = db.reservas.update_one({"ID_Reserva": res_id}, {"$set": campos_a_actualizar})
        
        if resultado.matched_count == 0:
            return jsonify({"error": "No encontrada"}), 404
            
        return jsonify({"mensaje": "Actualizado"})
    except Exception as e: 
        return jsonify({"error": str(e)}), 500

@reservas_bp.route("/api/borrar_reserva", methods=["POST"])
def api_borrar_reserva():
    try:
        res_id = int(request.json.get("ID_Reserva"))
        get_db().reservas.delete_one({"ID_Reserva": res_id})
        return jsonify({"mensaje": "Eliminado"})
    except Exception as e: 
        return jsonify({"error": str(e)}), 500