import 'dart:io';
import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import '../../domain/enums/message_type.dart';

part 'app_database.g.dart';

class ChatSessions extends Table {
  TextColumn get id => text()();
  TextColumn get title => text().withDefault(const Constant('New Chat'))();
  TextColumn get projectId => text().nullable()();
  DateTimeColumn get createdAt => dateTime()();
  DateTimeColumn get updatedAt => dateTime()();
}

class ChatMessages extends Table {
  TextColumn get id => text()();
  TextColumn get chatSessionId => text().nullable().references(ChatSessions, #id)();
  TextColumn get content => text()();
  BoolColumn get isUser => boolean()();
  IntColumn get messageType => integer().map(const MessageTypeConverter())();
  DateTimeColumn get timestamp => dateTime()();
  TextColumn get metadata => text().nullable()();
}

class MessageTypeConverter extends TypeConverter<MessageType, int> {
  const MessageTypeConverter();

  @override
  MessageType fromSql(int fromDb) {
    return MessageType.values[fromDb];
  }

  @override
  int toSql(MessageType value) {
    return value.index;
  }
}

@DriftDatabase(tables: [ChatSessions, ChatMessages])
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  @override
  int get schemaVersion => 3;

  @override
  MigrationStrategy get migration => MigrationStrategy(
        onCreate: (Migrator m) async {
          await m.createAll();
        },
        onUpgrade: (Migrator m, int from, int to) async {
          if (from < 2) {
            await m.createTable(chatSessions);
            await m.addColumn(chatMessages, chatMessages.chatSessionId);
            
            // Create a default chat session for existing messages
            final defaultSessionId = 'default-session';
            final now = DateTime.now();
            await into(chatSessions).insert(
              ChatSessionsCompanion(
                id: Value(defaultSessionId),
                title: const Value('General Chat'),
                createdAt: Value(now),
                updatedAt: Value(now),
              ),
            );
            
            // Update all existing messages to belong to the default session
            await (update(chatMessages)..where((t) => const Constant(true)))
                .write(ChatMessagesCompanion(chatSessionId: Value(defaultSessionId)));
          }
          if (from < 3) {
            // Already made chatSessionId nullable—no action needed
          }
        },
      );

  // Chat Session Operations
  Future<List<ChatSession>> getAllChatSessions() async {
    return await (select(chatSessions)
          ..orderBy([(t) => OrderingTerm(expression: t.updatedAt, mode: OrderingMode.desc)]))
        .get();
  }

  Future<ChatSession?> getChatSession(String id) async {
    return await (select(chatSessions)..where((t) => t.id.equals(id))).getSingleOrNull();
  }

  Future<void> insertChatSession(ChatSessionsCompanion session) async {
    await into(chatSessions).insert(session);
  }

  Future<void> updateChatSession(ChatSessionsCompanion session) async {
    await (update(chatSessions)..where((t) => t.id.equals(session.id.value)))
        .write(session);
  }

  Future<void> deleteChatSession(String id) async {
    await (delete(chatSessions)..where((t) => t.id.equals(id))).go();
    // Also delete associated messages
    await (delete(chatMessages)..where((t) => t.chatSessionId.equals(id))).go();
  }

  // Message Operations (updated to work with sessions)
  Future<List<ChatMessage>> getAllMessages() async {
    return await (select(chatMessages)..orderBy([(t) => OrderingTerm(expression: t.timestamp)])).get();
  }

  Future<List<ChatMessage>> getMessagesForSession(String sessionId) async {
    return await (select(chatMessages)
          ..where((t) => t.chatSessionId.equals(sessionId))
          ..orderBy([(t) => OrderingTerm(expression: t.timestamp)]))
        .get();
  }

  Future<Map<DateTime, List<ChatMessage>>> getMessagesGroupedByDate() async {
    final messages = await getAllMessages();
    final Map<DateTime, List<ChatMessage>> grouped = {};
    
    for (final msg in messages) {
      final date = DateTime(msg.timestamp.year, msg.timestamp.month, msg.timestamp.day);
      if (!grouped.containsKey(date)) {
        grouped[date] = [];
      }
      grouped[date]!.add(msg);
    }
    
    return grouped;
  }

  Future<void> insertMessage(ChatMessagesCompanion message) async {
    await into(chatMessages).insert(message);
    // Update the chat session's updatedAt timestamp
    if (message.chatSessionId.present) {
      await (update(chatSessions)
            ..where((t) => t.id.equals(message.chatSessionId.value!)))
          .write(ChatSessionsCompanion(updatedAt: Value(DateTime.now())));
    }
  }

  Future<void> deleteAllMessages() async {
    await delete(chatMessages).go();
  }
  
  Future<void> deleteMessagesForSession(String sessionId) async {
    await (delete(chatMessages)..where((t) => t.chatSessionId.equals(sessionId))).go();
  }
}

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final dbFolder = await getApplicationDocumentsDirectory();
    final file = File(path.join(dbFolder.path, 'rip_chat.db'));
    return NativeDatabase.createInBackground(file);
  });
}