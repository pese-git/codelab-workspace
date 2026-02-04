# 🏗️ Архитектурное решение: Очистка истории сессии между subtasks

## 📋 Проблема

**LiteLLM 403 ошибка** вызвана дублированием `tool_call_id` из предыдущей subtask в истории сессии.

### Корневая причина

При выполнении плана с несколькими subtasks:

1. **Subtask 1** выполняется → генерирует `tool_call` с `id="call_abc123"`
2. `tool_result` добавляется в историю сессии с `tool_call_id="call_abc123"`
3. **Subtask 2** начинает выполняться в той же сессии
4. История сессии содержит старые `tool_call` и `tool_result` от Subtask 1
5. LLM видит старый `tool_call_id` и может попытаться его переиспользовать
6. LiteLLM proxy отклоняет запрос с 403 из-за дублирования `tool_call_id`

### Текущий flow

```
ExecutionEngine.execute_plan()
  ├─> SubtaskExecutor.execute_subtask(subtask_1)
  │     ├─> agent.process() → tool_call (id="call_abc123")
  │     └─> session.add_message(role="tool", tool_call_id="call_abc123")
  │
  ├─> [tool_result обработан, execution возобновляется]
  │
  └─> SubtaskExecutor.execute_subtask(subtask_2)
        ├─> agent.process() → использует ту же сессию
        └─> История содержит старые tool_call/tool_result от subtask_1
            ❌ LiteLLM 403: duplicate tool_call_id
```

---

## 🎯 Архитектурное решение

### Принцип: Изоляция контекста между subtasks

**Каждая subtask должна выполняться в изолированном контексте, но с доступом к результатам зависимостей.**

### Варианты решения

#### ✅ Вариант 1: Session Snapshot (Рекомендуемый)

**Идея**: Создавать snapshot истории сессии перед каждой subtask и восстанавливать после.

**Преимущества**:
- ✅ Полная изоляция между subtasks
- ✅ Сохранение базовой истории сессии (user messages, system context)
- ✅ Нет дублирования tool_call_id
- ✅ Возможность rollback при ошибке

**Реализация**:

```python
# session_management.py

class SessionManagementService:
    
    async def create_subtask_context(
        self,
        session_id: str,
        subtask_id: str,
        dependency_results: Dict[str, Any]
    ) -> str:
        """
        Создать изолированный контекст для subtask.
        
        1. Сохранить snapshot текущей истории
        2. Очистить tool-related messages (assistant с tool_calls, tool results)
        3. Добавить dependency results как system context
        4. Вернуть snapshot_id для восстановления
        
        Args:
            session_id: ID основной сессии
            subtask_id: ID subtask
            dependency_results: Результаты зависимостей
            
        Returns:
            snapshot_id для восстановления после subtask
        """
        session = await self.get_session(session_id)
        
        # 1. Создать snapshot
        snapshot_id = f"{session_id}_snapshot_{subtask_id}"
        snapshot = session.create_snapshot()
        await self._repository.save_snapshot(snapshot_id, snapshot)
        
        # 2. Очистить tool-related messages
        session.clear_tool_messages()
        
        # 3. Добавить dependency context
        if dependency_results:
            context_message = self._format_dependency_context(dependency_results)
            await self.add_message(
                session_id=session_id,
                role="system",
                content=context_message
            )
        
        await self._repository.save(session)
        
        logger.info(
            f"Created subtask context for {subtask_id} "
            f"(snapshot: {snapshot_id})"
        )
        
        return snapshot_id
    
    async def restore_from_snapshot(
        self,
        session_id: str,
        snapshot_id: str,
        preserve_last_result: bool = True
    ) -> None:
        """
        Восстановить сессию из snapshot после subtask.
        
        Args:
            session_id: ID сессии
            snapshot_id: ID snapshot
            preserve_last_result: Сохранить последний assistant message
        """
        session = await self.get_session(session_id)
        snapshot = await self._repository.get_snapshot(snapshot_id)
        
        if not snapshot:
            logger.warning(f"Snapshot {snapshot_id} not found, skipping restore")
            return
        
        # Сохранить последний результат если нужно
        last_result = None
        if preserve_last_result:
            last_result = session.get_last_assistant_message()
        
        # Восстановить из snapshot
        session.restore_from_snapshot(snapshot)
        
        # Добавить последний результат обратно
        if last_result:
            session.add_message(last_result)
        
        await self._repository.save(session)
        await self._repository.delete_snapshot(snapshot_id)
        
        logger.info(f"Restored session {session_id} from snapshot {snapshot_id}")
    
    def _format_dependency_context(
        self,
        dependency_results: Dict[str, Any]
    ) -> str:
        """Форматировать результаты зависимостей в system message."""
        lines = ["Previous subtask results:"]
        for dep_id, result in dependency_results.items():
            lines.append(f"\n## {result['description']}")
            lines.append(f"Result: {result['result']}")
        return "\n".join(lines)
```

