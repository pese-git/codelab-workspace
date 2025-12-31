# Руководство по интеграции IDE с Gateway Service

## 📋 Обзор архитектуры

```
┌─────────────────┐         WebSocket          ┌─────────────────┐         HTTP/SSE         ┌─────────────────┐
│                 │ ◄─────────────────────────► │                 │ ◄──────────────────────► │                 │
│   IDE Client    │         (Port 8000)         │    Gateway      │        (Internal)        │ Agent Runtime   │
│   (Flutter)     │                             │   (FastAPI)     │                          │   (FastAPI)     │
│                 │                             │                 │                          │                 │
└─────────────────┘                             └─────────────────┘                          └─────────────────┘
     Единственный                                   Port: 8000                                   Port: 8001
     точка доступа                                  Проксирует все                              (Недоступен
                                                    REST endpoints                               напрямую)
```

### Роли компонентов

1. **IDE Client (Flutter)** - пользовательский интерфейс
   - ✅ Общается **ТОЛЬКО** с Gateway Service (порт 8000)
   - ✅ WebSocket для стриминга сообщений
   - ✅ REST API для управления сессиями (через Gateway)
   - ❌ **НЕ имеет прямого доступа** к Agent Runtime
   - Отправляет сообщения пользователя
   - Выполняет tool calls (file operations, commands)
   - Отображает ответы агента
   - Запрашивает подтверждения (HITL)

2. **Gateway Service** - единая точка входа и прокси
   - Преобразует WebSocket ↔ HTTP/SSE
   - **Проксирует все REST API endpoints** от Agent Runtime
   - Управляет WebSocket соединениями
   - Пересылает сообщения между IDE и Agent Runtime
   - Добавляет внутреннюю аутентификацию (`X-Internal-Auth`)
   - Не содержит бизнес-логики

3. **Agent Runtime** - AI движок (внутренний сервис)
   - ❌ **Недоступен напрямую** для IDE
   - ✅ Доступен только через Gateway
   - Мультиагентная система (5 агентов)
   - Интеграция с LLM
   - Управление сессиями и контекстом
   - Генерация tool calls

---

## 🔌 WebSocket протокол (IDE ↔ Gateway)

### Подключение

```dart
// Flutter WebSocket подключение
final uri = Uri.parse('ws://localhost:8000/ws/$sessionId');
final channel = WebSocketChannel.connect(uri);

await channel.ready;
print('WebSocket connected');
```

### Типы сообщений

#### 1. User Message (IDE → Gateway)

**Назначение:** Отправка сообщения пользователя агенту

```json
{
  "type": "user_message",
  "role": "user",
  "content": "Create a Flutter widget for user profile"
}
```

**Dart модель:**
```dart
class WSUserMessage {
  final String type = 'user_message';
  final String role;
  final String content;
  
  WSUserMessage({
    required this.role,
    required this.content,
  });
  
  Map<String, dynamic> toJson() => {
    'type': type,
    'role': role,
    'content': content,
  };
}
```

#### 2. Tool Result (IDE → Gateway)

**Назначение:** Отправка результата выполнения инструмента

```json
{
  "type": "tool_result",
  "call_id": "call_abc123",
  "result": {
    "content": "file content here",
    "success": true
  }
}
```

**Или с ошибкой:**
```json
{
  "type": "tool_result",
  "call_id": "call_abc123",
  "error": "File not found: /path/to/file.dart"
}
```

**Dart модель:**
```dart
class WSToolResult {
  final String type = 'tool_result';
  final String callId;
  final Map<String, dynamic>? result;
  final String? error;
  
  WSToolResult({
    required this.callId,
    this.result,
    this.error,
  });
  
  Map<String, dynamic> toJson() => {
    'type': type,
    'call_id': callId,
    if (result != null) 'result': result,
    if (error != null) 'error': error,
  };
}
```

#### 3. Switch Agent (IDE → Gateway)

**Назначение:** Явное переключение на другого агента

```json
{
  "type": "switch_agent",
  "agent_type": "architect",
  "content": "Design the authentication system",
  "reason": "User requested architect mode"
}
```

**Dart модель:**
```dart
class WSSwitchAgent {
  final String type = 'switch_agent';
  final String agentType;
  final String content;
  final String? reason;
  
  WSSwitchAgent({
    required this.agentType,
    required this.content,
    this.reason,
  });
  
  Map<String, dynamic> toJson() => {
    'type': type,
    'agent_type': agentType,
    'content': content,
    if (reason != null) 'reason': reason,
  };
}
```

