# Анализ критических ошибок Agent Runtime

**Дата:** 2026-02-09  
**Статус:** 🔴 КРИТИЧЕСКИЕ ОШИБКИ ОБНАРУЖЕНЫ

## 📊 Обзор

Проанализированы логи Docker Compose для сервиса `agent-runtime`. Обнаружены **2 критические ошибки**, блокирующие работу системы.

---

## 🔴 Критическая ошибка #1: AttributeError в ToolResultHandler

### Описание
```python
AttributeError: 'Conversation' object has no attribute 'get_messages_by_role'
```

### Локация
- **Файл:** [`tool_result_handler.py:260`](../codelab-ai-service/agent-runtime/app/domain/services/tool_result_handler.py:260)
- **Метод:** `_extract_last_user_message()`
- **Частота:** Повторяется дважды в логах (строки 128-140, 181-193)

### Traceback
```python
File "/app/app/application/use_cases/process_tool_result_use_case.py", line 134, in execute
    async for chunk in self._tool_result_handler.handle(
File "/app/app/domain/services/tool_result_handler.py", line 199, in handle
    last_user_message = self._extract_last_user_message(session)
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/app/app/domain/services/tool_result_handler.py", line 260, in _extract_last_user_message
    user_messages = session.get_messages_by_role("user")
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

### Контекст выполнения
```
2026-02-09 08:18:47,636 - agent-runtime.domain.tool_result_handler - INFO - 
Результат инструмента добавлен в сессию ade14cd8-343a-4655-958e-8373ee614762, 
call_id=call_JJ095hoNcCiT6KigJH5NMbT5, has_error=False, 
продолжаем обработку с агентом coder
```

### Причина
Класс [`Conversation`](../codelab-ai-service/agent-runtime/app/domain/session_context/entities/conversation.py:26) **не имеет метода** `get_messages_by_role()`.

**Доступные методы в Conversation:**
- `add_message(message: Message)`
- `get_message_count()`
- `is_empty()`
- `get_history_for_llm(max_messages)`
- `clear_messages()`
- `deactivate(reason)`
- `activate()`

**Сообщения хранятся в:** `messages: MessageCollection` (Value Object)

### Решение
Необходимо либо:
1. **Добавить метод** `get_messages_by_role()` в класс `Conversation`
2. **ИЛИ** изменить код в `tool_result_handler.py:260` для работы с `MessageCollection`

**Рекомендуемое решение:**
```python
# В tool_result_handler.py:260
# БЫЛО:
user_messages = session.get_messages_by_role("user")

