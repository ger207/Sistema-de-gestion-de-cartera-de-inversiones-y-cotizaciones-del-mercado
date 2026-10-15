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
from typing import Any, Optional

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

# Inyectar estilos CSS para una interfaz limpia, moderna y profesional
st.markdown("""
<style>
    .metric-card {
        background-color: #1e222d;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
        border-left: 5px solid #00C853;
    }
    .stMetric label {
        font-weight: 600;
    }
    .badge-positive {
        color: #00E676;
        font-weight: bold;
    }
    .badge-negative {
        color: #FF5252;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# FUNCIONES AUXILIARES DEFENSIVAS Y CLIENTE API
# ==============================================================================
def safe_float(val: Any, default: float = 0.0) -> float:
    """Convierte cualquier valor a float de manera segura para evitar errores de formateo."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


@st.cache_data(ttl=15)
def fetch_api(endpoint: str) -> Optional[Any]:
    """Realiza una petición GET al backend FastAPI con manejo de errores."""
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None


def post_api(endpoint: str, payload: dict) -> Optional[requests.Response]:
    """Realiza una petición POST al backend FastAPI."""
    try:
        response = requests.post(f"{API_BASE_URL}{endpoint}", json=payload, timeout=15)
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"Error de conexión con el backend: {e}")
        return None


# ==============================================================================
# VERIFICACIÓN DE ESTADO DEL SERVIDOR FASTAPI
# ==============================================================================
backend_health = fetch_api("/../../health")
if not backend_health:
    st.error("⚠️ No se puede conectar con el backend en `http://localhost:8000`. Asegúrate de que FastAPI esté corriendo.")
    st.info("Para iniciarlo, ejecuta en una terminal: `uvicorn app.main:app --reload` dentro de la carpeta `backend`.")
    st.stop()


# ==============================================================================
# CARGA DE CARTERA UNIFICADA (SIN SELECCIÓN MANUAL DE CUENTAS NI BROKERS)
# ==============================================================================
portfolios = fetch_api("/portfolios/")
if not portfolios:
    st.warning("No hay carteras registradas. Por favor ejecuta el script de inicialización o crea una.")
    st.stop()

# Cartera única consolidada
active_portfolio = portfolios[0]
portfolio_id = active_portfolio["id"]
accounts = active_portfolio.get("accounts", [])
# Cuenta por defecto para imputar operaciones automáticamente
default_account_id = accounts[0]["id"] if accounts else None