```python
# session.py (Entity)

class Session:
    
    def create_snapshot(self) -> Dict[str, Any]:
        """Создать snapshot текущего состояния."""
        return {
            "messages": [msg.to_dict() for msg in self.messages],
            "metadata": self.metadata.copy(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    
    def restore_from_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Восстановить состояние из snapshot."""
        self.messages = [
            Message.from_dict(msg_dict)
            for msg_dict in snapshot["messages"]
        ]
        self.metadata.update(snapshot.get("metadata", {}))
    
    def clear_tool_messages(self) -> None:
        """
        Очистить tool-related messages.
        
        Удаляет:
        - assistant messages с tool_calls
        - tool result messages
        
        Сохраняет:
        - user messages
        - system messages
        - assistant messages без tool_calls
        """
        self.messages = [
            msg for msg in self.messages
            if not (
                (msg.role == "assistant" and msg.tool_calls) or
                msg.role == "tool"
            )
        ]
        
        logger.debug(
            f"Cleared tool messages from session {self.id}, "
            f"remaining: {len(self.messages)}"
        )
    
    def get_last_assistant_message(self) -> Optional[Message]:
        """Получить последнее assistant message."""
        for msg in reversed(self.messages):
            if msg.role == "assistant":
                return msg
        return None
```

```python
# subtask_executor.py

class SubtaskExecutor:
    
    async def execute_subtask(
        self,
        plan_id: str,
        subtask_id: str,
        session_id: str,
        session_service: "SessionManagementService",
        stream_handler: "IStreamHandler"
    ) -> AsyncGenerator[StreamChunk, None]:
        """Выполнить subtask с изолированным контекстом."""
        
        # ... existing code ...
        
        # Подготовить контекст для агента
        context = self._prepare_agent_context(subtask, plan)
        
        # ✅ НОВОЕ: Создать изолированный контекст для subtask
        snapshot_id = await session_service.create_subtask_context(
            session_id=session_id,
            subtask_id=subtask_id,
            dependency_results=context.get("dependencies", {})
        )
        
        try:
            # Выполнить подзадачу через агента
            result_chunks = []
            async for chunk in agent.process(
                session_id=session_id,
                message=subtask.description,
                context=context,
                session=session,
                session_service=session_service,
                stream_handler=stream_handler
            ):
                result_chunks.append(chunk)
                yield chunk
            
            # ... existing result processing ...
            
        finally:
            # ✅ НОВОЕ: Восстановить сессию из snapshot
            await session_service.restore_from_snapshot(
                session_id=session_id,
                snapshot_id=snapshot_id,
                preserve_last_result=True
            )
```

---

#### 🔄 Вариант 2: Separate Session per Subtask

**Идея**: Создавать отдельную временную сессию для каждой subtask.

**Преимущества**:
- ✅ Полная изоляция
- ✅ Простая реализация
- ✅ Нет риска загрязнения основной сессии

**Недостатки**:
- ❌ Потеря контекста основной сессии
- ❌ Сложность передачи результатов
- ❌ Дополнительная нагрузка на БД

**Реализация**:

```python
# subtask_executor.py

async def execute_subtask(
    self,
    plan_id: str,
    subtask_id: str,
    session_id: str,
    session_service: "SessionManagementService",
    stream_handler: "IStreamHandler"
) -> AsyncGenerator[StreamChunk, None]:
    """Выполнить subtask в отдельной сессии."""
    
    # Создать временную сессию для subtask
    subtask_session_id = f"{session_id}_subtask_{subtask_id}"
    subtask_session = await session_service.create_session(subtask_session_id)
    
    # Скопировать базовый контекст из основной сессии
    main_session = await session_service.get_session(session_id)
    await self._copy_base_context(main_session, subtask_session)
    
    # Добавить dependency results
    context = self._prepare_agent_context(subtask, plan)
    if context.get("dependencies"):
        await session_service.add_message(
            session_id=subtask_session_id,
            role="system",
            content=self._format_dependencies(context["dependencies"])
        )
    
    try:
        # Выполнить в временной сессии
        async for chunk in agent.process(
            session_id=subtask_session_id,  # ✅ Используем временную сессию
            message=subtask.description,
            context=context,
            session=subtask_session,
            session_service=session_service,
            stream_handler=stream_handler
        ):
            yield chunk
        
        # ... result processing ...
        
    finally:
        # Удалить временную сессию
        await session_service.deactivate_session(
            subtask_session_id,
            reason="Subtask completed"
        )
```

---

#### 🧹 Вариант 3: Selective Message Cleanup

**Идея**: Очищать только tool-related messages перед каждой subtask.

**Преимущества**:
- ✅ Простая реализация
- ✅ Минимальные изменения
- ✅ Сохранение основной истории

**Недостатки**:
- ❌ Нет возможности rollback
- ❌ Потеря tool_call истории (может быть важна для debugging)

**Реализация**:

```python
# subtask_executor.py

async def execute_subtask(
    self,
    plan_id: str,
    subtask_id: str,
    session_id: str,
    session_service: "SessionManagementService",
    stream_handler: "IStreamHandler"
) -> AsyncGenerator[StreamChunk, None]:
    """Выполнить subtask с очисткой tool messages."""
    
    # ... existing code ...
    
    # ✅ НОВОЕ: Очистить tool messages перед subtask
    session = await session_service.get_session(session_id)
    session.clear_tool_messages()
    await session_service._repository.save(session)
    
    logger.info(
        f"Cleared tool messages for subtask {subtask_id}, "
        f"remaining messages: {len(session.messages)}"
    )
    
    # Выполнить подзадачу
    async for chunk in agent.process(...):
        yield chunk
```

