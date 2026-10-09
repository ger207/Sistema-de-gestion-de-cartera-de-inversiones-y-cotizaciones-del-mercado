# Gestor de Carteras & Riesgo Bimonetario (USD / ARS)

Sistema automatizado de seguimiento de carteras de inversión y gestión de riesgo financiero bimonetario para el mercado argentino (Acciones Merval, CEDEARs, Bonos Soberanos) y Criptomonedas (Spot y Futuros).

## 🚀 Arquitectura y Tecnologías
- **Framework Web**: [FastAPI](https://fastapi.tiangolo.com/)
- **ORM & Migraciones**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) + [Alembic](https://alembic.sqlalchemy.org/)
- **Base de Datos**: SQLite (desarrollo local / MVP sin fricción) con compatibilidad total para migración a PostgreSQL.
- **Cotizaciones Automáticas**: 
  - Yahoo Finance (`yfinance`) para activos locales (`.BA`), CEDEARs y Cripto (`BTC-USD`).
  - [DolarApi](https://dolarapi.com/) para cotizaciones del Dólar CCL, MEP, Oficial y Cripto.

## 📁 Estructura del Proyecto
```
backend/
├── alembic/                 # Control de versiones de base de datos
│   ├── versions/
│   └── env.py
├── app/
│   ├── core/               # Configuraciones globales y conexión a BD
│   │   ├── config.py
│   │   └── database.py
│   ├── models/             # Modelos relacionales SQLAlchemy 2.0
│   │   ├── asset.py        # Activos (Merval, CEDEARs, Bonos, Cripto)
│   │   ├── portfolio.py    # Carteras y Cuentas de custodia
│   │   ├── transaction.py  # Libro contable / Ledger inmutable
│   │   ├── market_data.py  # Cotizaciones históricas y tipos de cambio FX
│   │   ├── risk.py         # Derivados cripto y métricas de riesgo
│   │   └── enums.py        # Enums de dominio
│   ├── schemas/            # Esquemas Pydantic v2 para validación
│   ├── services/           # Lógica de negocio (market data, PnL, riesgo)
│   ├── api/                # Endpoints REST (FastAPI)
│   └── main.py             # Entrada de la aplicación
├── requirements.txt
├── alembic.ini
└── .env
```

## 🛠️ Instalación y Puesta en Marcha

1. **Crear entorno virtual e instalar dependencias:**
   ```bash
   cd backend
   python -m venv .venv
   .\.venv\Scripts\activate   # En Windows
   pip install -r requirements.txt
   ```

2. **Ejecutar migraciones de base de datos:**
   ```bash
   alembic upgrade head
   ```

3. **Iniciar el servidor de desarrollo:**
   ```bash
   uvicorn app.main:app --reload
   ```
   Acceder a la documentación Swagger interactiva en: [http://localhost:8000/docs](http://localhost:8000/docs)
