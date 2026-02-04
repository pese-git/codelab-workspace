# Gateway Timeout Issue при Plan Execution с HITL

## 🔴 Проблема

Gateway получает `ReadTimeout` при выполнении плана с HITL approval.

## 📊 Анализ логов

### Что происходит:

1. **22:35:48** - Plan approved, starting execution
2. **22:35:48** - ExecutionEngine начинает выполнение subtask #1
3. **22:35:50** - LLM генерирует tool_call `create_directory` (requires_approval=true)
4. **22:35:50** - Создается pending approval
5. **22:35:50** - ExecutionEngine переходит в WAITING_APPROVAL state
6. **22:35:50** - ExecutionEngine ждет approval (polling каждые 0.5s)
7. **~22:36:50** - Gateway получает ReadTimeout (60 секунд)
8. **ERROR** - Gateway: "Error streaming from Agent: httpcore.ReadTimeout"

### Root Cause

**HTTP timeout в gateway (60 секунд) < Approval timeout в ExecutionEngine (300 секунд)**

```
Gateway HTTP timeout: 60s
ExecutionEngine approval timeout: 300s (5 минут)

Timeline:
0s   - Plan execution starts
2s   - Tool call generated (requires approval)
2s   - ExecutionEngine enters WAITING_APPROVAL
60s  - Gateway HTTP timeout ❌
300s - ExecutionEngine approval timeout (не достигается)
```

## 🎯 Это НЕ баг State Machine!

**State Machine работает правильно:**
- ✅ ExecutionEngine ждет HITL approval
- ✅ Переходит в WAITING_APPROVAL state
- ✅ Polling работает
- ✅ Timeout protection есть (300s)

**Проблема в Gateway:**
- ❌ HTTP timeout слишком короткий для HITL flow
- ❌ Gateway не поддерживает long-running SSE connections

## 💡 Решения

### Вариант 1: Увеличить HTTP timeout в Gateway (Быстрое решение)

**Файл**: `codelab-ai-service/gateway/app/websocket/handler.py` или конфигурация httpx

```python
# Увеличить timeout для SSE connections
timeout = httpx.Timeout(
    connect=10.0,
    read=360.0,    # ✅ 6 минут (больше чем approval timeout)
    write=10.0,
    pool=10.0
)
```

**Плюсы**:
- ✅ Быстро (1 строка)
- ✅ Решает проблему

**Минусы**:
- ❌ Не масштабируется (долгие connections)

### Вариант 2: Разделить execution на фазы (Правильное решение)

**Идея**: Plan approval НЕ должен запускать execution в том же HTTP request.

**Новый flow**:
```
1. Client → Gateway → Agent: plan_decision (approve)
2. Agent → Gateway → Client: plan_approved (is_final=true)
3. HTTP connection закрывается ✅

4. Client → Gateway → Agent: start_plan_execution (новый request)
5. Agent → Gateway → Client: SSE stream с chunks
6. При tool approval:
   - Agent → Client: tool_call chunk
   - HTTP connection закрывается ✅
   
7. Client → Agent: hitl_decision (approve)
8. Client → Agent: tool_result
9. Agent продолжает execution
```

**Плюсы**:
- ✅ Короткие HTTP connections
- ✅ Масштабируемо
- ✅ Правильная архитектура

**Минусы**:
- ❌ Требует изменений в PlanApprovalHandler
- ❌ Требует изменений в клиенте (IDE)

### Вариант 3: WebSocket keep-alive (Средний вариант)

**Идея**: Gateway отправляет keep-alive chunks каждые 30 секунд

```python
# В ExecutionEngine._wait_for_approvals()
while waiting:
    if elapsed % 30 == 0:
        yield StreamChunk(type="keep_alive", content="Waiting...")
    await asyncio.sleep(0.5)
```

**Плюсы**:
- ✅ Поддерживает connection alive
- ✅ Минимальные изменения

**Минусы**:
- ❌ Все еще долгие connections
- ❌ Не решает фундаментальную проблему

## 🎯 Рекомендация

### Краткосрочно (СЕЙЧАС):
**Вариант 1** - Увеличить HTTP timeout в Gateway до 360 секунд

### Долгосрочно (ПОЗЖЕ):
**Вариант 2** - Разделить plan approval и execution на разные requests

## 📝 Immediate Fix

### 1. Найти конфигурацию timeout в Gateway

```bash
grep -r "timeout\|Timeout" codelab-ai-service/gateway/
```

### 2. Увеличить read timeout

```python
# gateway/app/websocket/handler.py или gateway/app/config.py

# Было:
timeout = httpx.Timeout(60.0)

# Стало:
timeout = httpx.Timeout(
    connect=10.0,
    read=360.0,  # 6 минут для HITL approval
    write=10.0,
    pool=10.0
)
```

### 3. Перезапустить Gateway

```bash
docker compose restart gateway
```

## ✅ Вывод

**State Machine реализация корректна!**

Проблема не в ExecutionEngine, а в Gateway HTTP timeout.
Нужно увеличить timeout для поддержки long-running HITL approvals.