# ==============================================================================
# SIDEBAR: FORMULARIO INTELIGENTE DE TRANSACCIONES (CON COMISIÓN EN %)
# ==============================================================================
st.sidebar.image("https://img.icons8.com/fluency/96/bullish.png", width=64)
st.sidebar.title("Gestión de Cartera")
st.sidebar.markdown(f"**Cartera Unificada:** `{active_portfolio['name']}`")
st.sidebar.caption("Todas las cuentas y activos consolidados.")
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

    # 3. Tipo de Operación
    tx_type = st.selectbox(
        "Tipo de Operación:",
        options=["BUY", "SELL"],
        format_func=lambda x: "Compra (BUY)" if x == "BUY" else "Venta (SELL)"
    )
    
    col_q, col_p = st.columns(2)
    with col_q:
        quantity = st.number_input("Cantidad:", min_value=0.00000001, value=1.0, format="%.6f")
    with col_p:
        price = st.number_input("Precio Unitario:", min_value=0.0001, value=1000.0, format="%.2f")

    col_cur, col_fee_pct = st.columns(2)
    with col_cur:
        currency = st.selectbox(
            "Moneda:",
            options=["ARS", "USD", "USDT"],
            index=0 if default_currency == "ARS" else 1
        )
    with col_fee_pct:
        # Requerimiento: Comisión en porcentaje (%) ingresada por el usuario
        fee_percentage = st.number_input(
            "Comisión Broker (%):",
            min_value=0.0,
            max_value=15.0,
            value=0.50,
            step=0.05,
            format="%.2f",
            help="Porcentaje de comisión o arancel que cobra tu broker o exchange."
        )

    # Cálculo dinámico de subtotal y comisión
    gross_subtotal = quantity * price
    calculated_fee_amount = gross_subtotal * (fee_percentage / 100.0)
    estimated_net = (gross_subtotal + calculated_fee_amount) if tx_type == "BUY" else (gross_subtotal - calculated_fee_amount)

    st.markdown(
        f"<small>💰 Subtotal: <b>{currency} ${gross_subtotal:,.2f}</b><br>"
        f"🏷️ Comisión ({fee_percentage:.2f}%): <b>{currency} ${calculated_fee_amount:,.2f}</b><br>"
        f"🧾 Total Estimado: <b>{currency} ${estimated_net:,.2f}</b></small>",
        unsafe_allow_html=True
    )

    notes = st.text_input("Notas (Opcional):", placeholder="Ej: Compra periódica")

    submit_button = st.form_submit_button("🚀 Registrar Transacción", use_container_width=True)

    if submit_button:
        if not ticker_input:
            st.sidebar.error("Debes ingresar un ticker válido.")
        elif not default_account_id:
            st.sidebar.error("No se encontró una cuenta de custodia para imputar la operación.")
        else:
            # A. Asegurar existencia del activo en el catálogo
            existing_assets = fetch_api("/assets/") or []
            asset_obj = next((a for a in existing_assets if a["ticker"] == normalized_ticker), None)

            if not asset_obj:
                with st.spinner(f"Registrando {normalized_ticker} en el catálogo..."):
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
            ccl_rate = 1250.0
            if latest_ccl:
                ccl_item = next((r for r in latest_ccl if r.get("rate_type") == "CCL"), None)
                if ccl_item:
                    ccl_rate = safe_float(ccl_item.get("sell_price"), 1250.0)

            # C. Registrar transacción en el Ledger con la comisión calculada
            tx_payload = {
                "account_id": default_account_id,
                "asset_id": asset_obj["id"],
                "transaction_type": tx_type,
                "executed_at": datetime.utcnow().isoformat(),
                "quantity": quantity,
                "price": price,
                "currency": currency,
                "fee": round(calculated_fee_amount, 2),
                "fx_rate": ccl_rate,
                "fx_rate_type": "CCL",
                "notes": notes or f"{asset_class_choice} ({fee_percentage}% comisión)"
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
    with st.spinner("Sincronizando Dólar, Activos, Merval, CEDEARs y Cripto..."):
        post_api("/market-data/sync/dolar", {})
        fetch_api("/market-data/merval-panel?force_refresh=true")
        fetch_api("/market-data/cedears-panel?force_refresh=true")
        fetch_api("/market-data/crypto-panel?force_refresh=true")
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
# DASHBOARD PRINCIPAL: MÉTRICAS CLAVE (KPIs BLINDADOS CONTRA STRINGS)
# ==============================================================================
ccl_rate_used = safe_float(valuation_data.get("fx_rate_applied"), 1250.0)

if is_usd:
    total_val = safe_float(valuation_data.get("total_value_usd"))
    total_cost = safe_float(valuation_data.get("total_cost_usd"))
    total_pnl = safe_float(valuation_data.get("total_pnl_usd"))
    pnl_pct = safe_float(valuation_data.get("total_pnl_pct_usd"))
    currency_symbol = "USD $"
else:
    total_val = safe_float(valuation_data.get("total_value_ars"))
    total_cost = safe_float(valuation_data.get("total_cost_ars"))
    total_pnl = safe_float(valuation_data.get("total_pnl_ars"))
    pnl_pct = safe_float(valuation_data.get("total_pnl_pct_ars"))
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
        value=f"ARS ${ccl_rate_used:,.2f}",
        help="Tipo de cambio financiero aplicado para la conversión bimonetaria."
    )

# Banner explicativo de Aislamiento de Ilusión Monetaria
pnl_usd_pct = safe_float(valuation_data.get("total_pnl_pct_usd"))
pnl_ars_pct = safe_float(valuation_data.get("total_pnl_pct_ars"))

st.info(
    f"💡 **Análisis de Rendimiento Real vs Nominal:** "
    f"En **moneda dura (USD)** tu cartera rinde **{pnl_usd_pct:+.2f}%**, mientras que en **pesos (ARS)** la ganancia aparente es de **{pnl_ars_pct:+.2f}%**. "
    f"La diferencia de **{abs(pnl_ars_pct - pnl_usd_pct):.2f}%** corresponde al efecto de la devaluación cambiaria del ARS."
)


