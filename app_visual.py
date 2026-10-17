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
from typing import Any, Optional, Tuple

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
    /* Evitar que los números de las métricas se corten con '...' y permitir ancho completo */
    [data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
    }
    [data-testid="stMetricValue"] > div {
        font-size: 1.35rem !important;
        white-space: normal !important;
        word-break: normal !important;
        text-overflow: unset !important;
        overflow: visible !important;
    }
    [data-testid="stMetricLabel"] {
        white-space: normal !important;
        font-size: 0.85rem !important;
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
# MOTOR INTELIGENTE DE AUTODETECCIÓN DE INSTRUMENTO
# ==============================================================================
def auto_detect_instrument(raw_ticker: str, existing_assets: list) -> Tuple[str, str, str, str, str]:
    """
    Analiza el ticker ingresado por el usuario y detecta automáticamente:
    (ticker_normalizado, nombre_descriptivo, clase_activo, moneda_sugerida, etiqueta_visual).
    """
    clean = raw_ticker.strip().upper()
    if not clean:
        return "", "", "EQUITY_LOCAL", "ARS", "Sin Ticker"

    clean_no_ba = clean.replace(".BA", "")

    # 1. Verificar si ya existe en el catálogo registrado de la base de datos
    for a in existing_assets:
        t_exist = a.get("ticker", "").upper()
        if t_exist == clean or t_exist == f"{clean}.BA" or t_exist == clean_no_ba:
            cls = a.get("asset_class", "EQUITY_LOCAL")
            curr = a.get("currency", "ARS")
            name = a.get("name", clean)
            display_map = {
                "EQUITY_LOCAL": "Acción Merval",
                "CEDEAR": "CEDEAR",
                "SOVEREIGN_BOND": "Bono Soberano",
                "CRYPTO_SPOT": "Criptomoneda",
                "CRYPTO_FUTURES": "Futuros Cripto",
            }
            return a["ticker"], name, cls, curr, display_map.get(cls, cls)

    # 2. Criptomonedas comunes
    CRYPTO_SET = {
        "BTC", "ETH", "SOL", "USDT", "BNB", "XRP", "ADA", "DOGE", "DOT", "AVAX",
        "LINK", "MATIC", "LTC", "DAI", "USDC", "PEPE", "SHIB", "NEAR", "RENDER"
    }
    if clean in CRYPTO_SET or clean.endswith("-USD") or clean.endswith("-USDT") or clean.endswith("USDT"):
        norm = clean if ("-" in clean or clean.endswith("USDT")) else f"{clean}-USD"
        return norm, f"{clean_no_ba}", "CRYPTO_SPOT", "USD", "Criptomoneda"

    # 3. Bonos Soberanos / Renta Fija (AL30, GD30, AE38, TX26, T2X5, BOPREAL, etc.)
    BOND_PREFIXES = ("AL", "GD", "AE", "TX", "T2X", "BP", "BOP", "TV", "S3", "S1", "TO", "DICP", "PARP")
    if clean.startswith(BOND_PREFIXES) and any(c.isdigit() for c in clean):
        norm = clean if clean.endswith(".BA") else f"{clean}.BA"
        return norm, f"Bono {clean_no_ba}", "SOVEREIGN_BOND", "ARS", "Bono Soberano"

    # 4. CEDEARs populares de ByMA
    CEDEARS_SET = {
        "SPY", "QQQ", "DIA", "AAPL", "NVDA", "TSLA", "MELI", "MSFT", "AMZN", "META", "GOOGL", "GOOG",
        "KO", "VIST", "BABA", "PBR", "BBD", "DISN", "DIS", "AMD", "VALE", "WMT", "XOM", "JNJ", "MCD",
        "GOLD", "GLOB", "DESP", "COIN", "PYPL", "NFLX", "INTC", "IBM", "BA", "CAT", "GE", "JPM", "BAC",
        "C", "V", "MA", "PEP", "PG", "UNH", "LLY", "NKE", "ORCL", "CSCO", "CRM", "UBER", "ABBV", "BIOX",
        "HMY", "PAAS", "AUY", "ARCOS", "TEN", "TX", "BBVA", "SAN", "ITUB", "IWM", "MO", "PM", "BIIB"
    }
    if clean_no_ba in CEDEARS_SET:
        norm = f"{clean_no_ba}.BA"
        return norm, f"{clean_no_ba}", "CEDEAR", "ARS", "CEDEAR"

    # 5. Acciones Líderes y del Panel General del Merval
    MERVAL_SET = {
        "GGAL", "YPFD", "PAMP", "BMA", "ALUA", "TXAR", "CRES", "EDN", "TGSU2", "TRAN", "CEPU", "LOMA",
        "VALO", "MIRG", "SUPV", "BYMA", "COME", "BBAR", "TECO2", "HARG", "AGRO", "AUSO", "BHIP", "BOLT",
        "BPAT", "CADO", "CAPX", "CARC", "CELU", "CGPA2", "CTIO", "DGCU2", "FERR", "GCLA", "GRIM", "HAVA",
        "INVJ", "IRSA", "LEDE", "LONG", "METR", "MOLI", "MORI", "OEST", "PATA", "POLL", "RIGO", "SAMI",
        "SEMI", "TGLT", "TGNO4"
    }
    if clean_no_ba in MERVAL_SET:
        norm = f"{clean_no_ba}.BA"
        return norm, f"{clean_no_ba}", "EQUITY_LOCAL", "ARS", "Acción Merval"

    # 6. Heurística general de contingencia
    if "-" in clean or "USD" in clean:
        return clean, f"{clean}", "CRYPTO_SPOT", "USD", "Criptomoneda"
    
    norm = clean if clean.endswith(".BA") else f"{clean}.BA"
    return norm, f"{clean_no_ba}", "EQUITY_LOCAL", "ARS", "Acción Merval"


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
existing_assets_cache = fetch_api("/assets/") or []


# ==============================================================================
# SIDEBAR: FORMULARIO INTELIGENTE DE TRANSACCIONES (AUTODETECCIÓN DE CLASE)
# ==============================================================================
st.sidebar.image("https://img.icons8.com/fluency/96/bullish.png", width=64)
st.sidebar.title("Gestión de Cartera")
st.sidebar.markdown(f"**Cartera Unificada:** `{active_portfolio['name']}`")
st.sidebar.caption("Todas las cuentas y activos consolidados.")
st.sidebar.markdown("---")

st.sidebar.subheader("➕ Nueva Operación")

with st.sidebar.form(key="transaction_form", clear_on_submit=False):
    # 1. Entrada inteligente de Ticker (SIN selector manual de clase)
    ticker_input = st.text_input(
        "Ticker / Símbolo:",
        placeholder="Ej: AAPL, GGAL, AL30, BTC...",
        help="Escribe el ticker. El sistema detectará automáticamente si es CEDEAR, Acción Merval, Bono o Cripto."
    ).strip().upper()

    # Detección automática en tiempo real
    normalized_ticker, detected_name, detected_class, default_currency, display_class = auto_detect_instrument(
        ticker_input, existing_assets_cache
    )

    if ticker_input:
        st.info(f"**Detectado:** {display_class}  \n**Ticker:** `{normalized_ticker}`")

    # 2. Tipo de Operación
    tx_type = st.selectbox(
        "Tipo de Operación:",
        options=["BUY", "SELL"],
        format_func=lambda x: "Compra (BUY)" if x == "BUY" else "Venta (SELL)"
    )
    
    col_q, col_p = st.columns(2)
    with col_q:
        quantity = st.number_input("Cantidad:", min_value=0.0, value=0.0, step=1.0, format="%.4f")
    with col_p:
        price = st.number_input("Precio Unitario:", min_value=0.0, value=0.0, step=100.0, format="%.2f")

    col_cur, col_fee_pct = st.columns(2)
    with col_cur:
        currency = st.selectbox(
            "Moneda:",
            options=["ARS", "USD", "USDT"],
            index=0 if default_currency == "ARS" else 1,
            help="Moneda en la que se pacta y liquida la transacción."
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
            help="Porcentaje de arancel cobrado por tu broker o exchange."
        )

    # Cálculo dinámico de subtotal y comisión
    gross_subtotal = quantity * price
    calculated_fee_amount = gross_subtotal * (fee_percentage / 100.0)
    estimated_net = (gross_subtotal + calculated_fee_amount) if tx_type == "BUY" else (gross_subtotal - calculated_fee_amount)

    # Mostrar desglose únicamente si hay un ticker ingresado y valores mayores a cero
    if ticker_input and quantity > 0 and price > 0:
        st.markdown(
            f"**Subtotal:** {currency} \\${gross_subtotal:,.2f}  \n"
            f"**Comisión ({fee_percentage:.2f}%):** {currency} \\${calculated_fee_amount:,.2f}  \n"
            f"**Total Estimado:** {currency} \\${estimated_net:,.2f}"
        )

    notes = st.text_input("Notas (Opcional):", placeholder="Ej: Compra mensual DCA")

    submit_button = st.form_submit_button("🚀 Registrar Transacción", use_container_width=True)

    if submit_button:
        if not ticker_input:
            st.sidebar.error("Debes ingresar un ticker válido.")
        elif quantity <= 0:
            st.sidebar.error("Debes ingresar una cantidad mayor a 0.")
        elif price <= 0:
            st.sidebar.error("Debes ingresar un precio unitario mayor a 0.")
        elif not default_account_id:
            st.sidebar.error("No se encontró una cuenta de custodia activa para registrar la operación.")
        else:
            # A. Asegurar existencia del activo en el catálogo
            asset_obj = next((a for a in existing_assets_cache if a["ticker"] == normalized_ticker), None)

            if not asset_obj:
                with st.spinner(f"Registrando {normalized_ticker} en el catálogo como {display_class}..."):
                    new_asset_payload = {
                        "ticker": normalized_ticker,
                        "name": detected_name or f"{ticker_input}",
                        "asset_class": detected_class,
                        "currency": currency,
                        "is_active": True
                    }
                    create_asset_res = post_api("/assets/", new_asset_payload)
                    if create_asset_res and create_asset_res.status_code in [200, 201]:
                        asset_obj = create_asset_res.json()
                    else:
                        st.sidebar.error("Error al registrar el activo en el catálogo.")
                        st.stop()

            # B. Obtener tipo de cambio CCL actual para imputar conversión histórica
            latest_ccl = fetch_api("/market-data/dolar/latest")
            ccl_rate = 1250.0
            if latest_ccl:
                ccl_item = next((r for r in latest_ccl if r.get("rate_type") == "CCL"), None)
                if ccl_item:
                    ccl_rate = safe_float(ccl_item.get("sell_price"), 1250.0)

            # C. Registrar transacción en el Ledger con la comisión en monto monetario calculada
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
                "notes": notes or f"{display_class} ({fee_percentage}% comisión)"
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
        st.sidebar.success("Mercado sincronizado con éxito.")
        st.rerun()

# Botón para descargar el PDF de documentación académica del proyecto
pdf_candidates = [
    os.path.join(os.path.dirname(__file__), "..", "Documento_Tecnico_Proyecto_Integrador.pdf"),
    os.path.join(os.path.dirname(__file__), "Documento_Tecnico_Proyecto_Integrador.pdf"),
    "Documento_Tecnico_Proyecto_Integrador.pdf"
]
pdf_file_path = next((p for p in pdf_candidates if os.path.exists(p)), None)
if pdf_file_path:
    with open(pdf_file_path, "rb") as pdf_file:
        st.sidebar.download_button(
            label="📄 Descargar Documentación (PDF)",
            data=pdf_file.read(),
            file_name="Documento_Tecnico_Proyecto_Integrador.pdf",
            mime="application/pdf",
            use_container_width=True
        )


# ==============================================================================
# CABECERA Y CONTROL DE MONEDA (TOGGLE ARS / USD)
# ==============================================================================
col_title, col_toggle = st.columns([3, 1])

with col_title:
    st.title("💼 Gestor de Carteras Bimonetarias")
    st.caption("Seguimiento automatizado en tiempo real | Aislamiento de ilusión monetaria")

with col_toggle:
    st.write("")
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


# ==============================================================================
# PESTAÑAS (TABS) DE NAVEGACIÓN
# ==============================================================================
tab_main, tab_quotes, tab_dolar, tab_transactions, tab_risk = st.tabs([
    "📊 Mi Cartera & Tenencias",
    "📈 Cotizaciones",
    "💵 Dólar en Tiempo Real",
    "📜 Historial de Operaciones",
    "⚡ Gestión de Riesgo (Futuros)"
])


# ------------------------------------------------------------------------------
# TAB 1: MI CARTERA, COMPOSICIÓN (TORTA) Y DETALLE DE TENENCIAS CON PPP
# ------------------------------------------------------------------------------
with tab_main:
    raw_holdings = valuation_data.get("holdings", [])

    if raw_holdings:
        # Normalizar datos de tenencias a floats limpios incluyendo Precio Promedio de Compra (PPP)
        processed_holdings = []
        for h in raw_holdings:
            item = dict(h)
            item["quantity"] = safe_float(item.get("quantity"))
            item["latest_unit_price"] = safe_float(item.get("latest_unit_price"))
            
            # PPP (Precio Promedio de Compra)
            item["avg_buy_price_usd"] = safe_float(item.get("avg_buy_price_usd"))
            item["avg_buy_price_ars"] = safe_float(item.get("avg_buy_price_ars"))

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
        avg_col = "avg_buy_price_usd" if is_usd else "avg_buy_price_ars"

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
        # DETALLE DE TODAS LAS TENENCIAS CON PRECIO PROMEDIO DE COMPRA (PPP)
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
                "ticker", "name", "clase_display", "quantity",
                avg_col, "latest_unit_price", "quote_currency",
                val_col, cost_col, pnl_col, pct_col
            ]].copy()

            display_df.columns = [
                "Ticker", "Nombre", "Clase", "Cantidad",
                f"Precio Prom. Compra ({'USD' if is_usd else 'ARS'})",
                "Últ. Cotización", "Moneda",
                f"Valor Actual ({'USD' if is_usd else 'ARS'})",
                f"Costo Base ({'USD' if is_usd else 'ARS'})",
                f"P&L ({'USD' if is_usd else 'ARS'})",
                "P&L (%)"
            ]

            st.dataframe(
                display_df.style.format({
                    "Cantidad": "{:,.4f}",
                    f"Precio Prom. Compra ({'USD' if is_usd else 'ARS'})": "{:,.2f}",
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
# TAB 2: COTIZACIONES GENERALES (DESPLEGABLE UNIFICADO)
# ------------------------------------------------------------------------------
with tab_quotes:
    col_q_title, col_q_select = st.columns([2, 1])
    with col_q_title:
        st.subheader("📈 Monitor General de Cotizaciones de Mercado")
        st.caption("Precios actualizados automáticamente cada 5 minutos vía Yahoo Finance.")
    with col_q_select:
        market_panel_choice = st.selectbox(
            "Seleccionar Panel de Mercado:",
            options=[
                "🏛️ Acciones Líderes (S&P Merval)",
                "🌎 Principales CEDEARs (ByMA)",
                "🪙 Criptomonedas (BTC, ETH, SOL)"
            ],
            index=0
        )

    st.markdown("---")

    # =========================================================================
    # VISTA 1: ACCIONES LÍDERES MERVAL
    # =========================================================================
    if market_panel_choice == "🏛️ Acciones Líderes (S&P Merval)":
        st.markdown("### 🏛️ Panel Líder S&P Merval (Acciones Argentinas)")
        st.caption("Cotizaciones del mercado local de acciones en pesos (ARS).")

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

    # =========================================================================
    # VISTA 2: PRINCIPALES CEDEARS
    # =========================================================================
    elif market_panel_choice == "🌎 Principales CEDEARs (ByMA)":
        st.markdown("### 🌎 Panel de Principales CEDEARs (ByMA)")
        st.caption("Cotizaciones de empresas y ETFs internacionales negociados en pesos (ARS).")

        cedears_data = fetch_api("/market-data/cedears-panel")

        if cedears_data:
            df_cedears = pd.DataFrame(cedears_data)

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

            search_ced = st.text_input("🔍 Buscar en el panel CEDEARs:", placeholder="Ej: AAPL, NVDA, SPY, MELI, TSLA, BABA...").strip().upper()
            if search_ced:
                df_cedears = df_cedears[
                    df_cedears["symbol"].str.contains(search_ced) |
                    df_cedears["name"].str.upper().str.contains(search_ced)
                ]

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

    # =========================================================================
    # VISTA 3: CRIPTOMONEDAS (BITCOIN, ETHEREUM, SOLANA)
    # =========================================================================
    elif market_panel_choice == "🪙 Criptomonedas (BTC, ETH, SOL)":
        st.markdown("### 🪙 Criptomonedas Principales (Bitcoin, Ethereum, Solana)")
        st.caption("Cotizaciones en tiempo real 24/7 en USD y convertidas a Pesos Argentinos (ARS) mediante el CCL.")

        crypto_data = fetch_api("/market-data/crypto-panel")

        if crypto_data:
            # Tarjetas destacadas para BTC, ETH, SOL
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

            st.markdown("---")

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
# TAB 3: DÓLAR EN TIEMPO REAL
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
