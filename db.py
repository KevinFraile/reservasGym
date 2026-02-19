import os
import pandas as pd
import numpy as np

ARCHIVO = "base_datos_pami.xlsx"

# Definición de Columnas
COLS_PRODUCTOS = ["ID", "Producto", "Cantidad", "Costo_Compra", "Precio_Venta_Sugerido", "Imagen"]
COLS_VENTAS = ["ID_Venta", "Ticket_Ref", "Fecha", "ID_Producto", "Producto", "Cantidad", "Precio_Venta_Real", "Total_Venta", "Ganancia", "Cliente", "Direccion"]
COLS_RESERVAS = ["ID_Reserva", "Nombre", "Conjunto", "Torre_Apto", "Documento", "Celular", "Email", "Servicio", "Fecha_Reserva", "Hora", "Fecha_Registro"]

def limpiar_para_json(df):
    df = df.replace([np.inf, -np.inf], 0)
    cols_texto = ["Producto", "Cliente", "Direccion", "Fecha", "Imagen", "Ticket_Ref", "Nombre", "Conjunto", "Torre_Apto", "Email", "Servicio", "Fecha_Reserva", "Hora"]
    for col in cols_texto:
        if col in df.columns: df[col] = df[col].fillna("")
    
    cols_num = ["Cantidad", "Costo_Compra", "Precio_Venta_Sugerido", "Precio_Venta_Real", "Total_Venta", "Ganancia", "ID", "ID_Producto", "ID_Venta", "ID_Reserva", "Documento", "Celular"]
    for col in cols_num:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def asegurar_excel():
    try:
        if not os.path.exists(ARCHIVO):
            with pd.ExcelWriter(ARCHIVO, engine='openpyxl') as writer:
                pd.DataFrame(columns=COLS_PRODUCTOS).to_excel(writer, sheet_name='Productos', index=False)
                pd.DataFrame(columns=COLS_VENTAS).to_excel(writer, sheet_name='Ventas', index=False)
                pd.DataFrame(columns=COLS_RESERVAS).to_excel(writer, sheet_name='Reservas', index=False)
            return

        xls = pd.ExcelFile(ARCHIVO, engine='openpyxl')
        cambios = False
        dict_df = {}

        for nombre, cols in [('Productos', COLS_PRODUCTOS), ('Ventas', COLS_VENTAS), ('Reservas', COLS_RESERVAS)]:
            if nombre in xls.sheet_names:
                df = pd.read_excel(ARCHIVO, sheet_name=nombre, engine='openpyxl')
                for col in cols:
                    if col not in df.columns:
                        df[col] = 0 if col in ["Cantidad", "Costo_Compra", "Precio_Venta_Sugerido", "Total_Venta", "Ganancia", "ID_Reserva"] else ""
                        cambios = True
                dict_df[nombre] = df
            else:
                dict_df[nombre] = pd.DataFrame(columns=cols)
                cambios = True
        
        if cambios:
            with pd.ExcelWriter(ARCHIVO, engine='openpyxl') as writer:
                for k, v in dict_df.items():
                    v.to_excel(writer, sheet_name=k, index=False)
    except Exception as e:
        print(f"⚠️ Error iniciando DB: {e}")

def leer_datos(hoja):
    asegurar_excel()
    try:
        df = pd.read_excel(ARCHIVO, sheet_name=hoja, engine='openpyxl')
        return limpiar_para_json(df)
    except:
        if hoja == "Productos": cols = COLS_PRODUCTOS
        elif hoja == "Ventas": cols = COLS_VENTAS
        else: cols = COLS_RESERVAS
        return pd.DataFrame(columns=cols)

def guardar_datos(df, hoja):
    try:
        xls = pd.ExcelFile(ARCHIVO, engine='openpyxl')
        dict_df = {s: xls.parse(s) for s in xls.sheet_names}
        dict_df[hoja] = df
        with pd.ExcelWriter(ARCHIVO, engine='openpyxl') as writer:
            for k, v in dict_df.items():
                v.to_excel(writer, sheet_name=k, index=False)
        return True
    except:
        return False