#### 4. HITL Decision (IDE → Gateway)

**Назначение:** Решение пользователя по подтверждению опасной операции

```json
{
  "type": "hitl_decision",
  "call_id": "call_abc123",
  "decision": "approve"
}
```

**С модификацией аргументов:**
```json
{
  "type": "hitl_decision",
  "call_id": "call_abc123",
  "decision": "edit",
  "modified_arguments": {
    "path": "/src/main_v2.dart"
  }
}
```

**С отклонением:**
```json
{
  "type": "hitl_decision",
  "call_id": "call_abc123",
  "decision": "reject",
  "feedback": "This operation is too risky"
}
```

**Dart модель:**
```dart
class WSHITLDecision {
  final String type = 'hitl_decision';
  final String callId;
  final String decision; // 'approve', 'edit', 'reject'
  final Map<String, dynamic>? modifiedArguments;
  final String? feedback;
  
  WSHITLDecision({
    required this.callId,
    required this.decision,
    this.modifiedArguments,
    this.feedback,
  });
  
  Map<String, dynamic> toJson() => {
    'type': type,
    'call_id': callId,
    'decision': decision,
    if (modifiedArguments != null) 'modified_arguments': modifiedArguments,
    if (feedback != null) 'feedback': feedback,
  };
}
```

---

### Входящие сообщения (Gateway → IDE)

#### 1. Assistant Message (стриминг)

**Назначение:** Текстовый ответ агента (по токенам)

```json
{
  "type": "assistant_message",
  "token": "I'll create ",
  "is_final": false
}
```

**Финальный chunk:**
```json
{
  "type": "assistant_message",
  "token": "",
  "is_final": true
}
```

**Dart модель:**
```dart
class WSAssistantMessage {
  final String type;
  final String? token;
  final bool isFinal;
  
  WSAssistantMessage.fromJson(Map<String, dynamic> json)
      : type = json['type'],
        token = json['token'],
        isFinal = json['is_final'] ?? false;
}
```

#### 2. Tool Call

**Назначение:** Запрос на выполнение инструмента

```json
{
  "type": "tool_call",
  "call_id": "call_abc123",
  "tool_name": "read_file",
  "arguments": {
    "path": "/src/main.dart"
  },
  "requires_approval": false
}
```

**С требованием подтверждения:**
```json
{
  "type": "tool_call",
  "call_id": "call_xyz789",
  "tool_name": "write_file",
  "arguments": {
    "path": "/src/main.dart",
    "content": "new content"
  },
  "requires_approval": true
}
```

**Dart модель:**
```dart
class WSToolCall {
  final String type;
  final String callId;
  final String toolName;
  final Map<String, dynamic> arguments;
  final bool requiresApproval;
  
  WSToolCall.fromJson(Map<String, dynamic> json)
      : type = json['type'],
        callId = json['call_id'],
        toolName = json['tool_name'],
        arguments = json['arguments'],
        requiresApproval = json['requires_approval'] ?? false;
}
```

#### 3. Agent Switched

**Назначение:** Уведомление о переключении агента

```json
{
  "type": "agent_switched",
  "content": "Switched to coder agent",
  "metadata": {
    "from_agent": "orchestrator",
    "to_agent": "coder",
    "reason": "Coding task detected",
    "confidence": "high"
  }
}
```

**Dart модель:**
```dart
class WSAgentSwitched {
  final String type;
  final String content;
  final String fromAgent;
  final String toAgent;
  final String reason;
  final String? confidence;
  
  WSAgentSwitched.fromJson(Map<String, dynamic> json)
      : type = json['type'],
        content = json['content'],
        fromAgent = json['metadata']['from_agent'],
        toAgent = json['metadata']['to_agent'],
        reason = json['metadata']['reason'],
        confidence = json['metadata']['confidence'];
}
```

#### 4. Error

**Назначение:** Сообщение об ошибке

```json
{
  "type": "error",
  "error": "Failed to process request",
  "is_final": true
}
```

**Dart модель:**
```dart
class WSError {
  final String type;
  final String error;
  final bool isFinal;
  
  WSError.fromJson(Map<String, dynamic> json)
      : type = json['type'],
        error = json['error'],
        isFinal = json['is_final'] ?? true;
}
```

---

## 🔄 Полный поток взаимодействия

