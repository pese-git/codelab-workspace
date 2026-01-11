# ⚠️ УСТАРЕВШАЯ ДОКУМЕНТАЦИЯ POC

**Дата создания**: 2024-2025  
**Статус**: УСТАРЕЛО  
**Актуальная документация**: [website/docs/](../../website/docs/)

---

## Важное уведомление

Документы в этой директории относятся к **Proof of Concept (POC)** фазе проекта и **больше не актуальны**. Они сохранены для исторических целей и понимания эволюции проекта.

## ❌ Устаревшие документы

| Документ | Статус | Актуальная замена |
|----------|--------|-------------------|
| `tech-req-agent-runtime-service.md` | ⚠️ Устарело | [`website/docs/api/agent-runtime.md`](../../website/docs/api/agent-runtime.md) |
| `tech-req-gateway.md` | ⚠️ Устарело | [`website/docs/api/gateway.md`](../../website/docs/api/gateway.md) |
| `tech-req-llm-proxy-service.md` | ⚠️ Устарело | [`website/docs/api/llm-proxy.md`](../../website/docs/api/llm-proxy.md) |
| `streaming-protocol-spec.md` | ⚠️ Устарело | [`website/docs/api/websocket-protocol.md`](../../website/docs/api/websocket-protocol.md) |
| `tools-specification.md` | ⚠️ Устарело | [`website/docs/api/tools-specification.md`](../../website/docs/api/tools-specification.md) |
| `ai-agent-iterative-development-plan.md` | ⚠️ Устарело | [`codelab-ai-service/doc/ai-agent-iterative-development-plan.md`](../../codelab-ai-service/doc/ai-agent-iterative-development-plan.md) |
| `ai-agent-poc-arch.md` | ⚠️ Устарело | [`website/docs/architecture/overview.md`](../../website/docs/architecture/overview.md) |
| `ide-poc.arch.md` | ⚠️ Устарело | [`website/docs/architecture/ide-architecture.md`](../../website/docs/architecture/ide-architecture.md) |
| `system-specifications.md` | ⚠️ Устарело | [`website/docs/getting-started/system-requirements.md`](../../website/docs/getting-started/system-requirements.md) |

## ✅ Актуальная документация

Пожалуйста, используйте следующие источники для актуальной информации:

### Основная документация (Docusaurus)
- **Начало работы**: [`website/docs/getting-started/`](../../website/docs/getting-started/)
  - [Установка](../../website/docs/getting-started/installation.md)
  - [Быстрый старт](../../website/docs/getting-started/quick-start.md)
  - [Системные требования](../../website/docs/getting-started/system-requirements.md)

- **Архитектура**: [`website/docs/architecture/`](../../website/docs/architecture/)
  - [Обзор архитектуры](../../website/docs/architecture/overview.md)
  - [Архитектура AI Service](../../website/docs/architecture/ai-service-architecture.md)
  - [Архитектура IDE](../../website/docs/architecture/ide-architecture.md)
  - [Интеграция компонентов](../../website/docs/architecture/integration.md)

- **API документация**: [`website/docs/api/`](../../website/docs/api/)
  - [WebSocket Protocol](../../website/docs/api/websocket-protocol.md)
  - [Agent Protocol](../../website/docs/api/agent-protocol.md)
  - [Agent Runtime API](../../website/docs/api/agent-runtime.md)
  - [Gateway API](../../website/docs/api/gateway.md)
  - [LLM Proxy API](../../website/docs/api/llm-proxy.md)
  - [Auth Service API](../../website/docs/api/auth-service.md)
  - [Мультиагентная система](../../website/docs/api/multi-agent-system.md)
  - [Tools Specification](../../website/docs/api/tools-specification.md)

- **Разработка**: [`website/docs/development/`](../../website/docs/development/)
  - [Разработка IDE](../../website/docs/development/ide.md)
  - [Разработка AI Service](../../website/docs/development/ai-service.md)
  - [Тестирование](../../website/docs/development/testing.md)
  - [Contributing](../../website/docs/development/contributing.md)

### Техническая документация AI Service
- **Мультиагентная система**: [`codelab-ai-service/doc/`](../../codelab-ai-service/doc/)
  - [Multi-Agent README](../../codelab-ai-service/doc/MULTI_AGENT_README.md)
  - [Multi-Agent Architecture Plan](../../codelab-ai-service/doc/multi-agent-architecture-plan.md)
  - [Multi-Agent Quick Start](../../codelab-ai-service/doc/multi-agent-quick-start.md)

- **HITL система**: 
  - [HITL Implementation](../../codelab-ai-service/doc/HITL_IMPLEMENTATION.md)
  - [HITL Implementation Summary](../../codelab-ai-service/doc/HITL_IMPLEMENTATION_SUMMARY.md)

- **Миграции и изменения**:
  - [Migration Complete](../../codelab-ai-service/agent-runtime/MIGRATION_COMPLETE.md)
  - [Database Migration Guide](../../codelab-ai-service/agent-runtime/DATABASE_MIGRATION_GUIDE.md)
  - [Session Persistence Guide](../../codelab-ai-service/agent-runtime/SESSION_PERSISTENCE_GUIDE.md)

### Аналитические отчеты
- [Documentation Audit Report](../../DOCUMENTATION_AUDIT_REPORT.md) - Аудит документации
- [Project Roadmap 2026](../../PROJECT_ROADMAP_2026.md) - План развития на 2026 год

## 📚 Исторический контекст

Эти POC документы были созданы на ранних этапах проекта (2024-2025) для:
- Определения требований к MVP
- Проектирования архитектуры
- Планирования разработки
- Создания технических спецификаций

С тех пор проект значительно эволюционировал:
- ✅ Реализована мультиагентная система (5 агентов)
- ✅ Добавлен Auth Service с OAuth2
- ✅ Внедрена async database с PostgreSQL
- ✅ Реализован HITL с persistence
- ✅ Создана полная документация в Docusaurus

## 🔄 Миграция информации

Вся актуальная информация из POC документов была перенесена в:
1. **Docusaurus документацию** (`website/docs/`) - для пользователей и разработчиков
2. **Техническую документацию** (`codelab-ai-service/doc/`) - для внутренней команды
3. **README файлы** - для быстрого старта

## ⚠️ Не используйте эти документы

Если вы нашли ссылку на документ из этой директории:
1. Проверьте таблицу выше для актуальной замены
2. Используйте актуальную документацию
3. Сообщите о найденной ссылке для обновления

## 📞 Контакты

Если у вас есть вопросы по документации:
- Создайте Issue в GitHub
- Обратитесь к команде разработки
- Проверьте [Contributing Guide](../../website/docs/development/contributing.md)

---

**Последнее обновление**: 11 января 2026  
**Автор**: CodeLab Team
