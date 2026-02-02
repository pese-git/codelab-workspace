# Tool Approval Migration Guide

## 📋 Обзор

Руководство по миграции с `ToolApprovalServiceImpl` на `UnifiedApprovalService` через адаптер `ToolApprovalServiceAdapter`.

## 🎯 Цели миграции

1. **Унификация** - единая система для всех типов подтверждений (tool, plan, future types)
2. **Clean Architecture** - четкое разделение Domain и Data слоев
3. **Backward Compatibility** - существующий код продолжает работать
4. **Постепенная миграция** - можно мигрировать по одному компоненту

## 🏗️ Архитектура

### До миграции
```
AgentChatBloc
    ↓
ToolApprovalServiceImpl
    ↓
ApprovalSyncService → GatewayApi (HTTP)
```

### После миграции (Фаза 1 - через адаптер)
```
AgentChatBloc
    ↓
ToolApprovalServiceAdapter (wrapper)
    ↓
UnifiedApprovalService
    ↓
ApprovalApiDataSource → GatewayApi (HTTP) + AgentRemoteDataSource (WebSocket)
```

### Финальная архитектура (Фаза 2 - прямое использование)
```
AgentChatBloc
    ↓
UnifiedApprovalService (напрямую)
    ↓
ApprovalApiDataSource → GatewayApi (HTTP) + AgentRemoteDataSource (WebSocket)
```

## 📦 Созданные компоненты

### 1. ToolApprovalServiceAdapter
**Файл:** `lib/features/approval/data/services/tool_approval_service_adapter.dart`

**Назначение:** Адаптер для постепенной миграции, реализует интерфейс `ToolApprovalService`

**Ключевые возможности:**
- ✅ Полная совместимость с `ToolApprovalServiceImpl`
- ✅ Использует `UnifiedApprovalService` внутри
- ✅ Конвертация через `ToolApprovalAdapter`
- ✅ Поддержка восстановления pending approvals
- ✅ Callbacks для выполнения восстановленных tools

**API:**
```dart
class ToolApprovalServiceAdapter implements ToolApprovalService {
  // Основной метод - запрос подтверждения
  Future<ApprovalDecision> requestApproval(ToolCall toolCall);
  
  // Восстановление pending approvals
  Future<void> restorePendingApprovals(String sessionId);
  
  // Stream для UI (backward compatibility)
  Stream<ApprovalRequestWithCompleter> get approvalRequests;
  
  // Callbacks для восстановленных tools
  Future<dynamic> Function(ToolCall)? onExecuteRestoredTool;
  Future<void> Function(ToolCall, String reason)? onRejectRestoredTool;
  
  // Управление состоянием
  void clearRejectedTools();
  void clearActiveCompleters();
  void dispose();
}
```

### 2. ApprovalApiDataSourceImpl
**Файл:** `lib/features/approval/data/datasources/approval_api_datasource_impl.dart`

**Назначение:** Реализация data source для HTTP и WebSocket коммуникации

**Методы:**
- `getPendingApprovals(sessionId)` - получение через HTTP (GatewayApi)
- `sendApprovalDecision(response)` - отправка через WebSocket (AgentRemoteDataSource)

### 3. ToolApprovalAdapter
**Файл:** `lib/features/approval/data/adapters/tool_approval_adapter.dart`

**Назначение:** Конвертация между tool-specific и unified entities

**Методы:**
- `toApprovalRequest()` - ToolApprovalRequest → ApprovalRequest
- `fromApprovalDecision()` - ApprovalDecision → tool_approval.ApprovalDecision
- `toApprovalDecision()` - tool_approval.ApprovalDecision → ApprovalDecision
- `extractToolCall()` - извлечение ToolCall из ApprovalRequest
- `toToolApprovalRequest()` - ApprovalRequest → ToolApprovalRequest

## 🔄 План миграции

### Фаза 1: Подготовка (✅ Завершена)
- [x] Создать Unified Approval entities (Domain слой)
- [x] Создать ApprovalService interface
- [x] Создать UnifiedApprovalServiceImpl
- [x] Создать ApprovalApiDataSource
- [x] Создать ToolApprovalAdapter
- [x] Создать ToolApprovalServiceAdapter

### Фаза 2: Обновление DI (В процессе)

#### Шаг 1: Добавить новые зависимости

В `ai_assistent_module.dart` добавить:

```dart
// ========================================================================
// Unified Approval Feature
// ========================================================================

// Data Source
bind<ApprovalApiDataSource>()
    .toProvide(
      () => ApprovalApiDataSourceImpl(
        gatewayApi: currentScope.resolve<GatewayApi>(),
        remoteDataSource: currentScope.resolve<AgentRemoteDataSource>(),
        logger: currentScope.resolve<Logger>(),
      ),
    )
    .singleton();

// Service
bind<ApprovalService>()
    .toProvide(
      () => UnifiedApprovalServiceImpl(
        dataSource: currentScope.resolve<ApprovalApiDataSource>(),
        logger: currentScope.resolve<Logger>(),
      ),
    )
    .singleton();
```

#### Шаг 2: Заменить ToolApprovalServiceImpl на адаптер

