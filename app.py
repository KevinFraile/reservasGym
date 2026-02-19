import traceback
import pandas as pd
from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta

# Importamos la lógica compartida y el Blueprint
from db import asegurar_excel, leer_datos, guardar_datos
from api.reservas import reservas_bp  # <-- Importamos el archivo de la carpeta api

app = Flask(__name__)

# --- REGISTRAMOS EL BLUEPRINT DE RESERVAS ---
app.register_blueprint(reservas_bp)

# --- RUTAS DE VISTAS (HTML) ---
@app.route("/")
def index(): return render_template("index.html")

@app.route('/inventario')
def inventario():
    return render_template('inventario.html')

# --- API INVENTARIO (Se mantienen aquí o podrías moverlas a api/inventario.py en el futuro) ---
@app.route("/api/inventario", methods=["GET", "POST"])
def api_inventario():
    try:
        df = leer_datos("Productos")
        if request.method == "POST":
            data = request.json
            if not data.get("ID"): 
                data["ID"] = int(datetime.now().timestamp())
                df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
            else:
                idx = df[df['ID'] == int(data['ID'])].index
                if not idx.empty:
                    for k, v in data.items():
                        if k in df.columns: df.at[idx[0], k] = v
            if not guardar_datos(df, "Productos"): return jsonify({"error": "Excel abierto"}), 400
            return jsonify({"mensaje": "Guardado"})
        return jsonify(df.to_dict(orient="records"))
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/api/borrar_producto", methods=["POST"])
def api_borrar_producto():
    try:
        pid = int(request.json.get("ID"))
        df = leer_datos("Productos")
        df = df[df.ID != pid]
        guardar_datos(df, "Productos")
        return jsonify({"mensaje": "Eliminado"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/api/ventas", methods=["GET"])
def api_ventas():
    try:
        df = leer_datos("Ventas")
        if not df.empty: df = df.sort_values("ID_Venta", ascending=False)
        return jsonify(df.to_dict(orient="records"))
    except Exception as e: return jsonify({"error": str(e)}), 500

# --- VENTA MASIVA (CARRITO) ---
@app.route("/api/vender", methods=["POST"])
def api_vender():
    try:
        carrito = request.json.get('carrito', []) 
        cliente = request.json.get('cliente', '')
        direccion = request.json.get('direccion', '')
        
        if not carrito: return jsonify({"error": "El carrito está vacío"}), 400

        df_p = leer_datos("Productos")
        df_v = leer_datos("Ventas")
        
        ticket_ref = int(datetime.now().timestamp()) 
        fecha_global = datetime.now().strftime("%Y-%m-%d %H:%M")
        nuevas_ventas = []

        # 1. Validación de Stock
        for item in carrito:
            idx_p = df_p[df_p['ID'] == int(item['ID_Producto'])].index
            if idx_p.empty: return jsonify({"error": f"Producto ID {item['ID_Producto']} no existe"}), 404
            
            idx = idx_p[0]
            cant_solicitada = float(item['Cantidad'])
            stock_actual = float(df_p.at[idx, 'Cantidad'])
            
            if stock_actual < cant_solicitada:
                return jsonify({"error": f"Stock insuficiente para '{df_p.at[idx, 'Producto']}'. Disponibles: {stock_actual}"}), 400

        # 2. Procesamiento
        for item in carrito:
            idx_p = df_p[df_p['ID'] == int(item['ID_Producto'])].index
            idx = idx_p[0]
            
            cant = float(item['Cantidad'])
            precio_unit = float(item['Precio_Venta_Real'])
            costo = float(df_p.at[idx, 'Costo_Compra'])
            
            df_p.at[idx, 'Cantidad'] = float(df_p.at[idx, 'Cantidad']) - cant
            
            nueva_venta = {
                "ID_Venta": int(datetime.now().timestamp() * 1000) + carrito.index(item),
                "Ticket_Ref": ticket_ref,
                "Fecha": fecha_global,
                "ID_Producto": int(item['ID_Producto']),
                "Producto": str(df_p.at[idx, 'Producto']),
                "Cantidad": cant,
                "Precio_Venta_Real": precio_unit,
                "Total_Venta": precio_unit * cant,
                "Ganancia": (precio_unit - costo) * cant,
                "Cliente": str(cliente),
                "Direccion": str(direccion)
            }
            nuevas_ventas.append(nueva_venta)

        # 3. Guardar
        if not guardar_datos(df_p, "Productos"): return jsonify({"error": "Excel bloqueado por otro usuario"}), 400
        
        df_v = pd.concat([df_v, pd.DataFrame(nuevas_ventas)], ignore_index=True)
        guardar_datos(df_v, "Ventas")
        
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
def api_borrar_venta():
    try:
        vid = int(request.json.get("ID_Venta"))
        df_v = leer_datos("Ventas")
        row = df_v[df_v['ID_Venta'] == vid]
        if not row.empty:
            pid = int(row.iloc[0]['ID_Producto'])
            cant = float(row.iloc[0]['Cantidad'])
            df_p = leer_datos("Productos")
            idx_p = df_p[df_p['ID'] == pid].index
            if not idx_p.empty:
                df_p.at[idx_p[0], 'Cantidad'] += cant
                guardar_datos(df_p, "Productos")
            df_v = df_v[df_v['ID_Venta'] != vid]
            guardar_datos(df_v, "Ventas")
        return jsonify({"mensaje": "Eliminada"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/api/editar_venta", methods=["POST"])
def api_editar_venta():
    try:
        data = request.json
        df_v = leer_datos("Ventas")
        idx = df_v[df_v['ID_Venta'] == int(data['ID_Venta'])].index
        if not idx.empty:
            idx = idx[0]
            df_v.at[idx, 'Cliente'] = str(data['Cliente'] or "")
            df_v.at[idx, 'Direccion'] = str(data['Direccion'] or "")
            nuevo_total = float(data['Precio_Venta_Real'])
            cant = float(df_v.at[idx, 'Cantidad'])
            pid = int(df_v.at[idx, 'ID_Producto'])
            
            precio_unitario_nuevo = nuevo_total / cant if cant > 0 else 0
            
            df_p = leer_datos("Productos")
            costo = 0
            idx_p = df_p[df_p['ID'] == pid].index
            if not idx_p.empty: costo = float(df_p.at[idx_p[0], 'Costo_Compra'])
            
            df_v.at[idx, 'Precio_Venta_Real'] = precio_unitario_nuevo
            df_v.at[idx, 'Total_Venta'] = nuevo_total
            df_v.at[idx, 'Ganancia'] = (precio_unitario_nuevo - costo) * cant
            guardar_datos(df_v, "Ventas")
        return jsonify({"mensaje": "Editado"})
    except Exception as e: return jsonify({"error": str(e)}), 500

# --- REPORTES ---
@app.route("/api/reportes")
def reportes():
    try:
        fi = request.args.get('fecha_inicio')
        ff = request.args.get('fecha_fin')

        df_v = leer_datos("Ventas")
        df_p = leer_datos("Productos")
        
        res = { 
            "total_ingresos": 0, "total_ganancia": 0, "ventas_totales": 0, 
            "top_productos": [], "valor_inventario": 0,
            "grafica_fechas": [], "grafica_valores": [] 
        }
        
        if not df_p.empty:
            res["valor_inventario"] = float((df_p["Cantidad"] * df_p["Costo_Compra"]).sum())
            
        if not df_v.empty:
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
                prod_row = df_p[df_p["Producto"] == item["Producto"]]
                item["Imagen"] = str(prod_row.iloc[0].get("Imagen", "")) if not prod_row.empty else ""
            res["top_productos"] = top_dict
            
        return jsonify(res)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    asegurar_excel()
    app.run(debug=True, port=8080)