# ДОЛЖНО БЫТЬ:
user_messages = [msg for msg in session.messages.messages if msg.role == "user"]
```

---

## 🔴 Критическая ошибка #2: TypeError в HandleApprovalRequest

### Описание
```python
TypeError: HandleApprovalRequest.__init__() got an unexpected keyword argument 'approval_request_id'
```

### Локация
- **Файл:** [`messages_router.py:291`](../codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py:291)
- **Endpoint:** `POST /agent/message/stream` (HITL decision)
- **Строка лога:** 81-86

### Traceback
```python
File "/app/app/api/v1/routers/messages_router.py", line 291, in hitl_decision_generate
    use_case_request = HandleApprovalRequest(
                       ^^^^^^^^^^^^^^^^^^^^^^
TypeError: HandleApprovalRequest.__init__() got an unexpected keyword argument 'approval_request_id'
```

### Контекст выполнения
```python
# messages_router.py:291-296
use_case_request = HandleApprovalRequest(
    session_id=session_id,
    approval_request_id=call_id,  # ❌ НЕВЕРНЫЙ ПАРАМЕТР
    approved=(decision == "approved"),
    approval_type="hitl"
)
```

### Причина
**Фактическая сигнатура** [`HandleApprovalRequest`](../codelab-ai-service/agent-runtime/app/application/use_cases/handle_approval_use_case.py:25):
```python
@dataclass
class HandleApprovalRequest:
    session_id: str
    approval_type: ApprovalType
    approval_id: str              # ✅ ПРАВИЛЬНОЕ ИМЯ
    decision: str
    modified_arguments: Optional[dict] = None
    feedback: Optional[str] = None
```

**Используется неверное имя параметра:**
- ❌ `approval_request_id` (в router)
- ✅ `approval_id` (в dataclass)

### Решение
Исправить вызов в [`messages_router.py:291`](../codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py:291):

```python
# БЫЛО:
use_case_request = HandleApprovalRequest(
    session_id=session_id,
    approval_request_id=call_id,  # ❌
    approved=(decision == "approved"),  # ❌ Тоже неверно
    approval_type="hitl"
)

# ДОЛЖНО БЫТЬ:
use_case_request = HandleApprovalRequest(
    session_id=session_id,
    approval_type=ApprovalType.HITL,  # ✅ Используем enum
    approval_id=call_id,              # ✅ Правильное имя
    decision=decision                 # ✅ Передаем строку напрямую
)
```

---

## 📈 Статистика логов

### Успешные операции
- ✅ Health checks: работают корректно
- ✅ LLM запросы: выполняются успешно (2514ms, 1277 tokens)
- ✅ Tool approval required: события публикуются
- ✅ Сохранение сообщений: работает
- ✅ Session locks: корректно управляются

### Проблемные операции
- ❌ HITL decision processing: TypeError при создании request
- ❌ Tool result processing: AttributeError при извлечении user message
- ⚠️ Дублирование tool result: обрабатывается дважды (строки 92-143, 145-196)

### События в логах
```
08:18:45 - Tool call detected: execute_command
08:18:45 - TOOL_APPROVAL_REQUIRED event published
08:18:45 - Assistant message saved with tool_call
08:18:47 - HITL decision received (approve)
08:18:47 - ❌ TypeError: approval_request_id
08:18:47 - Tool result processing started
08:18:47 - ❌ AttributeError: get_messages_by_role
```

---

## 🎯 План исправления

### Приоритет 1: Исправить TypeError в HITL
**Файл:** [`messages_router.py:291-296`](../codelab-ai-service/agent-runtime/app/api/v1/routers/messages_router.py:291)

```python
use_case_request = HandleApprovalRequest(
    session_id=session_id,
    approval_type=ApprovalType.HITL,
    approval_id=call_id,
    decision=decision
)
```

### Приоритет 2: Исправить AttributeError в ToolResultHandler
**Файл:** [`tool_result_handler.py:260`](../codelab-ai-service/agent-runtime/app/domain/services/tool_result_handler.py:260)

**Вариант A:** Добавить метод в Conversation
```python
# В conversation.py
def get_messages_by_role(self, role: str) -> List[Message]:
    """Получить сообщения по роли."""
    return [msg for msg in self.messages.messages if msg.role == role]
```

**Вариант B:** Использовать MessageCollection напрямую
```python
# В tool_result_handler.py:260
def _extract_last_user_message(self, session) -> str:
    user_messages = [
        msg for msg in session.messages.messages 
        if msg.role == "user"
    ]
    return user_messages[-1].content if user_messages else ""
```

**Рекомендация:** Вариант A (добавить метод в Conversation) - более чистое решение.

### Приоритет 3: Проверить дублирование tool result
Логи показывают, что tool result обрабатывается дважды:
- 08:18:47,612 - Первая обработка
- 08:18:47,628 - Вторая обработка (16ms позже)

Необходимо проверить, почему происходит дублирование запросов.

---

## 🔍 Дополнительные наблюдения

### Архитектурные проблемы
1. **Несоответствие API:** Router использует устаревшие имена параметров
2. **Отсутствие методов:** Conversation не предоставляет необходимые методы для фильтрации
3. **Возможное дублирование:** Tool result обрабатывается дважды

### Положительные моменты
- ✅ Event-driven архитектура работает корректно
- ✅ UnitOfWork и транзакции функционируют
- ✅ Session locking предотвращает race conditions
- ✅ LLM интеграция стабильна

---

## 📝 Рекомендации

1. **Немедленно исправить** обе критические ошибки
2. **Добавить интеграционные тесты** для HITL flow
3. **Проверить все вызовы** HandleApprovalRequest в кодовой базе
4. **Добавить метод** `get_messages_by_role()` в Conversation
5. **Исследовать** причину дублирования tool result
6. **Обновить документацию** API для HandleApprovalRequest

---

## 🏁 Заключение

Обнаружены **2 критические ошибки**, полностью блокирующие HITL workflow:
1. ❌ TypeError при обработке HITL решения
2. ❌ AttributeError при обработке tool result

Обе ошибки легко исправляются и требуют минимальных изменений кода.

**Оценка времени на исправление:** 15-30 минут  
**Риск:** Низкий (локальные изменения)  
**Приоритет:** 🔴 КРИТИЧЕСКИЙ
