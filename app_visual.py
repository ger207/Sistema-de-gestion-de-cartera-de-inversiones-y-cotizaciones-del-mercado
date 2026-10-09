"""
Bimonetary Portfolio & Risk Manager - Streamlit Frontend MVP
Interfaz interactiva para seguimiento automatizado de carteras de inversión bimonetarias (USD/ARS).
Consume los endpoints de la API FastAPI (http://localhost:8000).
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from decimal import Decimal

# ==============================================================================
# CONFIGURACIÓN GENERAL Y ESTILO DE PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Portfolio & Risk Manager | USD/ARS",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE_URL = "http://localhost:8000/api/v1"

# Inyectar estilos CSS para pulir la interfaz
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border-left: 5px solid #1E88E5;
    }
    .stMetric label {
        font-weight: 600;
        color: #555;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# FUNCIONES AUXILIARES DE CONEXIÓN CON FASTAPI (API CLIENT)
# ==============================================================================
@st.cache_data(ttl=15)
def fetch_api(endpoint: str):
    """Realiza una petición GET al backend FastAPI con manejo de errores."""
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=8)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None

def post_api(endpoint: str, payload: dict):
    """Realiza una petición POST al backend FastAPI."""
    try:
        response = requests.post(f"{API_BASE_URL}{endpoint}", json=payload, timeout=12)
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"Error de conexión con el backend: {e}")
        return None


# ==============================================================================
# ESTADO DE CONEXIÓN
# ==============================================================================
backend_health = fetch_api("/../../health")
if not backend_health:
    st.error("⚠️ No se puede conectar con el backend en `http://localhost:8000`. Asegúrate de que FastAPI esté corriendo.")
    st.info("Para iniciarlo, ejecuta en una terminal: `uvicorn app.main:app --reload` dentro de la carpeta `backend`.")
    st.stop()


# ==============================================================================
# CARGA DE DATOS PRINCIPALES (PORTFOLIOS & ACCOUNTS)
# ==============================================================================
portfolios = fetch_api("/portfolios/")
if not portfolios:
    st.warning("No hay carteras registradas. Por favor ejecuta el script de inicialización o crea una.")
    st.stop()

# Selección de cartera en la barra lateral
active_portfolio = portfolios[0]
portfolio_id = active_portfolio["id"]
accounts = active_portfolio.get("accounts", [])


# ==============================================================================
# SIDEBAR: FORMULARIO INTELIGENTE DE TRANSACCIONES
# ==============================================================================
st.sidebar.image("https://img.icons8.com/fluency/96/bullish.png", width=64)
st.sidebar.title("Gestión de Cartera")
st.sidebar.markdown(f"**Cartera Activa:** `{active_portfolio['name']}`")
st.sidebar.markdown("---")

st.sidebar.subheader("➕ Nueva Operación")

with st.sidebar.form(key="transaction_form", clear_on_submit=False):
    # 1. Filtro por clase de activo
    asset_class_choice = st.selectbox(
        "Clase de Instrumento:",
        options=["CEDEARs", "Acciones Merval", "Bonos Soberanos", "Criptomonedas"],
        help="El sistema normalizará automáticamente el ticker según la clase elegida."
    )

    # 2. Entrada inteligente de Ticker
    ticker_input = st.text_input(
        "Ticker / Símbolo:",
        placeholder="Ej: AAPL, GGAL, AL30, BTC",
        help="Escribe el ticker base. El sistema le aplicará el sufijo correspondiente."
    ).strip().upper()

    # Normalización automática del ticker
    normalized_ticker = ticker_input
    asset_class_enum = "EQUITY_LOCAL"
    default_currency = "ARS"

    if ticker_input:
        if asset_class_choice == "CEDEARs":
            asset_class_enum = "CEDEAR"
            normalized_ticker = ticker_input if ticker_input.endswith(".BA") else f"{ticker_input}.BA"
            default_currency = "ARS"
        elif asset_class_choice == "Acciones Merval":
            asset_class_enum = "EQUITY_LOCAL"
            normalized_ticker = ticker_input if ticker_input.endswith(".BA") else f"{ticker_input}.BA"
            default_currency = "ARS"
        elif asset_class_choice == "Bonos Soberanos":
            asset_class_enum = "SOVEREIGN_BOND"
            normalized_ticker = ticker_input if ticker_input.endswith(".BA") else f"{ticker_input}.BA"
            default_currency = "ARS"
        elif asset_class_choice == "Criptomonedas":
            asset_class_enum = "CRYPTO_SPOT"
            if not ("-" in ticker_input or ticker_input.endswith("USDT") or ticker_input.endswith("USD")):
                normalized_ticker = f"{ticker_input}-USD"
            else:
                normalized_ticker = ticker_input
            default_currency = "USD"

        st.caption(f"Ticker interpretado: `{normalized_ticker}` ({asset_class_enum})")

    # 3. Datos de la transacción
    tx_type = st.selectbox("Tipo de Operación:", options=["BUY", "SELL"], format_func=lambda x: "Compra (BUY)" if x == "BUY" else "Venta (SELL)")
    
    col_q, col_p = st.columns(2)
    with col_q:
        quantity = st.number_input("Cantidad:", min_value=0.00000001, value=1.0, format="%.6f")
    with col_p:
        price = st.number_input("Precio Unitario:", min_value=0.0001, value=1000.0, format="%.2f")

    col_cur, col_acc = st.columns(2)
    with col_cur:
        currency = st.selectbox("Moneda:", options=["ARS", "USD", "USDT"], index=0 if default_currency == "ARS" else 1)
    with col_acc:
        if accounts:
            account_names = {acc["id"]: acc["name"] for acc in accounts}
            account_id = st.selectbox("Cuenta/Broker:", options=list(account_names.keys()), format_func=lambda x: account_names[x])
        else:
            account_id = None
            st.error("No hay cuentas asociadas a esta cartera.")

    fee = st.number_input("Comisión / Arancel:", min_value=0.0, value=0.0, format="%.2f")
    notes = st.text_input("Notas (Opcional):", placeholder="Ej: Compra mensual DCA")

    submit_button = st.form_submit_button("🚀 Registrar Transacción", use_container_width=True)

    if submit_button:
        if not ticker_input:
            st.sidebar.error("Debes ingresar un ticker válido.")
        elif not account_id:
            st.sidebar.error("Se requiere una cuenta de custodia para imputar la operación.")
        else:
            # A. Asegurar existencia del activo en el backend
            existing_assets = fetch_api("/assets/") or []
            asset_obj = next((a for a in existing_assets if a["ticker"] == normalized_ticker), None)

            if not asset_obj:
                with st.spinner(f"Creando activo {normalized_ticker} en el catálogo..."):
                    new_asset_payload = {
                        "ticker": normalized_ticker,
                        "name": f"{ticker_input} ({asset_class_choice})",
                        "asset_class": asset_class_enum,
                        "currency": currency,
                        "is_active": True
                    }
                    create_asset_res = post_api("/assets/", new_asset_payload)
                    if create_asset_res and create_asset_res.status_code in [200, 201]:
                        asset_obj = create_asset_res.json()
                    else:
                        st.sidebar.error("Error al registrar activo en el catálogo.")
                        st.stop()

            # B. Obtener tipo de cambio CCL actual para imputar conversión histórica
            latest_ccl = fetch_api("/market-data/dolar/latest")
            ccl_rate = 1250.0  # fallback de seguridad
            if latest_ccl:
                ccl_item = next((r for r in latest_ccl if r["rate_type"] == "CCL"), None)
                if ccl_item:
                    ccl_rate = float(ccl_item["sell_price"])

            # C. Registrar transacción en el Ledger
            tx_payload = {
                "account_id": account_id,
                "asset_id": asset_obj["id"],
                "transaction_type": tx_type,
                "executed_at": datetime.utcnow().isoformat(),
                "quantity": quantity,
                "price": price,
                "currency": currency,
                "fee": fee,
                "fx_rate": ccl_rate,
                "fx_rate_type": "CCL",
                "notes": notes or f"Operación desde UI ({asset_class_choice})"
            }

            res = post_api("/transactions/", tx_payload)
            if res and res.status_code in [200, 201]:
                st.sidebar.success(f"¡Transacción de {normalized_ticker} registrada con éxito!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.sidebar.error(f"Error al registrar la transacción: {res.text if res else 'Sin respuesta'}")

# Botón de sincronización manual en el sidebar
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Sincronizar Cotizaciones Ahora", use_container_width=True):
    with st.spinner("Sincronizando Dólar (DolarApi) y Activos (Yahoo Finance)..."):
        post_api("/market-data/sync/dolar", {})
        st.cache_data.clear()
        st.sidebar.success("Mercado sincronizado.")
        st.rerun()


# ==============================================================================
# CABECERA Y CONTROL DE MONEDA (TOGGLE ARS / USD)
# ==============================================================================
col_title, col_toggle = st.columns([3, 1])

with col_title:
    st.title("💼 Gestor de Carteras Bimonetarias")
    st.caption("Seguimiento automatizado en tiempo real | Aislamiento de ilusión monetaria")

with col_toggle:
    st.markdown("<br>", unsafe_allow_html=True)
    # Toggle para alternar la vista entre Pesos (ARS) y Dólares (USD)
    view_currency = st.radio(
        "Moneda de Visualización:",
        options=["USD (Moneda Dura)", "ARS (Pesos)"],
        horizontal=True,
        index=0,
        help="Cambia todos los totales y valuaciones entre Dólares y Pesos."
    )
    is_usd = "USD" in view_currency

# Obtener valuación calculada del backend
valuation_data = fetch_api(f"/portfolios/{portfolio_id}/valuation?fx_type=CCL")

if not valuation_data:
    st.error("No se pudo obtener la valuación de la cartera.")
    st.stop()


# ==============================================================================
# DASHBOARD PRINCIPAL: MÉTRICAS CLAVE (KPIs)
# ==============================================================================
ccl_rate_used = valuation_data.get("fx_rate_applied", 1250.0)

if is_usd:
    total_val = valuation_data.get("total_value_usd", 0.0)
    total_cost = valuation_data.get("total_cost_usd", 0.0)
    total_pnl = valuation_data.get("total_pnl_usd", 0.0)
    pnl_pct = valuation_data.get("total_pnl_pct_usd", 0.0)
    currency_symbol = "USD $"
else:
    total_val = valuation_data.get("total_value_ars", 0.0)
    total_cost = valuation_data.get("total_cost_ars", 0.0)
    total_pnl = valuation_data.get("total_pnl_ars", 0.0)
    pnl_pct = valuation_data.get("total_pnl_pct_ars", 0.0)
    currency_symbol = "ARS $"

col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

with col_kpi1:
    st.metric(
        label="Valor Total de Cartera (MTM)",
        value=f"{currency_symbol} {total_val:,.2f}",
        delta=f"{pnl_pct:+.2f}%",
    )

with col_kpi2:
    st.metric(
        label="Costo Base Invertido (PPP)",
        value=f"{currency_symbol} {total_cost:,.2f}",
    )

with col_kpi3:
    st.metric(
        label="Rendimiento Total (P&L)",
        value=f"{currency_symbol} {total_pnl:,.2f}",
        delta=f"{pnl_pct:+.2f}%",
        delta_color="normal"
    )

with col_kpi4:
    st.metric(
        label="Dólar CCL de Valuación",
        value=f"ARS ${float(ccl_rate_used):,.2f}",
        help="Tipo de cambio financiero aplicado para la conversión bimonetaria."
    )

# Banner explicativo de Aislamiento de Ilusión Monetaria
pnl_usd_pct = valuation_data.get("total_pnl_pct_usd", 0.0)
pnl_ars_pct = valuation_data.get("total_pnl_pct_ars", 0.0)

st.info(
    f"💡 **Análisis de Rendimiento Real vs Nominal:** "
    f"En **moneda dura (USD)** tu cartera rinde **{pnl_usd_pct:+.2f}%**, mientras que en **pesos (ARS)** la ganancia aparente es de **{pnl_ars_pct:+.2f}%**. "
    f"La diferencia de **{abs(pnl_ars_pct - pnl_usd_pct):.2f}%** corresponde al efecto de la devaluación cambiaria del ARS."
)


# ==============================================================================
# PESTAÑAS (TABS) DE NAVEGACIÓN
# ==============================================================================
tab_overview, tab_dolar, tab_transactions, tab_risk = st.tabs([
    "📊 Composición & Tenencias",
    "💵 Dólar en Tiempo Real",
    "📜 Historial de Operaciones",
    "⚡ Gestión de Riesgo (Futuros)"
])


# ------------------------------------------------------------------------------
# TAB 1: COMPOSICIÓN Y TENENCIAS
# ------------------------------------------------------------------------------
with tab_overview:
    holdings = valuation_data.get("holdings", [])

    if holdings:
        df_holdings = pd.DataFrame(holdings)

        # Gráficos en 2 columnas
        col_g1, col_g2 = st.columns([1, 1])

        with col_g1:
            st.subheader("Distribución por Clase de Activo")
            # Mapeo de nombres más amigables
            class_labels = {
                "EQUITY_LOCAL": "Acciones Merval",
                "CEDEAR": "CEDEARs",
                "SOVEREIGN_BOND": "Bonos Soberanos",
                "CRYPTO_SPOT": "Cripto Spot",
                "CASH": "Liquidez / Efectivo"
            }
            df_holdings["Clase"] = df_holdings["asset_class"].map(lambda x: class_labels.get(x, x))
            
            val_col = "current_value_usd" if is_usd else "current_value_ars"
            fig_pie = px.pie(
                df_holdings,
                names="Clase",
                values=val_col,
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Safe,
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=350)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_g2:
            st.subheader("P&L No Realizado por Activo")
            pnl_col = "unrealized_pnl_usd" if is_usd else "unrealized_pnl_ars"
            df_holdings["color"] = df_holdings[pnl_col].apply(lambda x: "Ganancia" if x >= 0 else "Pérdida")
            
            fig_bar = px.bar(
                df_holdings,
                x="ticker",
                y=pnl_col,
                color="color",
                color_discrete_map={"Ganancia": "#2E7D32", "Pérdida": "#C62828"},
                labels={"ticker": "Activo", pnl_col: f"P&L ({currency_symbol})"},
            )
            fig_bar.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=350, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

        st.subheader("📋 Detalle de Posiciones Activas")
        
        # Tabla detallada formateada
        display_df = df_holdings[[
            "ticker", "name", "Clase", "quantity", "latest_unit_price", "quote_currency",
            val_col, "cost_basis_usd" if is_usd else "cost_basis_ars",
            pnl_col, "pnl_pct_usd" if is_usd else "pnl_pct_ars"
        ]].copy()

        display_df.columns = [
            "Ticker", "Nombre", "Tipo", "Cantidad", "Últ. Cotización", "Moneda Cotiz.",
            f"Valor Actual ({'USD' if is_usd else 'ARS'})",
            f"Costo Base ({'USD' if is_usd else 'ARS'})",
            f"P&L ({'USD' if is_usd else 'ARS'})",
            "P&L (%)"
        ]

        st.dataframe(
            display_df.style.format({
                "Cantidad": "{:,.4f}",
                "Últ. Cotización": "{:,.2f}",
                f"Valor Actual ({'USD' if is_usd else 'ARS'})": "{:,.2f}",
                f"Costo Base ({'USD' if is_usd else 'ARS'})": "{:,.2f}",
                f"P&L ({'USD' if is_usd else 'ARS'})": "{:+,.2f}",
                "P&L (%)": "{:+.2f}%",
            }),
            use_container_width=True
        )
    else:
        st.info("No hay tenencias abiertas en esta cartera. Utiliza el formulario lateral para cargar tu primera compra.")


# ------------------------------------------------------------------------------
# TAB 2: DÓLAR EN TIEMPO REAL
# ------------------------------------------------------------------------------
with tab_dolar:
    st.subheader("Cotizaciones del Dólar Financiero & Libre")
    st.caption("Consumido en tiempo real desde DolarApi / Backend")

    dolar_rates = fetch_api("/market-data/dolar/latest")

    if dolar_rates:
        # Tarjetas de cotizaciones
        cols_fx = st.columns(len(dolar_rates))
        for idx, rate in enumerate(dolar_rates):
            r_type = rate["rate_type"]
            v_sell = float(rate["sell_price"])
            v_buy = float(rate["buy_price"]) if rate["buy_price"] else None
            
            with cols_fx[idx]:
                st.markdown(f"### Dólar {r_type}")
                st.metric(
                    label="Venta",
                    value=f"${v_sell:,.2f}",
                    delta=f"Compra: ${v_buy:,.2f}" if v_buy else "Único"
                )
                st.caption(f"Fuente: `{rate['source']}`")

        # Gráfico comparativo de brecha cambiaria
        df_fx = pd.DataFrame(dolar_rates)
        df_fx["sell_price"] = df_fx["sell_price"].astype(float)
        
        fig_fx = px.bar(
            df_fx,
            x="rate_type",
            y="sell_price",
            text="sell_price",
            color="rate_type",
            labels={"rate_type": "Tipo de Cambio", "sell_price": "Cotización Venta (ARS)"},
            title="Comparativa de Tipos de Cambio en Argentina"
        )
        fig_fx.update_traces(texttemplate='$%{text:,.2f}', textposition='outside')
        fig_fx.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_fx, use_container_width=True)
    else:
        st.warning("No se encontraron tipos de cambio registrados.")
        if st.button("Sincronizar Dólar ahora"):
            post_api("/market-data/sync/dolar", {})
            st.rerun()


# ------------------------------------------------------------------------------
# TAB 3: HISTORIAL DE TRANSACCIONES (LEDGER)
# ------------------------------------------------------------------------------
with tab_transactions:
    st.subheader("Libro Contable de Movimientos")
    tx_list = fetch_api("/transactions/")

    if tx_list:
        df_tx = pd.DataFrame(tx_list)
        df_tx_display = df_tx[[
            "id", "executed_at", "transaction_type", "asset_id",
            "quantity", "price", "currency", "fee", "fx_rate", "net_amount", "notes"
        ]].copy()
        
        df_tx_display["executed_at"] = pd.to_datetime(df_tx_display["executed_at"]).dt.strftime("%Y-%m-%d %H:%M")
        df_tx_display.columns = [
            "ID", "Fecha Ejecución", "Tipo", "ID Activo", "Cantidad",
            "Precio Unitario", "Moneda", "Comisión", "TC Aplicado (CCL)", "Monto Neto", "Notas"
        ]

        st.dataframe(df_tx_display, use_container_width=True)
    else:
        st.info("No hay transacciones registradas todavía.")


# ------------------------------------------------------------------------------
# TAB 4: GESTIÓN DE RIESGO (FUTUROS CRIPTO)
# ------------------------------------------------------------------------------
with tab_risk:
    st.subheader("Supervisión de Posiciones de Futuros & Margen")
    st.caption("Monitoreo de apalancamiento, precio de liquidación y niveles de Stop-Loss")

    futures_list = fetch_api("/risk/futures")

    if futures_list:
        for pos in futures_list:
            pos_id = pos["id"]
            risk_status = fetch_api(f"/risk/futures/{pos_id}/risk-status")
            
            if risk_status:
                with st.expander(f"📌 Posición #{pos_id}: {risk_status['ticker']} ({risk_status['direction']} {risk_status['leverage']})", expanded=True):
                    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                    
                    with col_r1:
                        st.metric("Precio de Entrada", f"${float(risk_status['entry_price']):,.2f}")
                    with col_r2:
                        st.metric("Precio Actual", f"${float(risk_status['current_price']):,.2f}")
                    with col_r3:
                        st.metric("Precio de Liquidación", f"${float(risk_status['liquidation_price']):,.2f}")
                    with col_r4:
                        dist_liq = float(risk_status["distance_to_liquidation_pct"])
                        risk_level = risk_status["risk_level"]
                        delta_color = "normal" if dist_liq > 15 else "inverse"
                        st.metric("Distancia a Liquidación", f"{dist_liq:.2f}%", delta=risk_level, delta_color=delta_color)

                    # Barra visual de proximidad de riesgo
                    buffer_pct = min(max(dist_liq, 0.0), 100.0)
                    st.progress(buffer_pct / 100.0, text=f"Buffer de Seguridad de Margen: {buffer_pct:.1f}%")
                    
                    st.caption(
                        f"🛡️ **Take-Profit:** ${risk_status.get('take_profit_price') or 'No fijado'} | "
                        f"🛑 **Stop-Loss:** ${risk_status.get('stop_loss_price') or 'No fijado'} | "
                        f"💰 **PnL No Realizado:** ${float(risk_status['unrealized_pnl_usd']):+,.2f} USD"
                    )
    else:
        st.info("No hay posiciones abiertas en contratos de futuros cripto.")
