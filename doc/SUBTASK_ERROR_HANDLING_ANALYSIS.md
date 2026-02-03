# Subtask Error Handling Analysis

## 📊 Анализ логов

### ✅ План выполнился успешно
```
Plan 97d6925d-135b-4895-aaa4-efd9ae8e9561 execution completed: 
status=completed, completed=8/8, failed=0, duration=40.83s
```

**Все 8 subtasks завершились со статусом DONE!**

### ⚠️ Но в зависимостях видны ошибки

```
Dependencies completed:
- Add necessary dependencies to pubspec.yaml (e.g., http, provider, flutter_svg).
  Result: [Error] LiteLLM proxy unavailable: Error code: 400 - 
  {'error': {'message': 'litellm.BadRequestError: OpenrouterException...
```

## 🔍 Корневая причина

### Проблема в [`subtask_executor.py:159`](../codelab-ai-service/agent-runtime/app/domain/services/subtask_executor.py:159)

```python
# Собрать результат
result = self._collect_result(result_chunks)

# Завершить подзадачу успешно
subtask.complete(result=result["content"])  # ❌ Всегда complete!
```

**Проблема**: Subtask всегда помечается как `complete()`, даже если:
- LLM вернул ошибку
- Agent не выполнил задачу
- В chunks есть error chunks

### Метод `_collect_result()` (строка 264)

```python
def _collect_result(self, chunks: list) -> Dict[str, Any]:
    """Собрать результат из chunks."""
    content_parts = []
    metadata = {}
    
    for chunk in chunks:
        if isinstance(chunk, StreamChunk):
            if chunk.content:
                content_parts.append(chunk.content)
            if chunk.metadata:
                metadata.update(chunk.metadata)
    
    return {
        "content": "\n".join(content_parts),
        "metadata": metadata,
        "chunk_count": len(chunks)
    }
```

**Проблема**: Метод НЕ проверяет:
- Наличие error chunks
- Статус выполнения
- Успешность операции

## 🎯 Почему subtasks помечаются как completed

### Текущая логика:

1. Agent выполняет subtask
2. Agent возвращает chunks (может быть error chunk)
3. `_collect_result()` собирает все chunks в один результат
4. **Subtask всегда помечается как `complete()`**
5. Даже если был error, subtask в статусе DONE

### Результат:

- ✅ План показывает "8/8 completed"
- ❌ Но фактически subtasks могли завершиться с ошибками
- ❌ Пользователь видит "Plan execution failed" в UI
- ❌ Но в логах "status=completed"

## 🔧 Возможные решения

### Вариант 1: Проверять error chunks

```python
# Собрать результат
result = self._collect_result(result_chunks)

# Проверить наличие ошибок в chunks
has_error = any(
    chunk.type == "error" 
    for chunk in result_chunks 
    if isinstance(chunk, StreamChunk)
)

if has_error:
    # Завершить с ошибкой
    error_content = next(
        (chunk.error for chunk in result_chunks 
         if isinstance(chunk, StreamChunk) and chunk.type == "error"),
        "Unknown error"
    )
    subtask.fail(error=error_content)
else:
    # Завершить успешно
    subtask.complete(result=result["content"])
```

### Вариант 2: Проверять metadata статус

```python
# Собрать результат
result = self._collect_result(result_chunks)

# Проверить статус в metadata
status = result.get("metadata", {}).get("status")

if status == "failed" or status == "error":
    error_msg = result.get("metadata", {}).get("error", "Subtask failed")
    subtask.fail(error=error_msg)
else:
    subtask.complete(result=result["content"])
```

### Вариант 3: Проверять финальный chunk

```python
# Получить финальный chunk
final_chunk = next(
    (chunk for chunk in reversed(result_chunks) 
     if isinstance(chunk, StreamChunk) and chunk.is_final),
    None
)

if final_chunk and final_chunk.type == "error":
    subtask.fail(error=final_chunk.error or "Subtask failed")
else:
    result = self._collect_result(result_chunks)
    subtask.complete(result=result["content"])
```

## 🤔 Текущее поведение

Судя по логам:
```
2026-02-03 17:17:10,855 - agent-runtime.domain.subtask_executor - INFO - 
Subtask 1a328b39-2d91-4c0b-b51e-97093bf3d75f completed successfully by ask agent
```

**Все subtasks завершаются успешно**, даже если LLM вернул ошибку.

Это может быть:
1. **Правильное поведение** - если ошибка LLM не критична для subtask
2. **Неправильное поведение** - если ошибка означает, что subtask не выполнена

## 📝 Рекомендация

Нужно уточнить требования:

1. **Если LLM вернул ошибку** - должна ли subtask помечаться как failed?
2. **Если agent не вызвал tools** - должна ли subtask помечаться как failed?
3. **Какие критерии успешности** subtask?

## 🎯 Вероятная проблема в UI

Если в UI показывается "Plan execution failed", но в логах "status=completed", то проблема может быть:

1. **В клиенте (IDE)** - неправильная интерпретация результата
2. **В формате ответа** - клиент ожидает другой формат
3. **В error chunks** - клиент видит error chunks и считает план failed

Нужно проверить, что именно клиент получает в SSE stream.