---

## 🎯 Рекомендация: Вариант 1 (Session Snapshot)

### Почему Вариант 1?

1. **Полная изоляция** - каждая subtask работает в чистом контексте
2. **Сохранение истории** - можно восстановить состояние при ошибке
3. **Гибкость** - можно контролировать, что сохранять/восстанавливать
4. **Debugging** - snapshot можно использовать для анализа проблем
5. **Масштабируемость** - легко добавить дополнительную логику

### Архитектурные преимущества

```
┌─────────────────────────────────────────────────────────────┐
│                    ExecutionEngine                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   SubtaskExecutor                           │
│                                                             │
│  1. create_subtask_context()                                │
│     ├─> Save snapshot                                       │
│     ├─> Clear tool messages                                 │
│     └─> Add dependency context                              │
│                                                             │
│  2. agent.process()                                         │
│     └─> Clean context, no old tool_call_id                  │
│                                                             │
│  3. restore_from_snapshot()                                 │
│     ├─> Restore base history                                │
│     └─> Preserve last result                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 План реализации

### Этап 1: Расширение Session Entity

- [ ] Добавить `create_snapshot()` метод
- [ ] Добавить `restore_from_snapshot()` метод
- [ ] Добавить `clear_tool_messages()` метод
- [ ] Добавить `get_last_assistant_message()` метод

### Этап 2: Расширение SessionRepository

- [ ] Добавить `save_snapshot()` метод
- [ ] Добавить `get_snapshot()` метод
- [ ] Добавить `delete_snapshot()` метод
- [ ] Реализовать хранение snapshots (in-memory или Redis)

### Этап 3: Расширение SessionManagementService

- [ ] Добавить `create_subtask_context()` метод
- [ ] Добавить `restore_from_snapshot()` метод
- [ ] Добавить `_format_dependency_context()` helper

### Этап 4: Интеграция в SubtaskExecutor

- [ ] Вызывать `create_subtask_context()` перед `agent.process()`
- [ ] Вызывать `restore_from_snapshot()` в `finally` блоке
- [ ] Добавить логирование для debugging

### Этап 5: Тестирование

- [ ] Unit tests для snapshot механизма
- [ ] Integration tests для subtask isolation
- [ ] E2E тест с планом из 3+ subtasks
- [ ] Проверить отсутствие LiteLLM 403 ошибок

---

## 🔍 Альтернативные подходы

### Подход A: Message Filtering в Agent

Вместо очистки истории, фильтровать messages при отправке в LLM:

```python
# agent.py

def _prepare_messages_for_llm(
    self,
    session: Session,
    context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Подготовить messages для LLM, исключая старые tool_calls."""
    
    messages = []
    for msg in session.messages:
        # Пропустить assistant messages с tool_calls
        if msg.role == "assistant" and msg.tool_calls:
            continue
        # Пропустить tool result messages
        if msg.role == "tool":
            continue
        
        messages.append(msg.to_dict())
    
    return messages
```

**Проблема**: Не решает корневую причину, только маскирует симптом.

### Подход B: Tool Call ID Namespace

Добавить namespace к tool_call_id для уникальности:

```python
tool_call_id = f"{subtask_id}_{original_call_id}"
```

**Проблема**: Не решает загрязнение истории, только избегает коллизий.

---

## ✅ Критерии успеха

1. ✅ Каждая subtask выполняется в изолированном контексте
2. ✅ Нет дублирования `tool_call_id` между subtasks
3. ✅ LiteLLM 403 ошибки устранены
4. ✅ Dependency results доступны в subtask context
5. ✅ Базовая история сессии сохраняется
6. ✅ Возможность rollback при ошибке
7. ✅ Минимальное влияние на производительность

---

## 📊 Метрики для мониторинга

```python
# Добавить в SubtaskExecutor

logger.info(
    f"Subtask {subtask_id} context created: "
    f"snapshot_size={len(snapshot['messages'])}, "
    f"cleared_messages={cleared_count}, "
    f"dependency_count={len(dependency_results)}"
)

logger.info(
    f"Subtask {subtask_id} completed: "
    f"restored_from_snapshot={snapshot_id}, "
    f"final_message_count={len(session.messages)}"
)
```

---

## 🎯 Заключение

**Рекомендуемое решение**: Вариант 1 (Session Snapshot)

**Ключевые преимущества**:
- Полная изоляция между subtasks
- Сохранение возможности rollback
- Чистая архитектура с четким разделением ответственности
- Легко тестируется и отлаживается

**Следующие шаги**:
1. Реализовать snapshot механизм в Session entity
2. Расширить SessionRepository для хранения snapshots
3. Интегрировать в SubtaskExecutor
4. Провести тестирование с реальными планами
5. Мониторить метрики и производительность
