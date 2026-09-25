# Edu CRM

Ta’lim markazlarini boshqarish uchun React/Vite frontend va FastAPI backend.

## Ishga tushirish

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

`DATABASE_URL` orqali PostgreSQL ulanmasini belgilang. `.env` bo‘lmasa, lokal sinov uchun SQLite ishlatiladi. Ilk ishga tushishda super admin yaratiladi: `admin@educrm.uz` / `Admin123!` — ishlab chiqarishda darhol almashtiring.

Swagger: http://localhost:8000/docs  
ReDoc: http://localhost:8000/redoc

### Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Frontend: http://localhost:5173

### Test

```powershell
cd backend
pytest
```

## Arxitektura

Backend JWT autentifikatsiya, role-based ruxsatlar, Pydantic validatsiya va FastAPI OpenAPI hujjatlarini beradi. Moliyaviy summalar `Decimal/Numeric` orqali saqlanadi. Frontend API bilan Axios orqali bog‘langan va o‘zbekcha, responsive dashboardga ega.
