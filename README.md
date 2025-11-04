# 🔥 SCRAPPER TEAM REDCARDS v5.0 ELITE

Proyecto refactorizado con arquitectura profesional de 5 capas.

## 📦 CONTENIDO

- app.py - Aplicación principal (Flask + Telethon)
- config.py - Configuración centralizada
- database.py - Gestión SQLite + LIVES JSON
- auth.py - Autenticación + brute force
- scraper.py - Loop automático de CCs
- telegram_handler.py - Manejador de eventos
- utils.py - Funciones utilitarias
- requirements.txt - Dependencias
- Procfile, runtime.txt - Railway
- .env.example - Variables de entorno

## 🚀 SETUP RÁPIDO

### Local
```bash
pip install -r requirements.txt
cp .env.example .env
python app.py
```

### Railway
```bash
git init && git add .
git commit -m "Scrapper v5 Elite"
# Conectar a Railway
```

## 👤 CREDENCIALES DEFAULT

Usuario: `admin`
Contraseña: `ChangeMe123!@#`

⚠️ CAMBIAR EN PRODUCCIÓN

## 🏗️ ARQUITECTURA 5 CAPAS

1. **Autenticación Web VIP** - Login + brute force
2. **Telethon Integration** - Cliente Telegram
3. **Automatización de CCs** - Envío automático
4. **Detección de LIVES** - Captura respuestas
5. **Persistencia de Datos** - SQLite + JSON

## ✅ CARACTERÍSTICAS

✅ Login VIP con protección brute force
✅ Sesiones seguras (PBKDF2 + Tokens)
✅ Base de datos SQLite completa
✅ Telethon en background
✅ Generación de variantes con Luhn válido
✅ Detector de LIVES en tiempo real
✅ Dashboard interactivo
✅ API REST completa
✅ Despliegue Railway ready

---
Scrapper Team RedCards v5.0 Elite © 2025
