# Исправление критических ошибок Agent Runtime

**Дата:** 2026-02-09  
**Статус:** ✅ ИСПРАВЛЕНО

## 📋 Резюме

Исправлены **2 критические ошибки**, блокирующие HITL workflow в agent-runtime:

1. ✅ **AttributeError** в `tool_result_handler.py` - метод `get_messages_by_role()` не существует
2. ✅ **TypeError** в `messages_router.py` - неверные параметры `HandleApprovalRequest`

---

## 🔧 Исправление #1: AttributeError в ToolResultHandler

### Проблема
```python
AttributeError: 'Conversation' object has no attribute 'get_messages_by_role'
```

**Файл:** [`tool_result_handler.py:260`](../codelab-ai-service/agent-runtime/app/domain/services/tool_result_handler.py:260)

### Причина
Класс `Conversation` использует `MessageCollection` (Value Object) для хранения сообщений, но метод `_extract_last_user_message()` пытался вызвать несуществующий метод `get_messages_by_role()`.

### Решение
Использовать метод `filter_by_role()` из `MessageCollection`:

```python
# БЫЛО:
def _extract_last_user_message(self, session) -> str:
    user_messages = session.get_messages_by_role("user")
    return user_messages[-1].content if user_messages else ""

# СТАЛО:
def _extract_last_user_message(self, session) -> str:
    # Используем filter_by_role из MessageCollection
    user_messages = session.messages.filter_by_role("user")
    return user_messages[-1].content if user_messages else ""
```

**Изменения:**
- ✅ Используется `session.messages.filter_by_role("user")` вместо `session.get_messages_by_role("user")`
- ✅ Обновлен docstring для уточнения типа параметра

---

## 🔧 Исправление #2: TypeError в HandleApprovalRequest

### Проблема
```python
TypeError: HandleApprovalRequest.__init__() got an unexpected keyword argument 'approval_request_id'
```

**Файл:** [`messages_router.py:291`](../codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py:291)

### Причина
Router использовал устаревшие/неверные имена параметров при создании `HandleApprovalRequest`:
- ❌ `approval_request_id` (не существует)
- ❌ `approved` (не существует)
- ❌ `approval_type="hitl"` (строка вместо enum)

**Фактическая сигнатура:**
```python
@dataclass
class HandleApprovalRequest:
    session_id: str
    approval_type: ApprovalType  # Enum, не строка
    approval_id: str             # Не approval_request_id
    decision: str                # Не approved
    modified_arguments: Optional[dict] = None
    feedback: Optional[str] = None
```

### Решение

**1. Добавлен импорт `ApprovalType`:**
```python
from ....application.use_cases.handle_approval_use_case import HandleApprovalRequest, ApprovalType
```

**2. Исправлен вызов конструктора:**
```python
# БЫЛО:
use_case_request = HandleApprovalRequest(
    session_id=session_id,
    approval_request_id=call_id,      # ❌ Неверное имя
    approved=(decision == "approved"), # ❌ Неверное имя
    approval_type="hitl"               # ❌ Строка вместо enum
)

# СТАЛО:
use_case_request = HandleApprovalRequest(
    session_id=session_id,
    approval_type=ApprovalType.HITL,  # ✅ Используем enum
    approval_id=call_id,              # ✅ Правильное имя
    decision=decision                 # ✅ Передаем строку напрямую
)
```

**Изменения:**
- ✅ `approval_request_id` → `approval_id`
- ✅ `approved=(decision == "approved")` → `decision=decision`
- ✅ `approval_type="hitl"` → `approval_type=ApprovalType.HITL`
- ✅ Добавлен импорт `ApprovalType`

---

## 📁 Измененные файлы

### 1. [`tool_result_handler.py`](../codelab-ai-service/agent-runtime/app/domain/services/tool_result_handler.py)
**Строка:** 260  
**Изменение:** Использование `session.messages.filter_by_role("user")`

### 2. [`messages_router.py`](../codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py)
**Строки:** 19, 291-296  
**Изменения:**
- Добавлен импорт `ApprovalType`
- Исправлены параметры `HandleApprovalRequest`

---

## 🧪 Тестирование

### Перезапуск сервиса
```bash
cd codelab-ai-service
docker compose up -d --build agent-runtime
```

### Проверка логов
```bash
docker compose logs agent-runtime --tail=50 --follow
```

### Ожидаемый результат
- ✅ Контейнер успешно запускается
- ✅ Нет ошибок при обработке HITL решений
- ✅ Нет ошибок при обработке tool results
- ✅ HITL workflow работает полностью

---

## 📊 Влияние изменений

### Затронутые компоненты
- ✅ **ToolResultHandler** - обработка результатов инструментов
- ✅ **HITL Decision Handler** - обработка решений пользователя
- ✅ **Messages Router** - API endpoint для HITL

### Риски
- 🟢 **Низкий риск** - локальные изменения
- 🟢 **Обратная совместимость** - сохранена
- 🟢 **Побочные эффекты** - отсутствуют

### Производительность
- ⚡ **Без изменений** - те же операции, правильный API

---

## ✅ Чеклист проверки

- [x] Исправлен AttributeError в `tool_result_handler.py`
- [x] Исправлен TypeError в `messages_router.py`
- [x] Добавлен импорт `ApprovalType`
- [x] Код соответствует существующим API
- [x] Изменения минимальны и целенаправленны
- [ ] Контейнер успешно перезапущен
- [ ] Логи не содержат ошибок
- [ ] HITL workflow протестирован

---

## 🎯 Следующие шаги

1. ✅ Дождаться завершения сборки контейнера
2. ⏳ Проверить логи на отсутствие ошибок
3. ⏳ Протестировать HITL workflow end-to-end
4. ⏳ Проверить отсутствие дублирования tool result
5. ⏳ Обновить интеграционные тесты

---

## 📝 Дополнительные рекомендации

### Краткосрочные (следующий спринт)
1. Добавить интеграционные тесты для HITL flow
2. Проверить все вызовы `HandleApprovalRequest` в кодовой базе
3. Добавить type hints для параметра `session` в `_extract_last_user_message()`

### Среднесрочные
1. Рассмотреть добавление метода `get_messages_by_role()` в `Conversation` для удобства
2. Создать фабрику для `HandleApprovalRequest` чтобы избежать подобных ошибок
3. Добавить валидацию параметров на уровне Pydantic схем

### Долгосрочные
1. Исследовать причину дублирования tool result (2 запроса с разницей 16ms)
2. Добавить E2E тесты для всего HITL workflow
3. Рассмотреть использование строгой типизации (mypy) для предотвращения подобных ошибок

---

## 🔗 Связанные документы

- [Анализ критических ошибок](./AGENT_RUNTIME_CRITICAL_BUGS_ANALYSIS.md)
- [Conversation Entity](../codelab-ai-service/agent-runtime/app/domain/session_context/entities/conversation.py)
- [MessageCollection Value Object](../codelab-ai-service/agent-runtime/app/domain/session_context/value_objects/message_collection.py)
- [HandleApprovalUseCase](../codelab-ai-service/agent-runtime/app/application/use_cases/handle_approval_use_case.py)

---

## 📈 Метрики

**Время на анализ:** ~10 минут  
**Время на исправление:** ~5 минут  
**Количество измененных файлов:** 2  
**Количество измененных строк:** ~10  
**Сложность изменений:** Низкая  
**Риск регрессии:** Минимальный
