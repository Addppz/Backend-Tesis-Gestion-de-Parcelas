# Microservicio de Gestión de Parcelas

API REST construida con **FastAPI + SQLModel** para administrar parcelas agrícolas con compatibilidad nativa con el microservicio de imágenes satelitales Sentinel-2 (Delvis).

---

## Estructura del proyecto

```
Backend-Tesis-Gestion-de-Parcelas/
├── app/
│   ├── __init__.py
│   ├── main.py        # Punto de entrada FastAPI
│   ├── models.py      # Modelo SQLModel (tabla `parcelas`)
│   ├── schemas.py     # Schemas Pydantic con validaciones
│   ├── routers.py     # Endpoints REST
│   └── database.py    # Motor + sesión de BD
├── .env.example       # Plantilla de variables de entorno
├── requirements.txt
└── README.md
```

---

## Configuración

### 1. Crear entorno virtual e instalar dependencias

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar la conexión a Supabase

Copia `.env.example` a `.env` y rellena tu URL de conexión:

```powershell
Copy-Item .env.example .env
```

Edita `.env`:

```env
DATABASE_URL=postgresql://postgres:TU_PASSWORD@db.XXXXXXXXXX.supabase.co:5432/postgres
```

### 3. Arrancar el servidor

```powershell
uvicorn app.main:app --reload
```

El servicio estará disponible en `http://localhost:8000`.  
Documentación interactiva: `http://localhost:8000/docs`

---

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/` | Health check |
| `POST` | `/parcelas/` | Crear parcela (con validación de geometría) |
| `GET` | `/parcelas/` | Listar todas las parcelas |
| `GET` | `/parcelas/{id}/satelital` | Formato compatible con Delvis/Sentinel-2 |

---

## Formato de geometría (estándar Delvis)

```json
{
  "coordinates": [
    [-77.05, -12.05],
    [-77.04, -12.05],
    [-77.04, -12.04],
    [-77.05, -12.04],
    [-77.05, -12.05]
  ]
}
```

**Reglas de validación:**
- Debe contener la clave `coordinates`
- Mínimo **4 puntos** `[longitud, latitud]` en EPSG:4326 (WGS84)
- **Anillo cerrado**: el primer punto debe ser idéntico al último

### Ejemplo de request (POST /parcelas/)

```json
{
  "nombre": "Parcela Norte",
  "descripcion": "Parcela de maíz en la zona norte",
  "cultivo": "maíz",
  "geometria": {
    "coordinates": [
      [-77.05, -12.05],
      [-77.04, -12.05],
      [-77.04, -12.04],
      [-77.05, -12.04],
      [-77.05, -12.05]
    ]
  }
}
```

### Respuesta de GET /parcelas/{id}/satelital

```json
{
  "polygon": {
    "coordinates": [
      [-77.05, -12.05],
      [-77.04, -12.05],
      [-77.04, -12.04],
      [-77.05, -12.04],
      [-77.05, -12.05]
    ]
  }
}
```