### Сценарий 1: Простой запрос

```
1. User вводит: "Create a Flutter widget"
   ↓
2. IDE → Gateway (WebSocket):
   {
     "type": "user_message",
     "role": "user",
     "content": "Create a Flutter widget"
   }
   ↓
3. Gateway → Agent Runtime (HTTP POST /agent/message/stream):
   {
     "session_id": "session_123",
     "message": {
       "type": "user_message",
       "content": "Create a Flutter widget"
     }
   }
   ↓
4. Agent Runtime → Gateway (SSE stream):
   event: message
   data: {"type":"agent_switched","content":"Switched to coder agent",...}
   
   event: message
   data: {"type":"assistant_message","token":"I'll ","is_final":false}
   
   event: message
   data: {"type":"assistant_message","token":"create ","is_final":false}
   
   event: message
   data: {"type":"tool_call","call_id":"call_123","tool_name":"write_file",...}
   
   event: done
   data: {"status":"completed"}
   ↓
5. Gateway → IDE (WebSocket):
   {"type":"agent_switched",...}
   {"type":"assistant_message","token":"I'll ",...}
   {"type":"assistant_message","token":"create ",...}
   {"type":"tool_call","call_id":"call_123",...}
   ↓
6. IDE выполняет write_file
   ↓
7. IDE → Gateway (WebSocket):
   {
     "type": "tool_result",
     "call_id": "call_123",
     "result": {"success": true}
   }
   ↓
8. Gateway → Agent Runtime (HTTP POST /agent/message/stream):
   {
     "session_id": "session_123",
     "message": {
       "type": "tool_result",
       "call_id": "call_123",
       "result": {"success": true}
     }
   }
   ↓
9. Agent Runtime → Gateway → IDE:
   {"type":"assistant_message","content":"Widget created successfully","is_final":true}
```

### Сценарий 2: HITL подтверждение

```
1. Agent генерирует опасный tool_call:
   {
     "type": "tool_call",
     "call_id": "call_456",
     "tool_name": "execute_command",
     "arguments": {"command": "rm -rf /tmp/*"},
     "requires_approval": true
   }
   ↓
2. IDE показывает диалог подтверждения
   ↓
3. User нажимает "Approve" / "Edit" / "Reject"
   ↓
4. IDE → Gateway:
   {
     "type": "hitl_decision",
     "call_id": "call_456",
     "decision": "approve"
   }
   ↓
5. Gateway → Agent Runtime
   ↓
6. Agent Runtime выполняет или отклоняет операцию
```

---

## 💻 Реализация на Flutter

### 1. WebSocket Service

```dart
import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';

class WebSocketService {
  WebSocketChannel? _channel;
  final String baseUrl;
  final StreamController<Map<String, dynamic>> _messageController = 
      StreamController.broadcast();
  
  Stream<Map<String, dynamic>> get messages => _messageController.stream;
  
  WebSocketService({required this.baseUrl});
  
  Future<void> connect(String sessionId) async {
    final uri = Uri.parse('$baseUrl/ws/$sessionId');
    _channel = WebSocketChannel.connect(uri);
    
    await _channel!.ready;
    print('WebSocket connected to session: $sessionId');
    
    // Слушаем входящие сообщения
    _channel!.stream.listen(
      (data) {
        try {
          final json = jsonDecode(data);
          _messageController.add(json);
        } catch (e) {
          print('Error parsing message: $e');
        }
      },
      onError: (error) {
        print('WebSocket error: $error');
        _messageController.addError(error);
      },
      onDone: () {
        print('WebSocket closed');
      },
    );
  }
  
  void sendMessage(Map<String, dynamic> message) {
    if (_channel == null) {
      throw Exception('WebSocket not connected');
    }
    
    final json = jsonEncode(message);
    _channel!.sink.add(json);
    print('Sent: $json');
  }
  
  void sendUserMessage(String content) {
    sendMessage({
      'type': 'user_message',
      'role': 'user',
      'content': content,
    });
  }
  
  void sendToolResult(String callId, {Map<String, dynamic>? result, String? error}) {
    sendMessage({
      'type': 'tool_result',
      'call_id': callId,
      if (result != null) 'result': result,
      if (error != null) 'error': error,
    });
  }
  
  void sendSwitchAgent(String agentType, String content, {String? reason}) {
    sendMessage({
      'type': 'switch_agent',
      'agent_type': agentType,
      'content': content,
      if (reason != null) 'reason': reason,
    });
  }
  
  void sendHITLDecision(
    String callId,
    String decision, {
    Map<String, dynamic>? modifiedArguments,
    String? feedback,
  }) {
    sendMessage({
      'type': 'hitl_decision',
      'call_id': callId,
      'decision': decision,
      if (modifiedArguments != null) 'modified_arguments': modifiedArguments,
      if (feedback != null) 'feedback': feedback,
    });
  }
  
  void disconnect() {
    _channel?.sink.close();
    _channel = null;
  }
  
  void dispose() {
    disconnect();
    _messageController.close();
  }
}
```

