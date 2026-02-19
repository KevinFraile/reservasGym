from flask import Blueprint, request, jsonify
from datetime import datetime
import pandas as pd
import traceback
import sys
import os
import numpy as np

# Importamos las funciones compartidas desde db.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db import leer_datos, guardar_datos

reservas_bp = Blueprint('reservas', __name__)

# --- ENDPOINT PARA GUARDAR (POST) ---
@reservas_bp.route("/api/reservar", methods=["POST"])
def api_reservar():
    try:
        data = request.json
        
        # --- VALIDACIÓN DE FECHA Y HORA (NO PASADO) ---
        fecha_str = data.get("fecha") # Viene como MM/DD/YYYY
        hora_str = data.get("hora")   # Viene como HH:MM AM/PM
        
        if fecha_str and hora_str:
            try:
                # Construimos un objeto datetime con la fecha y hora de la reserva
                fecha_hora_reserva_str = f"{fecha_str} {hora_str}"
                fecha_hora_reserva = datetime.strptime(fecha_hora_reserva_str, "%m/%d/%Y %I:%M %p")
                
                # Obtenemos la fecha y hora actual
                ahora = datetime.now()
                
                # Comparamos
                if fecha_hora_reserva < ahora:
                    return jsonify({"error": "No puedes reservar en una fecha u hora anterior a la actual."}), 400
            except ValueError:
                # Si el formato de fecha/hora no es válido, dejamos pasar (o podrías retornar error)
                pass 
        # ---------------------------------------------

        df = leer_datos("Reservas")
        
        nueva_reserva = {
            "ID_Reserva": int(datetime.now().timestamp()),
            "Nombre": data.get("nombre"),
            "Conjunto": data.get("conjunto"),
            "Torre_Apto": data.get("torre_apto"),
            "Documento": data.get("documento"),
            "Celular": data.get("celular"),
            "Email": data.get("email"),
            "Servicio": data.get("servicio"),
            "Fecha_Reserva": data.get("fecha"), # Formato: MM/DD/YYYY
            "Hora": data.get("hora"),           # Formato: HH:MM AM/PM
            "Fecha_Registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        df = pd.concat([df, pd.DataFrame([nueva_reserva])], ignore_index=True)
        
        if not guardar_datos(df, "Reservas"): 
            return jsonify({"error": "Base de datos ocupada"}), 400
            
        return jsonify({"mensaje": "Reserva Exitosa", "id": nueva_reserva["ID_Reserva"]})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# --- ENDPOINT PARA CONSULTAR Y ORDENAR (GET) ---
@reservas_bp.route("/api/reservas", methods=["GET"])
def api_obtener_reservas():
    try:
        fecha_filtro = request.args.get('fecha') # Opcional (YYYY-MM-DD)
        df = leer_datos("Reservas")
        
        if df.empty: return jsonify([])

        # Limpiar nulos
        df = df.replace({np.nan: None})

        # 1. Crear columna temporal datetime para ordenar correctamente
        def parse_datetime(row):
            try:
                str_dt = f"{row['Fecha_Reserva']} {row['Hora']}"
                return datetime.strptime(str_dt, "%m/%d/%Y %I:%M %p")
            except:
                return datetime.max 

        df['_sort_key'] = df.apply(parse_datetime, axis=1)

        # 2. Ordenar: Mas cercano al inicio
        df = df.sort_values(by='_sort_key', ascending=True)

        # 3. Filtrar si el usuario pidió una fecha específica
        if fecha_filtro:
            try:
                dt_obj = datetime.strptime(fecha_filtro, '%Y-%m-%d')
                fecha_fmt = dt_obj.strftime('%m/%d/%Y')
                df = df[df['Fecha_Reserva'] == fecha_fmt]
            except:
                pass 

        # Eliminar la columna temporal antes de enviar
        df = df.drop(columns=['_sort_key'])

        return jsonify(df.to_dict(orient="records"))
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# --- ACTUALIZAR (POST) ---
@reservas_bp.route("/api/editar_reserva", methods=["POST"])
def api_editar_reserva():
    try:
        data = request.json
        res_id = int(data.get("ID_Reserva"))
        df = leer_datos("Reservas")
        idx = df[df['ID_Reserva'] == res_id].index
        if idx.empty: return jsonify({"error": "No encontrada"}), 404
        
        idx = idx[0]
        campos = ["Nombre", "Conjunto", "Torre_Apto", "Documento", "Celular", "Email", "Servicio", "Fecha_Reserva", "Hora"]
        for c in campos:
            if c in data: df.at[idx, c] = data[c]
            
        guardar_datos(df, "Reservas")
        return jsonify({"mensaje": "Actualizado"})
    except Exception as e: return jsonify({"error": str(e)}), 500

# --- BORRAR (POST) ---
@reservas_bp.route("/api/borrar_reserva", methods=["POST"])
def api_borrar_reserva():
    try:
        data = request.json
        df = leer_datos("Reservas")
        df = df[df['ID_Reserva'] != int(data.get("ID_Reserva"))]
        guardar_datos(df, "Reservas")
        return jsonify({"mensaje": "Eliminado"})
    except Exception as e: return jsonify({"error": str(e)}), 500