# ==============================================================================
# PESTAÑAS (TABS) DE NAVEGACIÓN
# ==============================================================================
tab_main, tab_merval, tab_cedears, tab_crypto, tab_dolar, tab_transactions, tab_risk = st.tabs([
    "📊 Mi Cartera & Tenencias",
    "🏛️ Panel Acciones Merval",
    "🌎 Panel CEDEARs",
    "🪙 Criptomonedas (BTC, ETH, SOL)",
    "💵 Dólar en Tiempo Real",
    "📜 Historial de Operaciones",
    "⚡ Gestión de Riesgo (Futuros)"
])


# ------------------------------------------------------------------------------
# TAB 1: MI CARTERA, COMPOSICIÓN (TORTA) Y DETALLE DE TENENCIAS CON FILTRO
# ------------------------------------------------------------------------------
with tab_main:
    raw_holdings = valuation_data.get("holdings", [])

    if raw_holdings:
        # Normalizar datos de tenencias a floats limpios
        processed_holdings = []
        for h in raw_holdings:
            item = dict(h)
            item["quantity"] = safe_float(item.get("quantity"))
            item["latest_unit_price"] = safe_float(item.get("latest_unit_price"))
            item["current_value_usd"] = safe_float(item.get("current_value_usd"))
            item["cost_basis_usd"] = safe_float(item.get("cost_basis_usd"))
            item["unrealized_pnl_usd"] = safe_float(item.get("unrealized_pnl_usd"))
            item["pnl_pct_usd"] = safe_float(item.get("pnl_pct_usd"))
            item["current_value_ars"] = safe_float(item.get("current_value_ars"))
            item["cost_basis_ars"] = safe_float(item.get("cost_basis_ars"))
            item["unrealized_pnl_ars"] = safe_float(item.get("unrealized_pnl_ars"))
            item["pnl_pct_ars"] = safe_float(item.get("pnl_pct_ars"))
            
            # Mapeo amigable de clase
            class_map = {
                "EQUITY_LOCAL": "Acciones Merval",
                "CEDEAR": "CEDEARs",
                "SOVEREIGN_BOND": "Bonos Soberanos",
                "CRYPTO_SPOT": "Criptomonedas",
                "CRYPTO_FUTURES": "Futuros Cripto",
                "CASH": "Liquidez / Efectivo"
            }
            raw_class = str(item.get("asset_class", ""))
            item["clase_display"] = class_map.get(raw_class, raw_class)
            processed_holdings.append(item)

        df_all = pd.DataFrame(processed_holdings)
        val_col = "current_value_usd" if is_usd else "current_value_ars"
        pnl_col = "unrealized_pnl_usd" if is_usd else "unrealized_pnl_ars"
        cost_col = "cost_basis_usd" if is_usd else "cost_basis_ars"
        pct_col = "pnl_pct_usd" if is_usd else "pnl_pct_ars"

        # ----------------------------------------------------------------------
        # GRÁFICO DE TORTA / COMPOSICIÓN DE ACTIVOS EN TENENCIA
        # ----------------------------------------------------------------------
        col_pie, col_pnl_bar = st.columns([1, 1])

        with col_pie:
            st.subheader("🥧 Distribución de Activos en Tenencia")
            pie_mode = st.radio(
                "Agrupar gráfico de torta por:",
                options=["Activo Individual (Ticker)", "Clase de Instrumento"],
                horizontal=True,
                index=0
            )

            group_field = "ticker" if pie_mode == "Activo Individual (Ticker)" else "clase_display"
            fig_pie = px.pie(
                df_all,
                names=group_field,
                values=val_col,
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Prism,
            )
            fig_pie.update_traces(
                textposition="inside",
                textinfo="percent+label",
                hovertemplate="<b>%{label}</b><br>Valor: " + ("USD $" if is_usd else "ARS $") + "%{value:,.2f}<br>Porcentaje: %{percent:.1%}"
            )
            fig_pie.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=340)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_pnl_bar:
            st.subheader("📊 Rendimiento P&L por Activo")
            df_all["Resultado"] = df_all[pnl_col].apply(lambda x: "Ganancia" if x >= 0 else "Pérdida")
            fig_bar = px.bar(
                df_all,
                x="ticker",
                y=pnl_col,
                color="Resultado",
                color_discrete_map={"Ganancia": "#00C853", "Pérdida": "#D50000"},
                labels={"ticker": "Activo", pnl_col: f"P&L ({currency_symbol})"},
            )
            fig_bar.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=340, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")

        # ----------------------------------------------------------------------
        # DETALLE DE TODAS LAS TENENCIAS CON FILTRO POR CLASE
        # ----------------------------------------------------------------------
        col_h_title, col_h_filter = st.columns([2, 1])
        with col_h_title:
            st.subheader("📋 Detalle Completo de Posiciones en Cartera")
        with col_h_filter:
            category_filter = st.selectbox(
                "Filtrar por tipo de activo:",
                options=["Todos los Activos", "CEDEARs", "Acciones Merval", "Bonos Soberanos", "Criptomonedas"],
                index=0
            )

        if category_filter != "Todos los Activos":
            df_filtered = df_all[df_all["clase_display"] == category_filter].copy()
        else:
            df_filtered = df_all.copy()

        if not df_filtered.empty:
            display_df = df_filtered[[
                "ticker", "name", "clase_display", "quantity", "latest_unit_price", "quote_currency",
                val_col, cost_col, pnl_col, pct_col
            ]].copy()

            display_df.columns = [
                "Ticker", "Nombre", "Clase", "Cantidad", "Últ. Cotización", "Moneda",
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
            st.info(f"No posees tenencias activas en la categoría '{category_filter}'.")

    else:
        st.info("No hay tenencias abiertas en esta cartera. Utiliza el formulario lateral para cargar tu primera compra.")


# ------------------------------------------------------------------------------
# TAB 2: PANEL GENERAL DE ACCIONES DEL MERVAL (EN VIVO - CADA 5 MINUTOS)
# ------------------------------------------------------------------------------
with tab_merval:
    st.subheader("🏛️ Panel Líder S&P Merval (Acciones Argentinas)")
    st.caption("Cotizaciones del mercado local actualizadas automáticamente cada 5 minutos vía Yahoo Finance.")

    merval_data = fetch_api("/market-data/merval-panel")

    if merval_data:
        df_merval = pd.DataFrame(merval_data)

        # KPIs rápidos del Merval
        df_merval["change_pct_num"] = df_merval["change_pct"].apply(safe_float)
        top_gainer = df_merval.sort_values(by="change_pct_num", ascending=False).iloc[0]
        top_loser = df_merval.sort_values(by="change_pct_num", ascending=True).iloc[0]

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Total Acciones Seguidas", f"{len(df_merval)} empresas")
        with col_m2:
            st.metric(
                "Mayor Alza del Día",
                f"{top_gainer['symbol']} ${safe_float(top_gainer['current_price']):,.2f}",
                delta=f"{safe_float(top_gainer['change_pct']):+.2f}%"
            )
        with col_m3:
            st.metric(
                "Mayor Baja del Día",
                f"{top_loser['symbol']} ${safe_float(top_loser['current_price']):,.2f}",
                delta=f"{safe_float(top_loser['change_pct']):+.2f}%",
                delta_color="inverse"
            )

        # Buscador por ticker o empresa
        search_merval = st.text_input("🔍 Buscar en el panel Merval:", placeholder="Ej: GGAL, YPFD, PAMP...").strip().upper()
        if search_merval:
            df_merval = df_merval[
                df_merval["symbol"].str.contains(search_merval) |
                df_merval["name"].str.upper().str.contains(search_merval)
            ]

        # Tabla completa formateada
        df_merval_display = df_merval[[
            "symbol", "name", "current_price", "change_pct", "open_price", "previous_close", "high_price", "low_price"
        ]].copy()

        df_merval_display.columns = [
            "Ticker", "Empresa", "Precio Actual (ARS)", "Var. Diaria (%)",
            "Apertura (ARS)", "Cierre Anterior (ARS)", "Máx Día", "Mín Día"
        ]

        st.dataframe(
            df_merval_display.style.format({
                "Precio Actual (ARS)": "${:,.2f}",
                "Var. Diaria (%)": "{:+.2f}%",
                "Apertura (ARS)": "${:,.2f}",
                "Cierre Anterior (ARS)": "${:,.2f}",
                "Máx Día": "${:,.2f}",
                "Mín Día": "${:,.2f}",
            }),
            use_container_width=True
        )
    else:
        st.warning("No se pudieron obtener cotizaciones del panel Merval en este momento.")
        if st.button("Reintentar descarga de Merval"):
            fetch_api("/market-data/merval-panel?force_refresh=true")
            st.rerun()


# ------------------------------------------------------------------------------
# TAB 3: PANEL GENERAL DE CEDEARS (ByMA)
# ------------------------------------------------------------------------------
with tab_cedears:
    st.subheader("🌎 Panel de Principales CEDEARs (ByMA)")
    st.caption("Cotizaciones de las empresas y ETFs internacionales más operados en Argentina en pesos (ARS), actualizadas cada 5 minutos.")

    cedears_data = fetch_api("/market-data/cedears-panel")

    if cedears_data:
        df_cedears = pd.DataFrame(cedears_data)

        # KPIs rápidos de CEDEARs
        df_cedears["change_pct_num"] = df_cedears["change_pct"].apply(safe_float)
        top_gainer_ced = df_cedears.sort_values(by="change_pct_num", ascending=False).iloc[0]
        top_loser_ced = df_cedears.sort_values(by="change_pct_num", ascending=True).iloc[0]

        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            st.metric("Total CEDEARs Seguidos", f"{len(df_cedears)} activos")
        with col_c2:
            st.metric(
                "Mayor Alza del Día",
                f"{top_gainer_ced['symbol']} ${safe_float(top_gainer_ced['current_price']):,.2f}",
                delta=f"{safe_float(top_gainer_ced['change_pct']):+.2f}%"
            )
        with col_c3:
            st.metric(
                "Mayor Baja del Día",
                f"{top_loser_ced['symbol']} ${safe_float(top_loser_ced['current_price']):,.2f}",
                delta=f"{safe_float(top_loser_ced['change_pct']):+.2f}%",
                delta_color="inverse"
            )

        # Buscador por ticker o empresa
        search_ced = st.text_input("🔍 Buscar en el panel CEDEARs:", placeholder="Ej: AAPL, NVDA, SPY, MELI, TSLA, BABA...").strip().upper()
        if search_ced:
            df_cedears = df_cedears[
                df_cedears["symbol"].str.contains(search_ced) |
                df_cedears["name"].str.upper().str.contains(search_ced)
            ]

        # Tabla completa formateada
        df_cedears_display = df_cedears[[
            "symbol", "name", "current_price", "change_pct", "open_price", "previous_close", "high_price", "low_price"
        ]].copy()

        df_cedears_display.columns = [
            "Ticker", "Empresa / ETF", "Precio Actual (ARS)", "Var. Diaria (%)",
            "Apertura (ARS)", "Cierre Anterior (ARS)", "Máx Día", "Mín Día"
        ]

        st.dataframe(
            df_cedears_display.style.format({
                "Precio Actual (ARS)": "${:,.2f}",
                "Var. Diaria (%)": "{:+.2f}%",
                "Apertura (ARS)": "${:,.2f}",
                "Cierre Anterior (ARS)": "${:,.2f}",
                "Máx Día": "${:,.2f}",
                "Mín Día": "${:,.2f}",
            }),
            use_container_width=True
        )
    else:
        st.warning("No se pudieron obtener cotizaciones del panel CEDEARs en este momento.")
        if st.button("Reintentar descarga de CEDEARs"):
            fetch_api("/market-data/cedears-panel?force_refresh=true")
            st.rerun()


# ------------------------------------------------------------------------------
# TAB 4: CRIPTOMONEDAS PRINCIPALES (BITCOIN, ETHEREUM, SOLANA)
# ------------------------------------------------------------------------------
with tab_crypto:
    st.subheader("🪙 Criptomonedas Principales (Bitcoin, Ethereum, Solana)")
    st.caption("Cotizaciones 24/7 en USD y convertidas en tiempo real a Pesos Argentinos (ARS) mediante el Dólar CCL de referencia.")

    crypto_data = fetch_api("/market-data/crypto-panel")

    if crypto_data:
        # Tarjetas destacadas en 3 columnas (BTC, ETH, SOL)
        cols_cry = st.columns(len(crypto_data))
        for idx, coin in enumerate(crypto_data):
            symbol = coin.get("symbol", "")
            name = coin.get("name", "")
            p_usd = safe_float(coin.get("current_price"))
            p_ars = p_usd * ccl_rate_used
            chg = safe_float(coin.get("change_pct"))
            hi_usd = safe_float(coin.get("high_price"))
            lo_usd = safe_float(coin.get("low_price"))

            icon = "₿" if symbol == "BTC" else ("Ξ" if symbol == "ETH" else "◎")

            with cols_cry[idx]:
                st.markdown(f"### {icon} {name} ({symbol})")
                st.metric(
                    label="Precio Actual (USD)",
                    value=f"${p_usd:,.2f} USD",
                    delta=f"{chg:+.2f}% (24h)"
                )
                st.caption(f"💵 Equivalente en ARS: **${p_ars:,.2f}** (CCL: ${ccl_rate_used:,.2f})")
                st.markdown(f"<small>Rango 24h: <b>${lo_usd:,.2f}</b> - <b>${hi_usd:,.2f}</b></small>", unsafe_allow_html=True)

        st.markdown("---")

        # Gráfico comparativo de variación 24h y Tabla Comparativa
        df_cry = pd.DataFrame(crypto_data)
        df_cry["change_pct_num"] = df_cry["change_pct"].apply(safe_float)
        df_cry["Color"] = df_cry["change_pct_num"].apply(lambda x: "Alza" if x >= 0 else "Baja")

        col_g1, col_g2 = st.columns([1, 1])
        with col_g1:
            st.subheader("📊 Variación en 24 Horas (%)")
            fig_cry_bar = px.bar(
                df_cry,
                x="symbol",
                y="change_pct_num",
                color="Color",
                color_discrete_map={"Alza": "#00C853", "Baja": "#D50000"},
                labels={"symbol": "Criptomoneda", "change_pct_num": "Variación 24h (%)"},
                text="change_pct_num"
            )
            fig_cry_bar.update_traces(texttemplate='%{text:+.2f}%', textposition='outside')
            fig_cry_bar.update_layout(height=350, showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_cry_bar, use_container_width=True)

        with col_g2:
            st.subheader("📋 Tabla Comparativa Cripto")
            df_cry_disp = df_cry.copy()
            df_cry_disp["precio_ars"] = df_cry_disp["current_price"].apply(safe_float) * ccl_rate_used
            
            df_disp = df_cry_disp[[
                "symbol", "name", "current_price", "precio_ars", "change_pct", "open_price", "previous_close", "high_price", "low_price"
            ]].copy()
            df_disp.columns = [
                "Símbolo", "Nombre", "Precio (USD)", "Precio (ARS)", "Var. 24h (%)",
                "Apertura (USD)", "Cierre Ant. (USD)", "Máx 24h", "Mín 24h"
            ]
            st.dataframe(
                df_disp.style.format({
                    "Precio (USD)": "${:,.2f}",
                    "Precio (ARS)": "${:,.2f}",
                    "Var. 24h (%)": "{:+.2f}%",
                    "Apertura (USD)": "${:,.2f}",
                    "Cierre Ant. (USD)": "${:,.2f}",
                    "Máx 24h": "${:,.2f}",
                    "Mín 24h": "${:,.2f}",
                }),
                use_container_width=True
            )
    else:
        st.warning("No se pudieron obtener cotizaciones cripto en este momento.")
        if st.button("Reintentar descarga de Criptomonedas"):
            fetch_api("/market-data/crypto-panel?force_refresh=true")
            st.rerun()


# ------------------------------------------------------------------------------
# TAB 5: DÓLAR EN TIEMPO REAL
# ------------------------------------------------------------------------------
with tab_dolar:
    st.subheader("💵 Cotizaciones del Dólar Financiero & Libre")
    st.caption("Consumido en tiempo real desde DolarApi / Backend")

    dolar_rates = fetch_api("/market-data/dolar/latest")

    if dolar_rates:
        cols_fx = st.columns(len(dolar_rates))
        for idx, rate in enumerate(dolar_rates):
            r_type = rate.get("rate_type", "")
            v_sell = safe_float(rate.get("sell_price"))
            v_buy = safe_float(rate.get("buy_price")) if rate.get("buy_price") else None
            
            with cols_fx[idx]:
                st.markdown(f"### Dólar {r_type}")
                st.metric(
                    label="Venta",
                    value=f"${v_sell:,.2f}",
                    delta=f"Compra: ${v_buy:,.2f}" if v_buy else "Único"
                )
                st.caption(f"Fuente: `{rate.get('source')}`")

        df_fx = pd.DataFrame(dolar_rates)
        df_fx["sell_price"] = df_fx["sell_price"].apply(safe_float)
        
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
        fig_fx.update_layout(height=380, showlegend=False)
        st.plotly_chart(fig_fx, use_container_width=True)
    else:
        st.warning("No se encontraron tipos de cambio registrados.")
        if st.button("Sincronizar Dólar ahora"):
            post_api("/market-data/sync/dolar", {})
            st.rerun()


# ------------------------------------------------------------------------------
# TAB 4: HISTORIAL DE TRANSACCIONES (LEDGER)
# ------------------------------------------------------------------------------
with tab_transactions:
    st.subheader("📜 Libro Contable de Movimientos")
    tx_list = fetch_api("/transactions/")

    if tx_list:
        df_tx = pd.DataFrame(tx_list)
        df_tx_display = df_tx[[
            "id", "executed_at", "transaction_type", "asset_id",
            "quantity", "price", "currency", "fee", "fx_rate", "net_amount", "notes"
        ]].copy()
        
        df_tx_display["executed_at"] = pd.to_datetime(df_tx_display["executed_at"]).dt.strftime("%Y-%m-%d %H:%M")
        df_tx_display["quantity"] = df_tx_display["quantity"].apply(safe_float)
        df_tx_display["price"] = df_tx_display["price"].apply(safe_float)
        df_tx_display["fee"] = df_tx_display["fee"].apply(safe_float)
        df_tx_display["fx_rate"] = df_tx_display["fx_rate"].apply(safe_float)
        df_tx_display["net_amount"] = df_tx_display["net_amount"].apply(safe_float)

        df_tx_display.columns = [
            "ID", "Fecha Ejecución", "Tipo", "ID Activo", "Cantidad",
            "Precio Unitario", "Moneda", "Comisión Pagada", "TC Aplicado (CCL)", "Monto Neto", "Notas"
        ]

        st.dataframe(
            df_tx_display.style.format({
                "Cantidad": "{:,.4f}",
                "Precio Unitario": "{:,.2f}",
                "Comisión Pagada": "{:,.2f}",
                "TC Aplicado (CCL)": "${:,.2f}",
                "Monto Neto": "{:,.2f}",
            }),
            use_container_width=True
        )
    else:
        st.info("No hay transacciones registradas todavía.")


# ------------------------------------------------------------------------------
# TAB 5: GESTIÓN DE RIESGO (FUTUROS CRIPTO)
# ------------------------------------------------------------------------------
with tab_risk:
    st.subheader("⚡ Supervisión de Posiciones de Futuros & Margen")
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
                        st.metric("Precio de Entrada", f"${safe_float(risk_status['entry_price']):,.2f}")
                    with col_r2:
                        st.metric("Precio Actual", f"${safe_float(risk_status['current_price']):,.2f}")
                    with col_r3:
                        st.metric("Precio de Liquidación", f"${safe_float(risk_status['liquidation_price']):,.2f}")
                    with col_r4:
                        dist_liq = safe_float(risk_status["distance_to_liquidation_pct"])
                        risk_level = risk_status["risk_level"]
                        delta_color = "normal" if dist_liq > 15 else "inverse"
                        st.metric("Distancia a Liquidación", f"{dist_liq:.2f}%", delta=risk_level, delta_color=delta_color)

                    buffer_pct = min(max(dist_liq, 0.0), 100.0)
                    st.progress(buffer_pct / 100.0, text=f"Buffer de Seguridad de Margen: {buffer_pct:.1f}%")
                    
                    st.caption(
                        f"🛡️ **Take-Profit:** ${risk_status.get('take_profit_price') or 'No fijado'} | "
                        f"🛑 **Stop-Loss:** ${risk_status.get('stop_loss_price') or 'No fijado'} | "
                        f"💰 **PnL No Realizado:** ${safe_float(risk_status['unrealized_pnl_usd']):+,.2f} USD"
                    )
    else:
        st.info("No hay posiciones abiertas en contratos de futuros cripto.")