### 2. Message Handler

```dart
class MessageHandler {
  final WebSocketService wsService;
  final ToolExecutor toolExecutor;
  final HITLManager hitlManager;
  
  MessageHandler({
    required this.wsService,
    required this.toolExecutor,
    required this.hitlManager,
  });
  
  void startListening() {
    wsService.messages.listen((message) {
      final type = message['type'];
      
      switch (type) {
        case 'assistant_message':
          _handleAssistantMessage(message);
          break;
        case 'tool_call':
          _handleToolCall(message);
          break;
        case 'agent_switched':
          _handleAgentSwitched(message);
          break;
        case 'error':
          _handleError(message);
          break;
        default:
          print('Unknown message type: $type');
      }
    });
  }
  
  void _handleAssistantMessage(Map<String, dynamic> message) {
    final token = message['token'] as String?;
    final isFinal = message['is_final'] as bool;
    
    if (token != null && token.isNotEmpty) {
      // Добавить токен к текущему сообщению
      print('Token: $token');
    }
    
    if (isFinal) {
      print('Message completed');
    }
  }
  
  Future<void> _handleToolCall(Map<String, dynamic> message) async {
    final callId = message['call_id'] as String;
    final toolName = message['tool_name'] as String;
    final arguments = message['arguments'] as Map<String, dynamic>;
    final requiresApproval = message['requires_approval'] as bool? ?? false;
    
    if (requiresApproval) {
      // Показать диалог подтверждения
      await hitlManager.requestApproval(
        callId: callId,
        toolName: toolName,
        arguments: arguments,
      );
    } else {
      // Выполнить инструмент сразу
      await _executeToolCall(callId, toolName, arguments);
    }
  }
  
  Future<void> _executeToolCall(
    String callId,
    String toolName,
    Map<String, dynamic> arguments,
  ) async {
    try {
      final result = await toolExecutor.execute(toolName, arguments);
      wsService.sendToolResult(callId, result: result);
    } catch (e) {
      wsService.sendToolResult(callId, error: e.toString());
    }
  }
  
  void _handleAgentSwitched(Map<String, dynamic> message) {
    final content = message['content'] as String;
    final metadata = message['metadata'] as Map<String, dynamic>?;
    
    if (metadata != null) {
      final fromAgent = metadata['from_agent'];
      final toAgent = metadata['to_agent'];
      print('Agent switched: $fromAgent → $toAgent');
    }
  }
  
  void _handleError(Map<String, dynamic> message) {
    final error = message['error'] as String;
    print('Error: $error');
    // Показать ошибку пользователю
  }
}
```

### 3. Tool Executor

```dart
class ToolExecutor {
  Future<Map<String, dynamic>> execute(
    String toolName,
    Map<String, dynamic> arguments,
  ) async {
    switch (toolName) {
      case 'read_file':
        return await _readFile(arguments['path']);
      case 'write_file':
        return await _writeFile(arguments['path'], arguments['content']);
      case 'list_files':
        return await _listFiles(arguments['path']);
      case 'execute_command':
        return await _executeCommand(arguments['command']);
      default:
        throw Exception('Unknown tool: $toolName');
    }
  }
  
  Future<Map<String, dynamic>> _readFile(String path) async {
    try {
      final file = File(path);
      final content = await file.readAsString();
      return {'content': content, 'success': true};
    } catch (e) {
      throw Exception('Failed to read file: $e');
    }
  }
  
  Future<Map<String, dynamic>> _writeFile(String path, String content) async {
    try {
      final file = File(path);
      await file.writeAsString(content);
      return {'success': true};
    } catch (e) {
      throw Exception('Failed to write file: $e');
    }
  }
  
  Future<Map<String, dynamic>> _listFiles(String path) async {
    try {
      final dir = Directory(path);
      final files = await dir.list().map((e) => e.path).toList();
      return {'files': files, 'success': true};
    } catch (e) {
      throw Exception('Failed to list files: $e');
    }
  }
  
  Future<Map<String, dynamic>> _executeCommand(String command) async {
    try {
      final result = await Process.run('sh', ['-c', command]);
      return {
        'stdout': result.stdout,
        'stderr': result.stderr,
        'exit_code': result.exitCode,
        'success': result.exitCode == 0,
      };
    } catch (e) {
      throw Exception('Failed to execute command: $e');
    }
  }
}
```

