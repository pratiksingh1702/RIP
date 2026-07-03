import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:drift/drift.dart' show Value;
import 'package:uuid/uuid.dart';
import '../../data/local/app_database.dart';
import 'chat_provider.dart';

const uuid = Uuid();

final activeChatSessionIdProvider = StateProvider<String?>((ref) => null);

final chatSessionsProvider = FutureProvider<List<ChatSession>>((ref) async {
  final db = ref.watch(databaseProvider);
  return await db.getAllChatSessions();
});

class ChatSessionNotifier extends Notifier<void> {
  @override
  void build() {}

  Future<ChatSession> createNewChat({String? projectId, String? title}) async {
    final db = ref.read(databaseProvider);
    final sessionId = uuid.v4();
    final now = DateTime.now();
    
    final session = ChatSessionsCompanion(
      id: Value(sessionId),
      title: Value(title ?? 'New Chat'),
      projectId: projectId != null ? Value(projectId) : const Value.absent(),
      createdAt: Value(now),
      updatedAt: Value(now),
    );
    
    await db.insertChatSession(session);
    ref.read(activeChatSessionIdProvider.notifier).state = sessionId;
    ref.invalidate(chatSessionsProvider);
    
    // Clear messages for the new chat
    ref.read(chatProvider.notifier).clearMessages();
    
    return ChatSession(
      id: sessionId,
      title: title ?? 'New Chat',
      projectId: projectId,
      createdAt: now,
      updatedAt: now,
    );
  }

  Future<void> selectChatSession(String sessionId) async {
    final db = ref.read(databaseProvider);
    final session = await db.getChatSession(sessionId);
    
    if (session != null) {
      ref.read(activeChatSessionIdProvider.notifier).state = sessionId;
      // Load messages for this session
      await ref.read(chatProvider.notifier).loadSessionMessages(sessionId);
    }
  }

  Future<void> updateChatSessionTitle(String sessionId, String newTitle) async {
    final db = ref.read(databaseProvider);
    await db.updateChatSession(
      ChatSessionsCompanion(
        id: Value(sessionId),
        title: Value(newTitle),
        updatedAt: Value(DateTime.now()),
      ),
    );
    ref.invalidate(chatSessionsProvider);
  }

  Future<void> deleteChatSession(String sessionId) async {
    final db = ref.read(databaseProvider);
    await db.deleteChatSession(sessionId);
    
    // If deleting the active session, clear it
    final activeId = ref.read(activeChatSessionIdProvider);
    if (activeId == sessionId) {
      ref.read(activeChatSessionIdProvider.notifier).state = null;
      ref.read(chatProvider.notifier).clearMessages();
    }
    
    ref.invalidate(chatSessionsProvider);
  }
}

final chatSessionNotifierProvider = NotifierProvider<ChatSessionNotifier, void>(
  ChatSessionNotifier.new,
);
