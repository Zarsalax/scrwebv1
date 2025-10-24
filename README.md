# CC Checker Web - Bot de Telegram 24/7

Bot automatizado de Telegram con Flask que verifica tarjetas de crédito. Optimizado para Railway.app

## 🚀 Despliegue en Railway

1. **Conecta tu repositorio de GitHub a Railway**
   - Ve a [railway.app](https://railway.app)
   - Click en "New Project" → "Deploy from GitHub repo"
   - Selecciona este repositorio

2. **Configura Variables de Entorno** (Opcional)
   - `API_ID` - Tu API ID de Telegram (obtén en https://my.telegram.org)
   - `API_HASH` - Tu API Hash de Telegram
   - `CHANNEL_ID` - Canal de destino por defecto

3. **Railway detectará automáticamente:**
   - `Procfile` para iniciar la aplicación
   - `requirements.txt` para instalar dependencias
   - `runtime.txt` para la versión de Python

4. **Primera vez: Autenticación de Telegram**
   - Ejecuta localmente primero: `python app.py`
   - Se generará el archivo `session.session`
   - Súbelo manualmente a Railway (Files → Upload)

## 📋 Estructura

- `app.py` - Código principal (Flask + Telethon)
- `requirements.txt` - Dependencias
- `Procfile` - Comando de inicio
- `runtime.txt` - Versión de Python
- `ccs.txt` - Tarjetas (crear y llenar)
- `cmds.txt` - Comandos del bot

## 🌐 Acceso

Una vez desplegado, Railway te dará una URL pública tipo:
`https://tu-proyecto.up.railway.app`

## 🔒 Seguridad

- NO subas `ccs.txt` con datos reales a GitHub
- Usa variables de entorno para API_ID y API_HASH
- El `.gitignore` protege archivos sensibles

## 📱 Uso

1. Accede a tu URL
2. Verás el panel con logs en tiempo real
3. Usa el formulario para cambiar el canal
4. Los contadores se actualizan automáticamente

## ⚙️ Configuración

Edita las variables de entorno en Railway:
- `API_ID` y `API_HASH` de https://my.telegram.org
- `CHANNEL_ID` para el canal de destino

## 🐛 Logs

Railway tiene logs integrados en el panel. Monitorea ahí cualquier error.

## 📞 Soporte

Si tienes problemas, revisa los logs en el panel de Railway.