### 4. HITL Manager

```dart
class HITLManager {
  Future<void> requestApproval({
    required String callId,
    required String toolName,
    required Map<String, dynamic> arguments,
  }) async {
    // Показать диалог подтверждения
    final decision = await showDialog<HITLDecision>(
      context: context,
      builder: (context) => HITLApprovalDialog(
        toolName: toolName,
        arguments: arguments,
      ),
    );
    
    if (decision == null) {
      // Пользователь закрыл диалог - отклонить
      wsService.sendHITLDecision(
        callId,
        'reject',
        feedback: 'User cancelled',
      );
      return;
    }
    
    switch (decision.type) {
      case HITLDecisionType.approve:
        wsService.sendHITLDecision(callId, 'approve');
        break;
      case HITLDecisionType.edit:
        wsService.sendHITLDecision(
          callId,
          'edit',
          modifiedArguments: decision.modifiedArguments,
        );
        break;
      case HITLDecisionType.reject:
        wsService.sendHITLDecision(
          callId,
          'reject',
          feedback: decision.feedback,
        );
        break;
    }
  }
}
```

### 5. Использование в приложении

```dart
class ChatPage extends StatefulWidget {
  @override
  _ChatPageState createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  late WebSocketService wsService;
  late MessageHandler messageHandler;
  late ToolExecutor toolExecutor;
  late HITLManager hitlManager;
  
  final String sessionId = 'session_${DateTime.now().millisecondsSinceEpoch}';
  
  @override
  void initState() {
    super.initState();
    
    wsService = WebSocketService(baseUrl: 'ws://localhost:8000');
    toolExecutor = ToolExecutor();
    hitlManager = HITLManager(wsService: wsService);
    messageHandler = MessageHandler(
      wsService: wsService,
      toolExecutor: toolExecutor,
      hitlManager: hitlManager,
    );
    
    _connect();
  }
  
  Future<void> _connect() async {
    await wsService.connect(sessionId);
    messageHandler.startListening();
  }
  
  void _sendMessage(String content) {
    wsService.sendUserMessage(content);
  }
  
  @override
  void dispose() {
    wsService.dispose();
    super.dispose();
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('AI Chat')),
      body: Column(
        children: [
          Expanded(
            child: StreamBuilder<Map<String, dynamic>>(
              stream: wsService.messages,
              builder: (context, snapshot) {
                // Отображение сообщений
                return ListView();
              },
            ),
          ),
          TextField(
            onSubmitted: _sendMessage,
            decoration: InputDecoration(
              hintText: 'Type a message...',
            ),
          ),
        ],
      ),
    );
  }
}
```

---

## 🔐 Безопасность

### Gateway не требует аутентификации от IDE

Gateway **не проверяет** аутентификацию для WebSocket соединений от IDE. Это внутренний сервис.

### Agent Runtime защищен Internal Auth

Agent Runtime требует заголовок `X-Internal-Auth` для всех запросов. Gateway автоматически добавляет этот заголовок:

```python
# Gateway → Agent Runtime
headers = {
    "X-Internal-Auth": AppConfig.INTERNAL_API_KEY
}
```

---

## 📊 REST API через Gateway (проксирование)

**ВАЖНО:** IDE должен обращаться **ТОЛЬКО к Gateway** (порт 8000), который проксирует запросы к Agent Runtime.

### Gateway проксирует следующие endpoints:

#### 1. Получить историю сессии
```http
GET http://localhost:8000/api/sessions/{session_id}/history
```

**Ответ:**
```json
{
  "session_id": "session_123",
  "messages": [...],
  "message_count": 5,
  "last_activity": "2025-12-31T08:45:00.000Z",
  "current_agent": "coder",
  "agent_history": [...]
}
```

#### 2. Список всех сессий
```http
GET http://localhost:8000/api/sessions
```

