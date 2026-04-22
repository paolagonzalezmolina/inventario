"""
export_to_excel.py - Exportar inventario a Excel
════════════════════════════════════════════════════════════════
Genera un Excel con pestañas para cada tipo de componente.
Incluye datos de todas las cuentas y regiones.
"""

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from datetime import datetime
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═════════════════════════════════════════════════════════════════════════════

def _remove_timezones(df):
    """
    Remueve timezones de columnas datetime (Excel no los soporta).
    Maneja todos los casos: UTC, aware, naive, etc.
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    # Buscar columnas con datetime y remover timezone
    for col in df.columns:
        try:
            # Verificar si es datetime
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                # Si tiene timezone, removerlo
                if hasattr(df[col].dtype, 'tz') and df[col].dtype.tz is not None:
                    # Convertir a UTC primero, luego remover timezone
                    df[col] = df[col].dt.tz_convert('UTC').dt.tz_localize(None)
                elif df[col].dt.tz is not None:
                    # Método alternativo si la propiedad tz existe
                    df[col] = df[col].dt.tz_localize(None)
        except Exception as e:
            # Si hay error, intentar convertir a string para que Excel lo acepte
            logger.warning(f"Advertencia limpiando {col}: {e}")
            try:
                df[col] = df[col].astype(str)
            except:
                pass
    
    return df

# ═════════════════════════════════════════════════════════════════════════════
# ESTILOS EXCEL
# ═════════════════════════════════════════════════════════════════════════════

HEADER_FILL = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
BORDER = Border(
    left=Side(style='thin'),
    right=Side(style='thin'),
    top=Side(style='thin'),
    bottom=Side(style='thin')
)

def _apply_styles(ws, df):
    """Aplica estilos a un worksheet."""
    # Header
    for col_num, colname in enumerate(df.columns, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = colname
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = BORDER
    
    # Datos
    for row_num, row_data in enumerate(dataframe_to_rows(df, index=False, header=False), 2):
        for col_num, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col_num)
            cell.value = value
            cell.border = BORDER
            cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
    
    # Ancho de columnas
    for col_num, col in enumerate(df.columns, 1):
        max_length = max(
            df.iloc[:, col_num-1].astype(str).map(len).max(),
            len(str(col))
        )
        ws.column_dimensions[chr(64 + col_num)].width = min(max_length + 2, 50)

# ═════════════════════════════════════════════════════════════════════════════
# GENERADORES DE DATAFRAMES AGREGADOS
# ═════════════════════════════════════════════════════════════════════════════

def _aggregate_all_ec2(cache_manager, accounts, perfiles):
    """Agrega todos los EC2 de todas las cuentas y regiones."""
    dfs = []
    
    for account in accounts:
        for region in perfiles[account].get('regiones', []):
            try:
                data, _, exists = cache_manager.get(account, region, 'ec2')
                if exists and isinstance(data, pd.DataFrame):
                    data['cuenta'] = account
                    dfs.append(data)
            except:
                pass
    
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        # Reordenar columnas
        cols = ['cuenta', 'region', 'nombre', 'id', 'tipo', 'estado', 'vpc', 'ip_privada', 'ip_publica']
        existing_cols = [c for c in cols if c in df.columns]
        return df[existing_cols + [c for c in df.columns if c not in existing_cols]]
    
    return pd.DataFrame()

def _aggregate_all_rds(cache_manager, accounts, perfiles):
    """Agrega todos los RDS de todas las cuentas y regiones."""
    dfs = []
    
    for account in accounts:
        for region in perfiles[account].get('regiones', []):
            try:
                data, _, exists = cache_manager.get(account, region, 'rds')
                if exists and isinstance(data, pd.DataFrame):
                    data['cuenta'] = account
                    dfs.append(data)
            except:
                pass
    
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        cols = ['cuenta', 'region', 'nombre', 'id', 'motor', 'version', 'estado', 'tipo', 'almacenamiento_gb']
        existing_cols = [c for c in cols if c in df.columns]
        return df[existing_cols + [c for c in df.columns if c not in existing_cols]]
    
    return pd.DataFrame()

def _aggregate_all_vpc(cache_manager, accounts, perfiles):
    """Agrega todos los VPC de todas las cuentas y regiones."""
    dfs = []
    
    for account in accounts:
        for region in perfiles[account].get('regiones', []):
            try:
                data, _, exists = cache_manager.get(account, region, 'vpc')
                if exists and isinstance(data, pd.DataFrame):
                    data['cuenta'] = account
                    dfs.append(data)
            except:
                pass
    
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        cols = ['cuenta', 'region', 'nombre', 'id', 'cidr', 'estado', 'subnets']
        existing_cols = [c for c in cols if c in df.columns]
        return df[existing_cols + [c for c in df.columns if c not in existing_cols]]
    
    return pd.DataFrame()

def _aggregate_all_s3(cache_manager, accounts, perfiles):
    """Agrega todos los S3 de todas las cuentas."""
    dfs = []
    
    for account in accounts:
        region = perfiles[account].get('regiones', ['us-east-1'])[0]
        try:
            data, _, exists = cache_manager.get(account, region, 's3')
            if exists and isinstance(data, pd.DataFrame):
                data['cuenta'] = account
                dfs.append(data)
        except:
            pass
    
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        cols = ['cuenta', 'nombre', 'region', 'creacion']
        existing_cols = [c for c in cols if c in df.columns]
        return df[existing_cols + [c for c in df.columns if c not in existing_cols]]
    
    return pd.DataFrame()

def _aggregate_all_iam(cache_manager, accounts, perfiles):
    """Agrega todos los IAM Users de todas las cuentas."""
    dfs = []
    
    for account in accounts:
        region = perfiles[account].get('regiones', ['us-east-1'])[0]
        try:
            data, _, exists = cache_manager.get(account, region, 'iam_users')
            if exists and isinstance(data, pd.DataFrame):
                data['cuenta'] = account
                dfs.append(data)
        except:
            pass
    
    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        cols = ['cuenta', 'username', 'arn', 'mfa_enabled', 'access_keys', 'creacion']
        existing_cols = [c for c in cols if c in df.columns]
        return df[existing_cols + [c for c in df.columns if c not in existing_cols]]
    
    return pd.DataFrame()

# ═════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ═════════════════════════════════════════════════════════════════════════════

def export_to_excel(cache_manager, accounts, perfiles, output_path="inventario_aws.xlsx"):
    """
    Exporta TODO el inventario a un Excel con múltiples pestañas.
    
    Args:
        cache_manager: Instancia de CacheManager
        accounts: Lista de cuentas (ej: ["afex-des", "afex-prod", ...])
        perfiles: Dict de perfiles (PERFILES de config.py)
        output_path: Ruta de salida del Excel
    
    Returns:
        Ruta del archivo generado (o None si error)
    """
    
    try:
        logger.info(f"📊 Generando Excel: {output_path}")
        
        # Crear workbook
        wb = Workbook()
        wb.remove(wb.active)  # Remover hoja por defecto
        
        # ─────────────────────────────────────────────────────────────────────
        # PESTAÑA: RESUMEN
        # ─────────────────────────────────────────────────────────────────────
        
        ws_summary = wb.create_sheet("📊 Resumen", 0)
        
        # Título
        ws_summary['A1'] = "INVENTARIO AWS"
        ws_summary['A1'].font = Font(bold=True, size=14, color="FFFFFF")
        ws_summary['A1'].fill = PatternFill(start_color="003366", end_color="003366", fill_type="solid")
        ws_summary.merge_cells('A1:D1')
        
        # Fecha
        ws_summary['A2'] = f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ws_summary['A2'].font = Font(italic=True, size=10)
        
        # Tabla de cuentas
        ws_summary['A4'] = "CUENTA"
        ws_summary['B4'] = "EC2"
        ws_summary['C4'] = "RDS"
        ws_summary['D4'] = "VPC"
        ws_summary['E4'] = "S3"
        ws_summary['F4'] = "IAM Users"
        
        row = 5
        total_ec2 = 0
        total_rds = 0
        total_vpc = 0
        total_s3 = 0
        total_iam = 0
        
        for account in accounts:
            ec2_count = 0
            rds_count = 0
            vpc_count = 0
            s3_count = 0
            iam_count = 0
            
            # EC2
            for region in perfiles[account].get('regiones', []):
                data, _, exists = cache_manager.get(account, region, 'ec2')
                if exists and isinstance(data, pd.DataFrame):
                    ec2_count += len(data)
            
            # RDS
            for region in perfiles[account].get('regiones', []):
                data, _, exists = cache_manager.get(account, region, 'rds')
                if exists and isinstance(data, pd.DataFrame):
                    rds_count += len(data)
            
            # VPC
            for region in perfiles[account].get('regiones', []):
                data, _, exists = cache_manager.get(account, region, 'vpc')
                if exists and isinstance(data, pd.DataFrame):
                    vpc_count += len(data)
            
            # S3 (global)
            region = perfiles[account].get('regiones', ['us-east-1'])[0]
            data, _, exists = cache_manager.get(account, region, 's3')
            if exists and isinstance(data, pd.DataFrame):
                s3_count = len(data)
            
            # IAM (global)
            data, _, exists = cache_manager.get(account, region, 'iam_users')
            if exists and isinstance(data, pd.DataFrame):
                iam_count = len(data)
            
            # Agregar fila
            ws_summary[f'A{row}'] = account
            ws_summary[f'B{row}'] = ec2_count
            ws_summary[f'C{row}'] = rds_count
            ws_summary[f'D{row}'] = vpc_count
            ws_summary[f'E{row}'] = s3_count
            ws_summary[f'F{row}'] = iam_count
            
            total_ec2 += ec2_count
            total_rds += rds_count
            total_vpc += vpc_count
            total_s3 += s3_count
            total_iam += iam_count
            
            row += 1
        
        # Fila de totales
        ws_summary[f'A{row}'] = "TOTAL"
        ws_summary[f'A{row}'].font = Font(bold=True)
        ws_summary[f'B{row}'] = total_ec2
        ws_summary[f'B{row}'].font = Font(bold=True)
        ws_summary[f'C{row}'] = total_rds
        ws_summary[f'C{row}'].font = Font(bold=True)
        ws_summary[f'D{row}'] = total_vpc
        ws_summary[f'D{row}'].font = Font(bold=True)
        ws_summary[f'E{row}'] = total_s3
        ws_summary[f'E{row}'].font = Font(bold=True)
        ws_summary[f'F{row}'] = total_iam
        ws_summary[f'F{row}'].font = Font(bold=True)
        
        # Ancho de columnas
        for col in ['A', 'B', 'C', 'D', 'E', 'F']:
            ws_summary.column_dimensions[col].width = 15
        
        # ─────────────────────────────────────────────────────────────────────
        # PESTAÑA: EC2
        # ─────────────────────────────────────────────────────────────────────
        
        df_ec2 = _aggregate_all_ec2(cache_manager, accounts, perfiles)
        df_ec2 = _remove_timezones(df_ec2)
        if not df_ec2.empty:
            ws_ec2 = wb.create_sheet("💻 EC2", 1)
            for r_idx, row in enumerate(dataframe_to_rows(df_ec2, index=False, header=True), 1):
                for c_idx, value in enumerate(row, 1):
                    ws_ec2.cell(row=r_idx, column=c_idx, value=value)
            _apply_styles(ws_ec2, df_ec2)
            logger.info(f"✅ Pestaña EC2: {len(df_ec2)} filas")
        
        # ─────────────────────────────────────────────────────────────────────
        # PESTAÑA: RDS
        # ─────────────────────────────────────────────────────────────────────
        
        df_rds = _aggregate_all_rds(cache_manager, accounts, perfiles)
        df_rds = _remove_timezones(df_rds)
        if not df_rds.empty:
            ws_rds = wb.create_sheet("🗄️  RDS", 2)
            for r_idx, row in enumerate(dataframe_to_rows(df_rds, index=False, header=True), 1):
                for c_idx, value in enumerate(row, 1):
                    ws_rds.cell(row=r_idx, column=c_idx, value=value)
            _apply_styles(ws_rds, df_rds)
            logger.info(f"✅ Pestaña RDS: {len(df_rds)} filas")
        
        # ─────────────────────────────────────────────────────────────────────
        # PESTAÑA: VPC
        # ─────────────────────────────────────────────────────────────────────
        
        df_vpc = _aggregate_all_vpc(cache_manager, accounts, perfiles)
        df_vpc = _remove_timezones(df_vpc)
        if not df_vpc.empty:
            ws_vpc = wb.create_sheet("🌐 VPC", 3)
            for r_idx, row in enumerate(dataframe_to_rows(df_vpc, index=False, header=True), 1):
                for c_idx, value in enumerate(row, 1):
                    ws_vpc.cell(row=r_idx, column=c_idx, value=value)
            _apply_styles(ws_vpc, df_vpc)
            logger.info(f"✅ Pestaña VPC: {len(df_vpc)} filas")
        
        # ─────────────────────────────────────────────────────────────────────
        # PESTAÑA: S3
        # ─────────────────────────────────────────────────────────────────────
        
        df_s3 = _aggregate_all_s3(cache_manager, accounts, perfiles)
        df_s3 = _remove_timezones(df_s3)
        if not df_s3.empty:
            ws_s3 = wb.create_sheet("🪣 S3", 4)
            for r_idx, row in enumerate(dataframe_to_rows(df_s3, index=False, header=True), 1):
                for c_idx, value in enumerate(row, 1):
                    ws_s3.cell(row=r_idx, column=c_idx, value=value)
            _apply_styles(ws_s3, df_s3)
            logger.info(f"✅ Pestaña S3: {len(df_s3)} filas")
        
        # ─────────────────────────────────────────────────────────────────────
        # PESTAÑA: IAM Users
        # ─────────────────────────────────────────────────────────────────────
        
        df_iam = _aggregate_all_iam(cache_manager, accounts, perfiles)
        df_iam = _remove_timezones(df_iam)
        if not df_iam.empty:
            ws_iam = wb.create_sheet("👥 IAM Users", 5)
            for r_idx, row in enumerate(dataframe_to_rows(df_iam, index=False, header=True), 1):
                for c_idx, value in enumerate(row, 1):
                    ws_iam.cell(row=r_idx, column=c_idx, value=value)
            _apply_styles(ws_iam, df_iam)
            logger.info(f"✅ Pestaña IAM: {len(df_iam)} filas")
        
        # Guardar
        wb.save(output_path)
        
        logger.info(f"✅ Excel guardado: {output_path}")
        return output_path
    
    except Exception as e:
        logger.error(f"❌ Error generando Excel: {e}")
        return None