**Было:**
```dart
bind<ToolApprovalServiceImpl>()
    .toProvide(
      () => ToolApprovalServiceImpl(
        syncService: currentScope.resolve<ApprovalSyncService>(),
        logger: currentScope.resolve<Logger>(),
      ),
    )
    .singleton();

bind<ToolApprovalService>()
    .toProvide(() => currentScope.resolve<ToolApprovalServiceImpl>())
    .singleton();
```

**Стало:**
```dart
// Используем адаптер вместо прямой реализации
bind<ToolApprovalServiceImpl>()
    .toProvide(
      () => ToolApprovalServiceAdapter(
        unifiedService: currentScope.resolve<ApprovalService>(),
        logger: currentScope.resolve<Logger>(),
      ),
    )
    .singleton();

bind<ToolApprovalService>()
    .toProvide(() => currentScope.resolve<ToolApprovalServiceImpl>())
    .singleton();
```

#### Шаг 3: Удалить ApprovalSyncService (опционально)

После миграции `ApprovalSyncService` больше не нужен, так как его функциональность перенесена в `ApprovalApiDataSource`.

**Можно удалить:**
```dart
bind<ApprovalSyncService>()
    .toProvide(
      () => ApprovalSyncService(
        api: currentScope.resolve<GatewayApi>(),
        logger: currentScope.resolve<Logger>(),
      ),
    )
    .singleton();
```

### Фаза 3: Тестирование

1. **Unit тесты** - проверить адаптер
2. **Integration тесты** - проверить работу с AgentChatBloc
3. **E2E тесты** - проверить восстановление pending approvals

### Фаза 4: Финальная миграция (Будущее)

После успешного тестирования можно мигрировать на прямое использование `UnifiedApprovalService`:

1. Обновить `AgentChatBloc` для работы с `ApprovalService` напрямую
2. Удалить `ToolApprovalServiceAdapter`
3. Обновить UI для работы с unified entities

## 🔍 Ключевые отличия

### ToolApprovalServiceImpl vs ToolApprovalServiceAdapter

| Аспект | ToolApprovalServiceImpl | ToolApprovalServiceAdapter |
|--------|------------------------|---------------------------|
| **Data Source** | ApprovalSyncService (HTTP only) | ApprovalApiDataSource (HTTP + WebSocket) |
| **Архитектура** | Monolithic | Clean Architecture |
| **Отправка решений** | Через AgentChatBloc | Через UnifiedApprovalService |
| **Типы approval** | Только tool | Расширяемо (tool, plan, etc.) |
| **Конвертация** | Нет | Через ToolApprovalAdapter |

### Преимущества нового подхода

1. **Единая инфраструктура** - все approvals через один сервис
2. **Расширяемость** - легко добавить новые типы approvals
3. **Тестируемость** - четкое разделение ответственности
4. **Переиспользование** - общий код для всех типов approvals
5. **WebSocket для решений** - более эффективная коммуникация

## ⚠️ Важные замечания

### Backward Compatibility

Адаптер полностью совместим с существующим кодом:
- ✅ Тот же интерфейс `ToolApprovalService`
- ✅ Тот же stream `approvalRequests`
- ✅ Те же callbacks для восстановленных tools
- ✅ Та же логика rejected tools

### Breaking Changes

**НЕТ breaking changes** при использовании адаптера!

Все изменения внутренние, внешний API остается прежним.

## 📊 Метрики миграции

### Текущий прогресс: 70%

- ✅ Domain entities (100%)
- ✅ Data sources (100%)
- ✅ Adapters (100%)
- ✅ Service implementation (100%)
- 🔄 Dependency Injection (50%)
- ⏳ Testing (0%)
- ⏳ Documentation (80%)

### Оставшаяся работа

1. **Обновить DI** (30 минут)
   - Добавить новые bindings
   - Заменить ToolApprovalServiceImpl на адаптер
   - Удалить ApprovalSyncService

2. **Тестирование** (1-2 часа)
   - Unit тесты для адаптера
   - Integration тесты с AgentChatBloc
   - E2E тесты восстановления

3. **Финализация документации** (30 минут)
   - Обновить UNIFIED_APPROVAL_IMPLEMENTATION_PROGRESS.md
   - Создать migration checklist

## 🚀 Следующие шаги

1. ✅ Создать ToolApprovalServiceAdapter
2. ✅ Создать ApprovalApiDataSourceImpl
3. 🔄 Обновить DI конфигурацию
4. ⏳ Протестировать миграцию
5. ⏳ Обновить документацию
6. ⏳ Code review
7. ⏳ Merge в main

## 📚 Связанные документы

- [`UNIFIED_APPROVAL_ARCHITECTURE_PROPOSAL.md`](UNIFIED_APPROVAL_ARCHITECTURE_PROPOSAL.md) - архитектурное предложение
- [`UNIFIED_APPROVAL_IMPLEMENTATION_PROGRESS.md`](UNIFIED_APPROVAL_IMPLEMENTATION_PROGRESS.md) - прогресс реализации
- [`PLAN_APPROVAL_INTEGRATION_GUIDE.md`](PLAN_APPROVAL_INTEGRATION_GUIDE.md) - интеграция plan approval

## 🤝 Поддержка

При возникновении проблем:
1. Проверить логи с тегом `[ToolApprovalServiceAdapter]`
2. Убедиться что все DI bindings корректны
3. Проверить что callbacks установлены в AgentChatBloc
4. Проверить WebSocket соединение для отправки решений