**Ответ:**
```json
{
  "sessions": [
    {
      "session_id": "session_1",
      "message_count": 5,
      "last_activity": "2025-12-31T08:45:00.000Z",
      "current_agent": "coder"
    }
  ],
  "total": 1
}
```

#### 3. Список доступных агентов
```http
GET http://localhost:8000/api/agents
```

**Ответ:**
```json
[
  {
    "type": "coder",
    "name": "Coder Agent",
    "description": "Specialized in writing and modifying code",
    "allowed_tools": ["read_file", "write_file", "execute_command"],
    "has_file_restrictions": false
  }
]
```

#### 4. Текущий агент сессии
```http
GET http://localhost:8000/api/agents/{session_id}/current
```

**Ответ:**
```json
{
  "session_id": "session_123",
  "current_agent": "coder",
  "agent_history": [...],
  "switch_count": 1
}
```

### Реализация на Flutter (Dio + Retrofit + Freezed)

#### 1. Добавьте зависимости в `pubspec.yaml`

```yaml
dependencies:
  dio: ^5.4.0
  retrofit: ^4.0.0
  freezed_annotation: ^2.4.1
  json_annotation: ^4.8.1

dev_dependencies:
  retrofit_generator: ^8.0.0
  build_runner: ^2.4.0
  freezed: ^2.4.6
  json_serializable: ^6.7.1
```

#### 2. Создайте Freezed модели данных

**`lib/models/gateway_models.dart`:**
```dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'gateway_models.freezed.dart';
part 'gateway_models.g.dart';

/// Сообщение в чате
@freezed
class ChatMessage with _$ChatMessage {
  const factory ChatMessage({
    required String role,
    required String content,
    String? name,
  }) = _ChatMessage;

  factory ChatMessage.fromJson(Map<String, dynamic> json) =>
      _$ChatMessageFromJson(json);
}

/// Переключение агента
@freezed
class AgentSwitch with _$AgentSwitch {
  const factory AgentSwitch({
    required String from,
    required String to,
    required String reason,
    required String timestamp,
  }) = _AgentSwitch;

  factory AgentSwitch.fromJson(Map<String, dynamic> json) =>
      _$AgentSwitchFromJson(json);
}

/// История сессии
@freezed
class SessionHistory with _$SessionHistory {
  const factory SessionHistory({
    @JsonKey(name: 'session_id') required String sessionId,
    required List<ChatMessage> messages,
    @JsonKey(name: 'message_count') required int messageCount,
    @JsonKey(name: 'last_activity') String? lastActivity,
    @JsonKey(name: 'current_agent') String? currentAgent,
    @JsonKey(name: 'agent_history') List<AgentSwitch>? agentHistory,
  }) = _SessionHistory;

  factory SessionHistory.fromJson(Map<String, dynamic> json) =>
      _$SessionHistoryFromJson(json);
}

/// Информация о сессии
@freezed
class SessionInfo with _$SessionInfo {
  const factory SessionInfo({
    @JsonKey(name: 'session_id') required String sessionId,
    @JsonKey(name: 'message_count') required int messageCount,
    @JsonKey(name: 'last_activity') required String lastActivity,
    @JsonKey(name: 'current_agent') String? currentAgent,
  }) = _SessionInfo;

  factory SessionInfo.fromJson(Map<String, dynamic> json) =>
      _$SessionInfoFromJson(json);
}

/// Список сессий
@freezed
class SessionListResponse with _$SessionListResponse {
  const factory SessionListResponse({
    required List<SessionInfo> sessions,
    required int total,
  }) = _SessionListResponse;

  factory SessionListResponse.fromJson(Map<String, dynamic> json) =>
      _$SessionListResponseFromJson(json);
}

/// Информация об агенте
@freezed
class AgentInfo with _$AgentInfo {
  const factory AgentInfo({
    required String type,
    required String name,
    required String description,
    @JsonKey(name: 'allowed_tools') required List<String> allowedTools,
    @JsonKey(name: 'has_file_restrictions') required bool hasFileRestrictions,
  }) = _AgentInfo;

  factory AgentInfo.fromJson(Map<String, dynamic> json) =>
      _$AgentInfoFromJson(json);
}

/// Текущий агент сессии
@freezed
class CurrentAgentInfo with _$CurrentAgentInfo {
  const factory CurrentAgentInfo({
    @JsonKey(name: 'session_id') required String sessionId,
    @JsonKey(name: 'current_agent') required String currentAgent,
    @JsonKey(name: 'agent_history') required List<AgentSwitch> agentHistory,
    @JsonKey(name: 'switch_count') required int switchCount,
  }) = _CurrentAgentInfo;

  factory CurrentAgentInfo.fromJson(Map<String, dynamic> json) =>
      _$CurrentAgentInfoFromJson(json);
}
```

