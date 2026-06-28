import 'dart:io';
import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import '../../domain/enums/message_type.dart';

part 'app_database.g.dart';

class ChatMessages extends Table {
  TextColumn get id => text()();
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

@DriftDatabase(tables: [ChatMessages])
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  @override
  int get schemaVersion => 1;

  Future<List<ChatMessage>> getAllMessages() async {
    return await (select(chatMessages)..orderBy([(t) => OrderingTerm(expression: t.timestamp)])).get();
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
  }

  Future<void> deleteAllMessages() async {
    await delete(chatMessages).go();
  }
}

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final dbFolder = await getApplicationDocumentsDirectory();
    final file = File(path.join(dbFolder.path, 'rip_chat.db'));
    return NativeDatabase.createInBackground(file);
  });
}
