# Аутентификация в Benchmark Standalone

## Обзор

Benchmark Standalone поддерживает два типа аутентификации для доступа к Gateway API:

1. **Internal API Key** - простая аутентификация через заголовок X-Internal-Auth
2. **JWT OAuth2** - аутентификация через OAuth2 с автоматическим обновлением токенов

## Конфигурация

### Internal API Key (рекомендуется для разработки)

Простой метод аутентификации с использованием статического API ключа.

```yaml
gateway:
  auth_type: "internal"
  api_key: "change-me-in-production"
```

**Преимущества:**
- Простота настройки
- Не требует дополнительных сервисов
- Подходит для локальной разработки

**Недостатки:**
- Менее безопасно для production
- Нет автоматического истечения токенов

### JWT OAuth2 (рекомендуется для production)

Аутентификация через OAuth2 с поддержкой refresh токенов.

```yaml
gateway:
  auth_type: "jwt"
  jwt:
    auth_url: "http://localhost:80/oauth/token"
    username: "admin"
    password: "admin"
    client_id: "codelab-flutter-app"
    client_secret: ""  # Опционально
```

**Преимущества:**
- Безопасность через истекающие токены
- Автоматическое обновление токенов
- Поддержка refresh токенов
- Соответствие стандартам OAuth2

**Недостатки:**
- Требует запущенный auth-service
- Более сложная настройка

## Автоматическое обновление токенов

Система автоматически обрабатывает истечение JWT токенов:

### Механизм работы

```
1. HTTP запрос с access_token
   ↓
2. Получен 401 Unauthorized
   ↓
3. AuthManager.handle_unauthorized()
   ↓
4. Попытка обновления через refresh_token
   ↓
5. Если успешно → повтор запроса с новым токеном
   ↓
6. Если неудачно → полная повторная аутентификация
```

### Thread-safe обновление

AuthManager использует `asyncio.Lock` для предотвращения одновременных обновлений токена:

- Первый запрос с 401 начинает обновление токена
- Последующие запросы ожидают завершения обновления
- Все запросы используют обновленный токен

### Пример использования

```python
from src import AuthManager, GatewayClient

# Создание auth manager
auth_manager = AuthManager(config['gateway'])

# Создание клиента
client = GatewayClient(
    base_url=config['gateway']['base_url'],
    ws_url=config['gateway']['ws_url'],
    auth_manager=auth_manager
)

# Все HTTP запросы автоматически обрабатывают 401
session_id = await client.create_session()  # Автоматический retry при 401
metrics = await client.get_session_metrics(session_id)  # Автоматический retry при 401
```

## AuthManager API

### Методы

#### `get_headers() -> Dict[str, str]`

Получить заголовки аутентификации для HTTP запросов.

```python
headers = await auth_manager.get_headers()
# Internal: {"X-Internal-Auth": "api-key"}
# JWT: {"Authorization": "Bearer access_token"}
```

#### `authenticate_jwt() -> str`

Выполнить OAuth2 аутентификацию и получить access_token.

```python
access_token = await auth_manager.authenticate_jwt()
```

#### `refresh_access_token() -> str`

Обновить access_token используя refresh_token.

```python
new_token = await auth_manager.refresh_access_token()
```

#### `handle_unauthorized() -> None`

Обработать ошибку 401 Unauthorized.

```python
await auth_manager.handle_unauthorized()
```

## GatewayClient с автоматическим retry

### `_make_http_request()`

Универсальный метод для HTTP запросов с автоматическим retry при 401.

```python
response = await client._make_http_request(
    "POST",
    f"{base_url}/api/v1/sessions",
    retry_on_401=True  # По умолчанию True
)
```

**Логика работы:**
1. Выполняет HTTP запрос с текущим токеном
2. Если получен 401 и `retry_on_401=True`:
   - Вызывает `auth_manager.handle_unauthorized()`
   - Получает новые заголовки с обновленным токеном
   - Повторяет запрос
3. Возвращает результат или выбрасывает исключение

## Настройка auth-service

Для использования JWT аутентификации необходим запущенный auth-service.

### Docker Compose

```yaml
auth-service:
  image: your-registry/auth-service:latest
  environment:
    - AUTH_SERVICE__MASTER_KEY=admin
    - AUTH_SERVICE__JWT_SECRET=your-secret-key
    - AUTH_SERVICE__JWT_EXPIRATION=3600
  ports:
    - "8080:8080"
```

### Проверка работы

```bash
# Тест аутентификации
curl -X POST http://localhost:80/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=admin&password=admin&client_id=codelab-flutter-app"

# Ожидаемый ответ:
# {
#   "access_token": "eyJ...",
#   "refresh_token": "eyJ...",
#   "token_type": "bearer",
#   "expires_in": 3600
# }
```

## Тестирование

### Тест подключения

```bash
cd benchmark-standalone
uv run python test_connection.py
```

### Тест обновления токенов

```bash
cd benchmark-standalone
uv run python test_token_refresh.py
```

### Ожидаемые результаты

```
✅ Internal Auth: PASS
✅ JWT Auth: PASS (требует запущенный auth service)
✅ Token Refresh: PASS
✅ 401 Handling: PASS
```

## Логирование

Система логирует все важные события аутентификации:

```
🔐 Authenticating with OAuth2: admin
✅ JWT token obtained successfully
🔄 Refreshing access token using refresh_token...
✅ Access token refreshed successfully
⚠️ Received 401 from http://..., refreshing token and retrying...
```

## Troubleshooting

### Ошибка: "Failed to authenticate"

**Причина:** Неверные учетные данные или auth-service недоступен

**Решение:**
1. Проверьте настройки в [`config.yaml`](../config.yaml)
2. Убедитесь что auth-service запущен
3. Проверьте логи auth-service

### Ошибка: "No refresh_token available"

**Причина:** Refresh token не был получен при первичной аутентификации

**Решение:**
- Система автоматически выполнит полную повторную аутентификацию
- Проверьте что auth-service возвращает refresh_token

### Ошибка: "Token refresh failed"

**Причина:** Refresh token истек или недействителен

**Решение:**
- Система автоматически выполнит полную повторную аутентификацию
- Проверьте настройки JWT_EXPIRATION в auth-service

## Безопасность

### Рекомендации

1. **Не храните токены в git** - используйте `.env` файлы
2. **Используйте HTTPS в production** - защита токенов при передаче
3. **Регулярно обновляйте API ключи** - для Internal Auth
4. **Настройте короткое время жизни токенов** - для JWT (например, 1 час)
5. **Используйте сильные пароли** - для JWT аутентификации

### Пример .env файла

```bash
# .env
GATEWAY_AUTH_TYPE=jwt
GATEWAY_JWT_USERNAME=admin
GATEWAY_JWT_PASSWORD=secure-password-here
GATEWAY_API_KEY=change-me-in-production
```

Загрузка в config.yaml:

```python
import os
from dotenv import load_dotenv

load_dotenv()

config = {
    'gateway': {
        'auth_type': os.getenv('GATEWAY_AUTH_TYPE', 'internal'),
        'api_key': os.getenv('GATEWAY_API_KEY'),
        'jwt': {
            'username': os.getenv('GATEWAY_JWT_USERNAME'),
            'password': os.getenv('GATEWAY_JWT_PASSWORD'),
            # ...
        }
    }
}
```

## Будущие улучшения

- [ ] Проактивное обновление токена до истечения (используя expires_in)
- [ ] Кэширование токенов между запусками
- [ ] Поддержка других OAuth2 grant types (client_credentials)
- [ ] Метрики обновления токенов
- [ ] Поддержка нескольких auth providers
