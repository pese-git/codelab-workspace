# Фаза 2: Unified Approval System - Анализ и План Миграции

**Дата:** 03 февраля 2026  
**Статус:** 📋 Планирование  
**Цель:** Удалить дублирование approval систем (-500 строк кода)

---

## 📊 Текущее состояние

### Две параллельные системы

#### 1. **Legacy System** (ToolApprovalService)

**Файлы:**
- [`lib/features/tool_execution/data/services/tool_approval_service_impl.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/tool_execution/data/services/tool_approval_service_impl.dart) (282 строки)
- [`lib/features/tool_execution/data/services/approval_sync_service.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/tool_execution/data/services/approval_sync_service.dart) (80 строк)

**Особенности:**
- Специфична для tool approvals
- Использует `ApprovalRequestWithCompleter` wrapper
- Имеет callbacks: `onExecuteRestoredTool`, `onRejectRestoredTool`
- Хранит rejected tools в Set
- Stream: `Stream<ApprovalRequestWithCompleter>`

**Интерфейс:**
```dart
abstract class ToolApprovalService {
  Stream<ApprovalRequestWithCompleter> get approvalRequests;
  Future<ApprovalDecision> requestApproval(ToolCall toolCall);
  Future<void> restorePendingApprovals(String sessionId);
  void clearActiveCompleters();
  
  // Callbacks для восстановленных approvals
  Future<ToolResult> Function(ToolCall)? onExecuteRestoredTool;
  Future<void> Function(ToolCall, String reason)? onRejectRestoredTool;
}
```

#### 2. **Unified System** (ApprovalService)

**Файлы:**
- [`lib/features/approval/domain/services/approval_service.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/approval/domain/services/approval_service.dart) (62 строки)
- [`lib/features/approval/data/services/unified_approval_service_impl.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/approval/data/services/unified_approval_service_impl.dart) (191 строка)
- [`lib/features/approval/data/datasources/approval_api_datasource_impl.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/approval/data/datasources/approval_api_datasource_impl.dart) (120 строк)

**Особенности:**
- Универсальная для всех типов approvals (tool, plan, future types)
- Использует generic `ApprovalRequest` и `ApprovalResponse`
- Нет callbacks - чистая архитектура
- Stream: `Stream<ApprovalRequest>`
- Возвращает `List<ApprovalRequest>` из restore

**Интерфейс:**
```dart
abstract class ApprovalService {
  Future<ApprovalDecision> requestApproval(ApprovalRequest request);
  Future<List<ApprovalRequest>> restorePendingApprovals(String sessionId);
  Future<void> sendDecision(ApprovalResponse response);
  Stream<ApprovalRequest> get approvalRequests;
  void clearActiveCompleters();
  void dispose();
}
```

#### 3. **Adapter** (ToolApprovalServiceAdapter)

**Файл:**
- [`lib/features/approval/data/services/tool_approval_service_adapter.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/approval/data/services/tool_approval_service_adapter.dart) (330 строк)

**Назначение:**
- Адаптирует UnifiedApprovalService к интерфейсу ToolApprovalService
- Конвертирует между tool-specific и generic типами
- Эмулирует callbacks через внутреннюю логику

---

## 🔍 Места использования ToolApprovalService

### 1. **AgentChatBloc** (ОСНОВНОЕ)