#### 3. Создайте Retrofit API клиент

**`lib/api/gateway_api.dart`:**
```dart
import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';
import '../models/gateway_models.dart';

part 'gateway_api.g.dart';

@RestApi(baseUrl: 'http://localhost:8000/api')
abstract class GatewayApi {
  factory GatewayApi(Dio dio, {String baseUrl}) = _GatewayApi;

  /// Получить историю сессии
  @GET('/sessions/{sessionId}/history')
  Future<SessionHistory> getSessionHistory(
    @Path('sessionId') String sessionId,
  );

  /// Получить список всех сессий
  @GET('/sessions')
  Future<SessionListResponse> listSessions();

  /// Получить список доступных агентов
  @GET('/agents')
  Future<List<AgentInfo>> listAgents();

  /// Получить текущего агента для сессии
  @GET('/agents/{sessionId}/current')
  Future<CurrentAgentInfo> getCurrentAgent(
    @Path('sessionId') String sessionId,
  );
}
```

#### 4. Сгенерируйте код

```bash
flutter pub run build_runner build --delete-conflicting-outputs
```

Это создаст файлы:
- `gateway_models.freezed.dart` - Freezed модели
- `gateway_models.g.dart` - JSON сериализация
- `gateway_api.g.dart` - Retrofit клиент

#### 5. Создайте сервис для работы с Gateway API

**`lib/services/gateway_service.dart`:**
```dart
import 'package:dio/dio.dart';
import '../api/gateway_api.dart';
import '../models/gateway_models.dart';

class GatewayService {
  final GatewayApi _api;
  
  GatewayService({
    required GatewayApi api,
  }) : _api = api;
  
  /// Получить историю сессии
  Future<SessionHistory> getSessionHistory(String sessionId) async {
    try {
      return await _api.getSessionHistory(sessionId);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) {
        throw Exception('Session not found: $sessionId');
      }
      throw Exception('Failed to get session history: ${e.message}');
    }
  }
  
  /// Получить список всех сессий
  Future<SessionListResponse> listSessions() async {
    try {
      return await _api.listSessions();
    } on DioException catch (e) {
      throw Exception('Failed to list sessions: ${e.message}');
    }
  }
  
  /// Получить список доступных агентов
  Future<List<AgentInfo>> listAgents() async {
    try {
      return await _api.listAgents();
    } on DioException catch (e) {
      throw Exception('Failed to list agents: ${e.message}');
    }
  }
  
  /// Получить текущего агента для сессии
  Future<CurrentAgentInfo> getCurrentAgent(String sessionId) async {
    try {
      return await _api.getCurrentAgent(sessionId);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) {
        throw Exception('Session not found: $sessionId');
      }
      throw Exception('Failed to get current agent: ${e.message}');
    }
  }
}
```

#### 6. Настройте Dependency Injection (GetIt)

**`lib/di/service_locator.dart`:**
```dart
import 'package:dio/dio.dart';
import 'package:get_it/get_it.dart';
import '../api/gateway_api.dart';
import '../services/gateway_service.dart';

final getIt = GetIt.instance;

Future<void> setupServiceLocator() async {
  // Dio с настройками
  final dio = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 30),
    receiveTimeout: const Duration(seconds: 30),
  ));
  
  // Добавить логирование (опционально)
  dio.interceptors.add(LogInterceptor(
    requestBody: true,
    responseBody: true,
    logPrint: (obj) => print(obj),
  ));
  
  getIt.registerSingleton<Dio>(dio);

  // Gateway API клиент
  getIt.registerSingleton<GatewayApi>(
    GatewayApi(dio, baseUrl: 'http://localhost:8000/api'),
  );

  // Gateway Service
  getIt.registerSingleton<GatewayService>(
    GatewayService(api: getIt<GatewayApi>()),
  );
}
```

#### 7. Используйте в приложении

**`lib/main.dart`:**
```dart
import 'package:flutter/material.dart';
import 'di/service_locator.dart';
import 'services/gateway_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Настроить DI
  await setupServiceLocator();
  
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CodeLab IDE',
      home: SessionHistoryPage(),
    );
  }
}
```

