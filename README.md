# 📈 Sistema de Gestión de Cartera de Inversiones y Cotizaciones de Mercado

Plataforma integral y automatizada para el seguimiento de carteras de inversión bimonetarias (**USD / ARS**), análisis de rendimientos reales (*Mark-to-Market* y P&L realizado/no realizado), cotizaciones en tiempo real del mercado argentino y criptomonedas, y gestión cuantitativa de riesgo en derivados (futuros apalancados).

---

## 🚀 Características Principales

- **Gestión Multi-Cartera:** Creación, selección y eliminación de múltiples carteras independientes con aislamiento de balances y rendimientos.
- **Valuación Bimonetaria y Aislamiento de Ilusión Monetaria:** Monitoreo simultáneo en Pesos Argentinos (ARS) y Dólar CCL/MEP (USD), distinguiendo ganancias nominales de ganancias reales en moneda dura.
- **Registro Inteligente de Operaciones:** 
  - Detección automática de tipo de instrumento (CEDEAR, Acción Merval, Bono Soberano o Criptomoneda) al escribir el ticker.
  - Cálculo automático de comisiones de broker (%) y subtotales netos.
  - Reset automático de campos tras registrar cada orden.
- **Desglose de Rendimiento Total:** Cálculo preciso acumulado de P&L realizado (ventas históricas) y P&L no realizado (tenencias abiertas con Precio Promedio Ponderado - PPP).
- **Cotizaciones en Tiempo Real (Sincronización cada 5 min):**
  - **Dólar:** CCL, MEP, Blue, Oficial y Cripto (vía DolarApi).
  - **Mercado Local:** Acciones del Panel Líder de BYMA / Merval.
  - **CEDEARs:** Cotizaciones de empresas y ETFs internacionales negociados en pesos.
  - **Cripto:** BTC, ETH y SOL cotizadas 24/7 en USD y convertidas al CCL.
- **Simulador Cuantitativo de Riesgo de Futuros (BTC):**
  - Cálculo de valor nocional, precio de liquidación estimado y margen de mantenimiento (MMR).
  - Validación de Stop-Loss contra el precio de liquidación para mitigar pérdidas forzosas.
  - Tabla de sensibilidad por niveles de apalancamiento (2x a 50x).

---

## 🛠️ Stack Tecnológico

- **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+) con arquitectura modular y validación de datos mediante [Pydantic v2](https://docs.pydantic.dev/).
- **Base de Datos & ORM:** [SQLAlchemy 2.0](https://www.sqlalchemy.org/) con migraciones controladas por [Alembic](https://alembic.sqlalchemy.org/) (SQLite por defecto, portable a PostgreSQL).
- **Frontend / Dashboard:** [Streamlit](https://streamlit.io/) y visualizaciones interactivas con [Plotly](https://plotly.com/python/).
- **Proveedores de Datos Financieros:**
  - `yfinance` para cotizaciones bursátiles y criptomonedas.
  - `DolarApi` para tipos de cambio financieros de Argentina.
  - `APScheduler` para tareas periódicas en segundo plano.

---

## 📁 Estructura del Repositorio

```text
├── backend/
│   ├── alembic/                 # Migraciones de base de datos
│   ├── app/
│   │   ├── api/v1/endpoints/   # Endpoints REST (portfolios, transactions, market data, risk)
│   │   ├── core/               # Configuración global y sesiones de base de datos
│   │   ├── models/             # Modelos relacionales ORM (Portfolio, Account, Asset, Transaction, Risk)
│   │   ├── schemas/            # Esquemas Pydantic v2
│   │   └── services/           # Lógica financiera, valuación bimonetaria y scheduler
│   ├── main.py                 # Punto de entrada de la API FastAPI
│   └── requirements.txt        # Dependencias del backend
├── app_visual.py               # Aplicación interactiva frontend en Streamlit
├── .gitignore
└── README.md
```

---

## ⚙️ Instalación y Puesta en Marcha

### 1. Clonar el repositorio
```bash
git clone https://github.com/ger207/Sistema-de-gestion-de-cartera-de-inversiones-y-cotizaciones-del-mercado.git
cd Sistema-de-gestion-de-cartera-de-inversiones-y-cotizaciones-del-mercado
```

### 2. Configurar el entorno virtual e instalar dependencias
```bash
cd backend
python -m venv .venv

# Activar en Windows:
.\.venv\Scripts\activate
# O en Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Ejecutar migraciones de la base de datos
```bash
alembic upgrade head
```

### 4. Iniciar el Backend (FastAPI)
Desde la carpeta `backend`:
```bash
uvicorn app.main:app --reload --port 8000
```
> La documentación interactiva Swagger estará disponible en: [http://localhost:8000/docs](http://localhost:8000/docs)

### 5. Iniciar la Interfaz de Usuario (Streamlit)
En una segunda terminal (con el entorno virtual activado):
```bash
streamlit run app_visual.py
```
> La aplicación web se abrirá automáticamente en: [http://localhost:8501](http://localhost:8501)