**Файл:** [`lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/agent_chat/presentation/bloc/agent_chat_bloc.dart:92)

**Использование:**
```dart
class AgentChatBloc extends Bloc<AgentChatEvent, AgentChatState> {
  final ToolApprovalService _approvalService;  // ← Legacy
  
  StreamSubscription<ApprovalRequestWithCompleter>? _approvalSubscription;
  
  AgentChatBloc({
    required ToolApprovalService approvalService,  // ← Dependency
    // ...
  }) {
    // Подписка на approval requests
    _approvalSubscription = _approvalService.approvalRequests.listen((request) {
      add(AgentChatEvent.approvalRequested(request));
    });
    
    // Установка callbacks
    _approvalService.onExecuteRestoredTool = _executeRestoredTool;
    _approvalService.onRejectRestoredTool = _rejectRestoredTool;
  }
  
  // В _onConnect
  await _approvalService.restorePendingApprovals(event.sessionId);
  
  // В _onDisconnect
  _approvalService.clearActiveCompleters();
}
```

**Проблемы:**
- Зависимость от legacy интерфейса
- Использует callbacks вместо событий
- Подписка на `ApprovalRequestWithCompleter` вместо `ApprovalRequest`

### 2. **ToolRepositoryImpl** (КОСВЕННОЕ)

**Файл:** [`lib/features/tool_execution/data/repositories/tool_repository_impl.dart`](codelab_ide/packages/codelab_ai_assistant/lib/features/tool_execution/data/repositories/tool_repository_impl.dart)

**Использование:**
```dart
class ToolRepositoryImpl implements ToolRepository {
  final ToolApprovalService _approvalService;  // ← Legacy
  
  @override
  Future<Either<Failure, ApprovalDecision>> requestApproval(
    RequestApprovalParams params,
  ) async {
    try {
      final decision = await _approvalService.requestApproval(params.toolCall);
      return right(decision);
    } catch (e) {
      return left(Failure.unknown('Approval failed: $e'));
    }
  }
}
```

**Проблемы:**
- Прямая зависимость от ToolApprovalService
- Нужно обновить для работы с ApprovalService

### 3. **DI Configuration**

**Файл:** [`lib/ai_assistent_module.dart`](codelab_ide/packages/codelab_ai_assistant/lib/ai_assistent_module.dart:410-478)

**Текущая конфигурация:**
```dart
// Unified Approval System (новая)
bind<ApprovalApiDataSource>()
  .to<ApprovalApiDataSourceImpl>()
  .withDependencies([
    on<Dio>(),
    on<Logger>(),
  ]);

bind<ApprovalService>()
  .to<UnifiedApprovalServiceImpl>()
  .withDependencies([
    on<ApprovalApiDataSource>(),
    on<Logger>(),
  ]);

// Legacy Tool Approval (через адаптер)
bind<ToolApprovalService>()
  .to<ToolApprovalServiceAdapter>()
  .withDependencies([
    on<ApprovalService>(),
    on<Logger>(),
  ]);

// ApprovalSyncService (deprecated)
bind<ApprovalSyncService>()
  .to<ApprovalSyncService>()
  .withDependencies([
    on<GatewayApi>(),
    on<Logger>(),
  ]);
```

**Проблемы:**
- Три сервиса для одной задачи
- ApprovalSyncService дублирует функциональность ApprovalApiDataSource
- ToolApprovalServiceAdapter - временное решение

---

## 🎯 План миграции

### Этап 1: Подготовка (1 день)

#### 1.1. Создать адаптеры для обратной совместимости

**Цель:** Обеспечить плавную миграцию без breaking changes

**Создать файл:** `lib/features/approval/data/adapters/approval_request_adapter.dart`

```dart
/// Адаптер для конвертации между tool-specific и generic approval типами
class ApprovalRequestAdapter {
  /// Конвертирует ToolCall в ApprovalRequest
  static ApprovalRequest fromToolCall(ToolCall toolCall) {
    return ApprovalRequest(
      approvalRequestId: toolCall.id,
      type: ApprovalType.tool,
      requestedAt: toolCall.createdAt,
      timeoutSeconds: 300,
      data: {
        'tool_name': toolCall.toolName,
        'tool_arguments': toolCall.arguments,
        'tool_id': toolCall.id,
        'requires_approval': toolCall.requiresApproval,
        'created_at': toolCall.createdAt.toIso8601String(),
      },
    );
  }
  
  /// Конвертирует ApprovalRequest обратно в ToolCall
  static ToolCall toToolCall(ApprovalRequest request) {
    if (request.type != ApprovalType.tool) {
      throw ArgumentError('Request is not a tool approval');
    }
    
    return ToolCall(
      id: request.data['tool_id'] as String,
      toolName: request.data['tool_name'] as String,
      arguments: request.data['tool_arguments'] as Map<String, dynamic>,
      requiresApproval: request.data['requires_approval'] as bool,
      createdAt: DateTime.parse(request.data['created_at'] as String),
    );
  }
}
```

#### 1.2. Обновить тесты для новой системы

**Создать:** `test/features/approval/data/services/unified_approval_service_impl_test.dart`

```dart
void main() {
  late UnifiedApprovalServiceImpl service;
  late MockApprovalApiDataSource mockDataSource;
  late MockLogger mockLogger;
  
  setUp(() {
    mockDataSource = MockApprovalApiDataSource();
    mockLogger = MockLogger();
    service = UnifiedApprovalServiceImpl(
      apiDataSource: mockDataSource,
      logger: mockLogger,
    );
  });
  
  group('requestApproval', () {
    test('should emit request to stream and wait for decision', () async {
      // Test implementation
    });
    
    test('should timeout if no decision received', () async {
      // Test implementation
    });
  });
  
  group('restorePendingApprovals', () {
    test('should fetch and restore pending approvals', () async {
      // Test implementation
    });
  });
}
```

---

### Этап 2: Обновление AgentChatBloc (2 дня)

#### 2.1. Изменить зависимость

**Было:**
```dart
class AgentChatBloc extends Bloc<AgentChatEvent, AgentChatState> {
  final ToolApprovalService _approvalService;
  StreamSubscription<ApprovalRequestWithCompleter>? _approvalSubscription;
  
  AgentChatBloc({
    required ToolApprovalService approvalService,
    // ...
  }) : _approvalService = approvalService {
    _approvalSubscription = _approvalService.approvalRequests.listen((request) {
      add(AgentChatEvent.approvalRequested(request));
    });
    
    _approvalService.onExecuteRestoredTool = _executeRestoredTool;
    _approvalService.onRejectRestoredTool = _rejectRestoredTool;
  }
}
```

**Стало:**
```dart
class AgentChatBloc extends Bloc<AgentChatEvent, AgentChatState> {
  final ApprovalService _approvalService;  // ← Unified
  StreamSubscription<ApprovalRequest>? _approvalSubscription;  // ← Generic
  
  AgentChatBloc({
    required ApprovalService approvalService,  // ← Unified
    // ...
  }) : _approvalService = approvalService {
    // Подписка на generic approval requests
    _approvalSubscription = _approvalService.approvalRequests.listen((request) {
      // Обрабатываем все типы approvals
      _handleApprovalRequest(request);
    });
  }
  
  void _handleApprovalRequest(ApprovalRequest request) {
    request.type.when(
      tool: () {
        // Конвертируем в ToolCall и добавляем событие
        final toolCall = ApprovalRequestAdapter.toToolCall(request);
        final toolApprovalRequest = ToolApprovalRequest(
          requestId: request.approvalRequestId,
          toolCall: toolCall,
          requestedAt: request.requestedAt,
        );
        
        // Создаем completer для обратной совместимости с UI
        final completer = Completer<ApprovalDecision>();
        final requestWithCompleter = ApprovalRequestWithCompleter(
          toolApprovalRequest,
          completer,
        );
        
        add(AgentChatEvent.approvalRequested(requestWithCompleter));
        
        // Ожидаем решения и отправляем на сервер
        _waitForDecisionAndSend(request, completer);
      },
      plan: () {
        // Plan approvals уже обрабатываются через SendPlanDecisionEvent
        // Ничего не делаем здесь
      },
    );
  }
  
  Future<void> _waitForDecisionAndSend(
    ApprovalRequest request,
    Completer<ApprovalDecision> completer,
  ) async {
    try {
      final decision = await completer.future;
      
      // Отправляем решение через unified service
      final response = ApprovalResponse(
        approvalRequestId: request.approvalRequestId,
        type: request.type,
        decision: decision,
        respondedAt: DateTime.now(),
        decisionTimeMs: DateTime.now().difference(request.requestedAt).inMilliseconds,
      );
      
      await _approvalService.sendDecision(response);
      
      // Если это tool approval и approved - выполняем tool
      if (request.type == ApprovalType.tool && decision.isApproved) {
        final toolCall = ApprovalRequestAdapter.toToolCall(request);
        await _executeRestoredTool(toolCall);
      }
    } catch (e) {
      _logger.e('Error handling approval decision: $e');
    }
  }
}
```

#### 2.2. Обновить метод restore

**Было:**
```dart
Future<void> _onConnect(ConnectEvent event, Emitter<AgentChatState> emit) async {
  // ...
  try {
    await _approvalService.restorePendingApprovals(event.sessionId);
    _logger.i('Pending approvals restored successfully');
  } catch (e) {
    _logger.e('Failed to restore pending approvals: $e');
  }
}
```

**Стало:**
```dart
Future<void> _onConnect(ConnectEvent event, Emitter<AgentChatState> emit) async {
  // ...
  try {
    final restoredApprovals = await _approvalService.restorePendingApprovals(event.sessionId);
    _logger.i('Restored ${restoredApprovals.length} pending approvals');
    
    // Approvals уже эмитированы в stream, просто логируем
  } catch (e) {
    _logger.e('Failed to restore pending approvals: $e');
  }
}
```

#### 2.3. Удалить callbacks

**Удалить:**
```dart
// ❌ Удалить эти строки
_approvalService.onExecuteRestoredTool = _executeRestoredTool;
_approvalService.onRejectRestoredTool = _rejectRestoredTool;
```

**Причина:** Callbacks заменены на event-driven подход через `_waitForDecisionAndSend`

---

### Этап 3: Обновление ToolRepository (1 день)

#### 3.1. Изменить интерфейс

**Было:**
```dart
class ToolRepositoryImpl implements ToolRepository {
  final ToolApprovalService _approvalService;
  
  @override
  Future<Either<Failure, ApprovalDecision>> requestApproval(
    RequestApprovalParams params,
  ) async {
    try {
      final decision = await _approvalService.requestApproval(params.toolCall);
      return right(decision);
    } catch (e) {
      return left(Failure.unknown('Approval failed: $e'));
    }
  }
}
```

**Стало:**
```dart
class ToolRepositoryImpl implements ToolRepository {
  final ApprovalService _approvalService;  // ← Unified
  
  @override
  Future<Either<Failure, ApprovalDecision>> requestApproval(
    RequestApprovalParams params,
  ) async {
    try {
      // Конвертируем ToolCall в ApprovalRequest
      final approvalRequest = ApprovalRequestAdapter.fromToolCall(params.toolCall);
      
      // Запрашиваем подтверждение через unified service
      final decision = await _approvalService.requestApproval(approvalRequest);
      
      return right(decision);
    } catch (e) {
      return left(Failure.unknown('Approval failed: $e'));
    }
  }
}
```

---

### Этап 4: Обновление DI (1 день)

#### 4.1. Удалить legacy bindings

**Удалить из `ai_assistent_module.dart`:**
```dart
// ❌ Удалить
bind<ToolApprovalService>()
  .to<ToolApprovalServiceAdapter>()
  .withDependencies([
    on<ApprovalService>(),
    on<Logger>(),
  ]);

// ❌ Удалить
bind<ApprovalSyncService>()
  .to<ApprovalSyncService>()
  .withDependencies([
    on<GatewayApi>(),
    on<Logger>(),
  ]);
```

#### 4.2. Обновить зависимости

**Обновить:**
```dart
// ToolRepository теперь зависит от ApprovalService
bind<ToolRepository>()
  .to<ToolRepositoryImpl>()
  .withDependencies([
    on<ToolExecutorDataSource>(),
    on<ApprovalService>(),  // ← Было: ToolApprovalService
  ]);

// AgentChatBloc теперь зависит от ApprovalService
bind<AgentChatBloc>()
  .to<AgentChatBloc>()
  .withDependencies([
    // ...
    on<ApprovalService>(),  // ← Было: ToolApprovalService
    on<Logger>(),
  ]);
```

---

### Этап 5: Удаление legacy кода (1 день)

#### 5.1. Удалить файлы

**Удалить:**
1. `lib/features/tool_execution/data/services/tool_approval_service_impl.dart` (282 строки)
2. `lib/features/tool_execution/data/services/approval_sync_service.dart` (80 строк)
3. `lib/features/approval/data/services/tool_approval_service_adapter.dart` (330 строк)

**Итого удалено:** ~692 строки

#### 5.2. Обновить экспорты

**Файл:** `lib/codelab_ai_assistant.dart`

**Удалить:**
```dart
// ❌ Удалить legacy экспорты
export 'features/tool_execution/data/services/tool_approval_service_impl.dart';
export 'features/tool_execution/data/services/approval_sync_service.dart';
```

**Добавить:**
```dart
// ✅ Экспортировать unified систему
export 'features/approval/domain/services/approval_service.dart';
export 'features/approval/data/services/unified_approval_service_impl.dart';
export 'features/approval/data/adapters/approval_request_adapter.dart';
```

---

### Этап 6: Обновление тестов (1 день)

#### 6.1. Обновить AgentChatBloc тесты

**Файл:** `test/features/agent_chat/presentation/bloc/agent_chat_bloc_test.dart`

**Обновить моки:**
```dart
class MockApprovalService extends Mock implements ApprovalService {}  // ← Было: MockToolApprovalService

void main() {
  late AgentChatBloc bloc;
  late MockApprovalService mockApprovalService;  // ← Unified
  
  setUp(() {
    mockApprovalService = MockApprovalService();
    
    // Настройка stream
    when(() => mockApprovalService.approvalRequests)
        .thenAnswer((_) => Stream<ApprovalRequest>.empty());
    
    bloc = AgentChatBloc(
      approvalService: mockApprovalService,  // ← Unified
      // ...
    );
  });
  
  group('approval handling', () {
    test('should handle tool approval request', () async {
      // Создаем ApprovalRequest вместо ToolApprovalRequest
      final approvalRequest = ApprovalRequest(
        approvalRequestId: 'test-id',
        type: ApprovalType.tool,
        requestedAt: DateTime.now(),
        data: {
          'tool_name': 'test_tool',
          'tool_arguments': {},
          'tool_id': 'test-id',
          'requires_approval': true,
          'created_at': DateTime.now().toIso8601String(),
        },
      );
      
      // Эмитируем через stream
      final controller = StreamController<ApprovalRequest>();
      when(() => mockApprovalService.approvalRequests)
          .thenAnswer((_) => controller.stream);
      
      controller.add(approvalRequest);
      
      // Проверяем обработку
      await expectLater(
        bloc.stream,
        emitsInOrder([
          predicate<AgentChatState>((state) => state.pendingApproval.isSome()),
        ]),
      );
    });
  });
}
```

#### 6.2. Обновить ToolRepository тесты

**Файл:** `test/features/tool_execution/data/repositories/tool_repository_impl_test.dart`

**Обновить:**
```dart
class MockApprovalService extends Mock implements ApprovalService {}  // ← Unified

void main() {
  late ToolRepositoryImpl repository;
  late MockApprovalService mockApprovalService;
  
  setUp(() {
    mockApprovalService = MockApprovalService();
    repository = ToolRepositoryImpl(
      approvalService: mockApprovalService,  // ← Unified
      // ...
    );
  });
  
  test('requestApproval should convert ToolCall to ApprovalRequest', () async {
    final toolCall = ToolCall(
      id: 'test-id',
      toolName: 'test_tool',
      arguments: {},
      requiresApproval: true,
      createdAt: DateTime.now(),
    );
    
    when(() => mockApprovalService.requestApproval(any()))
        .thenAnswer((_) async => const ApprovalDecision.approved());
    
    final result = await repository.requestApproval(
      RequestApprovalParams(toolCall: toolCall),
    );
    
    expect(result.isRight(), true);
    verify(() => mockApprovalService.requestApproval(any())).called(1);
  });
}
```

---

## 📊 Ожидаемые результаты

### Метрики

| Метрика | До | После | Изменение |
|---------|-----|-------|-----------|
| Файлов approval систем | 6 | 3 | -50% |
| Строк кода | ~1,200 | ~500 | -58% |
| Интерфейсов | 2 | 1 | -50% |
| DI bindings | 3 | 1 | -67% |
| Дублирование логики | Высокое | Нет | -100% |

### Преимущества

✅ **Единая система** - один сервис для всех типов approvals  
✅ **Чистая архитектура** - нет callbacks, event-driven подход  
✅ **Расширяемость** - легко добавить новые типы approvals  
✅ **Меньше кода** - удалено ~700 строк  
✅ **Проще поддержка** - одна точка изменений  
✅ **Лучшая тестируемость** - меньше моков, проще тесты

---

## ⚠️ Риски и митигация

### Риск 1: Breaking changes для внешних потребителей

**Вероятность:** Средняя  
**Влияние:** Высокое

**Митигация:**
- Создать адаптеры для обратной совместимости
- Обновить все внутренние использования
- Добавить deprecation warnings
- Документировать миграцию

### Риск 2: Регрессия в approval flow

**Вероятность:** Низкая  
**Влияние:** Высокое

**Митигация:**
- Полное покрытие тестами перед миграцией
- Тестирование на dev окружении
- Feature flags для постепенного rollout
- Мониторинг ошибок

### Риск 3: Проблемы с восстановлением pending approvals

**Вероятность:** Средняя  
**Влияние:** Среднее

**Митигация:**
- Тщательное тестирование restore логики
- Логирование всех этапов восстановления
- Graceful degradation при ошибках
- Ручное тестирование сценариев

---

## 📋 Чеклист выполнения

### Подготовка
- [ ] Создать адаптеры для конвертации типов
- [ ] Написать тесты для UnifiedApprovalService
- [ ] Создать feature flag `useUnifiedApprovalOnly`

### Миграция
- [ ] Обновить AgentChatBloc
  - [ ] Изменить зависимость на ApprovalService
  - [ ] Обновить подписку на stream
  - [ ] Удалить callbacks
  - [ ] Обновить restore логику
- [ ] Обновить ToolRepository
  - [ ] Изменить зависимость на ApprovalService
  - [ ] Добавить конвертацию типов
- [ ] Обновить DI конфигурацию
  - [ ] Удалить ToolApprovalService binding
  - [ ] Удалить ApprovalSyncService binding
  - [ ] Обновить зависимости

### Очистка
- [ ] Удалить legacy файлы
  - [ ] tool_approval_service_impl.dart
  - [ ] approval_sync_service.dart
  - [ ] tool_approval_service_adapter.dart
- [ ] Обновить экспорты
- [ ] Удалить неиспользуемые импорты

### Тестирование
- [ ] Обновить все тесты
- [ ] Запустить полный test suite
- [ ] Ручное тестирование approval flow
- [ ] Тестирование restore pending approvals
- [ ] Проверка на dev окружении

### Документация
- [ ] Обновить MIGRATION_GUIDE.md
- [ ] Создать CHANGELOG entry
- [ ] Обновить API документацию
- [ ] Добавить примеры использования

---

## 🎯 Критерии успеха

1. ✅ Все тесты проходят (100% success rate)
2. ✅ Удалено минимум 500 строк кода
3. ✅ Нет дублирования approval логики
4. ✅ Approval flow работает идентично
5. ✅ Restore pending approvals работает корректно
6. ✅ Нет breaking changes для внешних API
7. ✅ Документация обновлена

---

## 📅 Временная оценка

| Этап | Время | Зависимости |
|------|-------|-------------|
| 1. Подготовка | 1 день | - |
| 2. AgentChatBloc | 2 дня | Этап 1 |
| 3. ToolRepository | 1 день | Этап 1 |
| 4. DI конфигурация | 1 день | Этапы 2-3 |
| 5. Удаление legacy | 1 день | Этап 4 |
| 6. Тестирование | 1 день | Этап 5 |
| **Итого** | **7 дней** | |

---

## 🚀 Следующие шаги

После завершения Фазы 2:

1. **Фаза 4:** BLoC Middleware (упрощение AgentChatBloc)
2. **Фаза 5:** Полная реализация протокола
3. **Оптимизация:** Performance improvements

---

**Дата создания:** 03 февраля 2026  
**Автор:** AI Code Analyzer  
**Статус:** ✅ Готово к выполнению