**`lib/pages/session_history_page.dart`:**
```dart
import 'package:flutter/material.dart';
import '../di/service_locator.dart';
import '../services/gateway_service.dart';
import '../models/gateway_models.dart';

class SessionHistoryPage extends StatefulWidget {
  @override
  _SessionHistoryPageState createState() => _SessionHistoryPageState();
}

class _SessionHistoryPageState extends State<SessionHistoryPage> {
  final GatewayService _gatewayService = getIt<GatewayService>();
  
  List<SessionInfo> _sessions = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadSessions();
  }

  Future<void> _loadSessions() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    
    try {
      final response = await _gatewayService.listSessions();
      setState(() {
        _sessions = response.sessions;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _viewSessionHistory(String sessionId) async {
    try {
      final history = await _gatewayService.getSessionHistory(sessionId);
      
      // Показать историю в диалоге
      showDialog(
        context: context,
        builder: (context) => AlertDialog(
          title: Text('Session History'),
          content: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Session ID: ${history.sessionId}'),
                Text('Messages: ${history.messageCount}'),
                Text('Current Agent: ${history.currentAgent ?? "N/A"}'),
                SizedBox(height: 16),
                Text('Messages:', style: TextStyle(fontWeight: FontWeight.bold)),
                ...history.messages.map((msg) => Padding(
                  padding: EdgeInsets.symmetric(vertical: 4),
                  child: Text('${msg.role}: ${msg.content}'),
                )),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text('Close'),
            ),
          ],
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        appBar: AppBar(title: Text('Sessions')),
        body: Center(child: CircularProgressIndicator()),
      );
    }

    if (_error != null) {
      return Scaffold(
        appBar: AppBar(title: Text('Sessions')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('Error: $_error'),
              SizedBox(height: 16),
              ElevatedButton(
                onPressed: _loadSessions,
                child: Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('Sessions (${_sessions.length})'),
        actions: [
          IconButton(
            icon: Icon(Icons.refresh),
            onPressed: _loadSessions,
          ),
        ],
      ),
      body: ListView.builder(
        itemCount: _sessions.length,
        itemBuilder: (context, index) {
          final session = _sessions[index];
          return ListTile(
            title: Text(session.sessionId),
            subtitle: Text(
              'Messages: ${session.messageCount}, '
              'Agent: ${session.currentAgent ?? "N/A"}',
            ),
            trailing: Text(session.lastActivity),
            onTap: () => _viewSessionHistory(session.sessionId),
          );
        },
      ),
    );
  }
}
```

**Примечание:** Gateway автоматически добавляет `X-Internal-Auth` заголовок при проксировании запросов к Agent Runtime. IDE **не нужно** добавлять этот заголовок!

### Преимущества Dio + Retrofit + Freezed:

1. ✅ **Freezed** - иммутабельные модели, автоматическая генерация `copyWith`, `==`, `hashCode`
2. ✅ **Retrofit** - декларативный HTTP клиент, автоматическая генерация кода
3. ✅ **Dio** - мощный HTTP клиент с interceptors, retry, logging
4. ✅ **Type Safety** - полная типизация на всех уровнях
5. ✅ **Меньше boilerplate** - автоматическая генерация кода
6. ✅ **Легкое тестирование** - моки через DI

---

## 🎯 Рекомендации

1. **Обработка переподключений** - реализуйте автоматическое переподключение при разрыве WebSocket
2. **Буферизация сообщений** - сохраняйте сообщения локально до подтверждения доставки
3. **Timeout handling** - устанавливайте таймауты для tool execution
4. **Error recovery** - обрабатывайте ошибки и показывайте пользователю
5. **Logging** - логируйте все WebSocket события для отладки
6. **UI feedback** - показывайте индикаторы загрузки и статус агента

---

## 📝 Заключение

Интеграция IDE с Agent Runtime через Gateway обеспечивает:
- ✅ Простой WebSocket протокол для IDE
- ✅ Автоматическое преобразование протоколов в Gateway
- ✅ Стриминг ответов в реальном времени
- ✅ HITL поддержку для опасных операций
- ✅ Мультиагентную систему без изменений в IDE
- ✅ Восстановление сессий через REST API

Gateway полностью скрывает сложность HTTP/SSE взаимодействия с Agent Runtime, предоставляя IDE простой WebSocket интерфейс.
