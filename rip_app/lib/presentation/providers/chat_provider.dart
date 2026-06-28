import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import 'package:drift/drift.dart' show Value;
import '../../data/models/message.dart';
import '../../data/local/app_database.dart';

const uuid = Uuid();

final databaseProvider = Provider<AppDatabase>((ref) {
  return AppDatabase();
});

class ChatNotifier extends Notifier<List<Message>> {
  late AppDatabase _db;

  @override
  List<Message> build() {
    _db = ref.watch(databaseProvider);
    _loadMessages();
    return [];
  }

  Future<void> _loadMessages() async {
    final dbMessages = await _db.getAllMessages();
    state = dbMessages.map((dbMsg) => Message(
      id: dbMsg.id,
      content: dbMsg.content,
      isUser: dbMsg.isUser,
      type: dbMsg.messageType,
      timestamp: dbMsg.timestamp,
    )).toList();
  }

  Future<void> addMessage(Message message) async {
    state = [...state, message];
    await _db.insertMessage(ChatMessagesCompanion(
      id: Value(message.id),
      content: Value(message.content),
      isUser: Value(message.isUser),
      messageType: Value(message.type),
      timestamp: Value(message.timestamp),
    ));
  }

  Future<void> addUserMessage(String content) async {
    final message = Message(
      id: uuid.v4(),
      content: content,
      isUser: true,
      timestamp: DateTime.now(),
    );
    await addMessage(message);
  }

  Future<void> addRipMessage(String content) async {
    final message = Message(
      id: uuid.v4(),
      content: content,
      isUser: false,
      timestamp: DateTime.now(),
    );
    await addMessage(message);
  }

  Future<void> clearChat() async {
    state = [];
    await _db.deleteAllMessages();
  }
}

final chatProvider = NotifierProvider<ChatNotifier, List<Message>>(ChatNotifier.new);
