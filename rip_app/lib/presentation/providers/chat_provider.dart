import 'dart:convert';
import 'dart:developer';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import 'package:drift/drift.dart' show Value;
import '../../data/models/message.dart';
import '../../data/models/rip_response.dart';
import '../../data/local/app_database.dart';
import '../../domain/enums/message_type.dart';
import '../../utils/command_parser.dart';
import '../../utils/response_parser.dart';
import '../../core/exceptions.dart';
import 'connection_provider.dart';
import 'project_provider.dart';

const uuid = Uuid();

final databaseProvider = Provider<AppDatabase>((ref) {
  return AppDatabase();
});

final isAssistantBusyProvider = StateProvider<bool>((ref) => false);

class ChatNotifier extends Notifier<List<Message>> {
  late AppDatabase _db;
  CancelToken? _activeCancelToken;
  String? _activePendingId;

  @override
  List<Message> build() {
    _db = ref.watch(databaseProvider);
    _loadMessages();
    return [];
  }

  Future<void> _loadMessages() async {
    final dbMessages = await _db.getAllMessages();
    state = dbMessages.map((dbMsg) {
      List<RipResponseBlock>? blocks;
      if (dbMsg.metadata != null && dbMsg.metadata!.isNotEmpty) {
        try {
          final List<dynamic> decoded = jsonDecode(dbMsg.metadata!);
          blocks = decoded
              .map((j) => RipResponseBlock.fromJson(j as Map<String, dynamic>))
              .toList();
        } catch (e) {
          log('Error decoding metadata blocks: $e');
        }
      }
      return Message(
        id: dbMsg.id,
        content: dbMsg.content,
        isUser: dbMsg.isUser,
        type: dbMsg.messageType,
        timestamp: dbMsg.timestamp,
        blocks: blocks,
      );
    }).toList();
  }

  Future<void> addMessage(Message message) async {
    state = [...state, message];
    await _db.insertMessage(ChatMessagesCompanion(
      id: Value(message.id),
      content: Value(message.content),
      isUser: Value(message.isUser),
      messageType: Value(message.type),
      timestamp: Value(message.timestamp),
      metadata: message.blocks != null
          ? Value(jsonEncode(message.blocks!.map((b) => b.toJson()).toList()))
          : const Value.absent(),
    ));
  }

  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty) return;
    if (ref.read(isAssistantBusyProvider)) {
      await addMessage(Message(
        id: uuid.v4(),
        content: 'Still working. Stop the current request before sending another.',
        isUser: false,
        type: MessageType.text,
        timestamp: DateTime.now(),
      ));
      return;
    }

    final trimmedText = text.trim();

    // 1. User Message
    final userMsg = Message(
      id: uuid.v4(),
      content: trimmedText,
      isUser: true,
      type: MessageType.text,
      timestamp: DateTime.now(),
    );

    state = [...state, userMsg];
    await _db.insertMessage(ChatMessagesCompanion(
      id: Value(userMsg.id),
      content: Value(userMsg.content),
      isUser: Value(userMsg.isUser),
      messageType: Value(userMsg.type),
      timestamp: Value(userMsg.timestamp),
    ));

    final localReply = _localReplyForUnsupportedMessage(trimmedText);
    if (localReply != null) {
      final ripMsg = Message(
        id: uuid.v4(),
        content: localReply,
        isUser: false,
        type: MessageType.text,
        timestamp: DateTime.now(),
      );
      state = [...state, ripMsg];
      await _db.insertMessage(ChatMessagesCompanion(
        id: Value(ripMsg.id),
        content: Value(ripMsg.content),
        isUser: Value(ripMsg.isUser),
        messageType: Value(ripMsg.type),
        timestamp: Value(ripMsg.timestamp),
      ));
      return;
    }

    // 2. Add temporary loading/typing indicator message
    final pendingId = uuid.v4();
    final pendingMsg = Message(
      id: pendingId,
      content: 'Working on it...',
      isUser: false,
      type: MessageType.text,
      timestamp: DateTime.now(),
      isLoading: true,
    );
    state = [...state, pendingMsg];
    final cancelToken = CancelToken();
    _activeCancelToken = cancelToken;
    _activePendingId = pendingId;
    ref.read(isAssistantBusyProvider.notifier).state = true;

    try {
      // 3. Parse command & execute
      final parsedCmd = CommandParser.parse(trimmedText);
      final rawResponse = await _executeCommand(
        parsedCmd,
        trimmedText,
        cancelToken: cancelToken,
      );

      // 4. Parse response into blocks
      final blocks = ResponseParser.parse(
        rawResponse,
        commandSymbol: parsedCmd.arguments.isNotEmpty ? parsedCmd.arguments.first : null,
      );

      // 5. Build final RIP message
      final ripMsg = Message(
        id: pendingId,
        content: rawResponse,
        isUser: false,
        type: MessageType.text,
        timestamp: DateTime.now(),
        blocks: blocks,
        isLoading: false,
      );

      // 6. Update state (replace pendingMsg with ripMsg)
      state = state.map((m) => m.id == pendingId ? ripMsg : m).toList();

      // 7. Save to DB
      await _db.insertMessage(ChatMessagesCompanion(
        id: Value(ripMsg.id),
        content: Value(ripMsg.content),
        isUser: Value(ripMsg.isUser),
        messageType: Value(ripMsg.type),
        timestamp: Value(ripMsg.timestamp),
        metadata: Value(jsonEncode(blocks.map((b) => b.toJson()).toList())),
      ));
    } catch (e, stackTrace) {
      log('Error sending message: $e', error: e, stackTrace: stackTrace);
      final pendingStillLoading =
          state.any((m) => m.id == pendingId && m.isLoading);
      if (e is DioException &&
          e.type == DioExceptionType.cancel &&
          !pendingStillLoading) {
        return;
      }
      String displayError = e.toString();
      var messageType = MessageType.error;
      if (e is DioException && e.type == DioExceptionType.cancel) {
        displayError = 'Stopped.';
        messageType = MessageType.text;
      }
      if (e is RIPAuthException) {
        displayError = e.message;
      }

      final errorMsg = Message(
        id: pendingId,
        content: displayError,
        isUser: false,
        type: messageType,
        timestamp: DateTime.now(),
        isLoading: false,
      );
      state = state.map((m) => m.id == pendingId ? errorMsg : m).toList();
      await _db.insertMessage(ChatMessagesCompanion(
        id: Value(errorMsg.id),
        content: Value(errorMsg.content),
        isUser: Value(errorMsg.isUser),
        messageType: Value(errorMsg.type),
        timestamp: Value(errorMsg.timestamp),
      ));
    } finally {
      if (_activePendingId == pendingId) {
        _activeCancelToken = null;
        _activePendingId = null;
        ref.read(isAssistantBusyProvider.notifier).state = false;
      }
    }
  }

  Future<void> resendMessage(String text) async {
    await sendMessage(text);
  }

  Future<void> regenerateFromAssistant(String assistantMessageId) async {
    final index = state.indexWhere((message) => message.id == assistantMessageId);
    if (index <= 0) return;

    for (var i = index - 1; i >= 0; i--) {
      final candidate = state[i];
      if (candidate.isUser && candidate.content.trim().isNotEmpty) {
        await sendMessage(candidate.content);
        return;
      }
    }
  }

  Future<void> cancelCurrentRequest() async {
    final pendingId = _activePendingId;
    _activeCancelToken?.cancel('User stopped the request.');
    ref.read(isAssistantBusyProvider.notifier).state = false;
    _activeCancelToken = null;
    _activePendingId = null;

    if (pendingId == null) return;
    final stoppedMsg = Message(
      id: pendingId,
      content: 'Stopped.',
      isUser: false,
      type: MessageType.text,
      timestamp: DateTime.now(),
      isLoading: false,
    );
    state = state.map((m) => m.id == pendingId ? stoppedMsg : m).toList();
    await _db.insertMessage(ChatMessagesCompanion(
      id: Value(stoppedMsg.id),
      content: Value(stoppedMsg.content),
      isUser: Value(stoppedMsg.isUser),
      messageType: Value(stoppedMsg.type),
      timestamp: Value(stoppedMsg.timestamp),
    ));
  }

  Future<String> _executeCommand(
    ParsedCommand cmd,
    String rawText, {
    required CancelToken cancelToken,
  }) async {
    final client = ref.read(ripClientProvider);
    final projectId = ref.read(activeProjectIdProvider);

    if (projectId == null &&
        cmd.type != CommandType.indexRepository &&
        cmd.type != CommandType.projects) {
      throw Exception('No active project selected. Select a project first using @ or drawer.');
    }

    switch (cmd.type) {
      case CommandType.search:
        final query = cmd.arguments.isNotEmpty ? cmd.arguments.join(' ') : 'search';
        final results = await client.search(
          projectId: projectId!,
          query: query,
          limit: _intFlag(cmd, 'limit', fallback: 10),
          cancelToken: cancelToken,
        );
        if (results.isEmpty) return 'No search results found.';
        return results
            .map((r) => '- [${r.name}](file:///${r.filePath}) (score: ${r.score.toStringAsFixed(2)})')
            .join('\n\n');

      case CommandType.explain:
        final topic = cmd.arguments.isNotEmpty ? cmd.arguments.join(' ') : 'explanation';
        final result = await client.explain(
          projectId: projectId!,
          topic: topic,
          contextLevel: cmd.flagValue('level') ?? 'file',
          provider: cmd.flagValue('provider'),
          model: cmd.flagValue('model'),
          diagram: cmd.hasFlag('diagram'),
          tree: cmd.hasFlag('tree'),
          dependencies: cmd.hasFlag('dependencies'),
          code: cmd.hasFlag('code'),
          noLlm: cmd.hasFlag('no-llm'),
          maxHops: _intFlag(cmd, 'max-hops', fallback: 8),
          cancelToken: cancelToken,
        );
        return result['explanation'] as String? ?? 'No explanation returned.';

      case CommandType.trace:
        final symbol = cmd.arguments.isNotEmpty ? cmd.arguments.first : 'main';
        final result = await client.trace(
          projectId: projectId!,
          symbol: symbol,
          cancelToken: cancelToken,
        );
        final chain = result['workflow_chain'] as List? ?? [];
        final files = result['important_files'] as List? ?? [];
        final buffer = StringBuffer();
        buffer.writeln('Traced symbol: $symbol\n');
        if (chain.isNotEmpty) {
          buffer.writeln(chain.map((c) => c['name'] ?? '').join(' -> '));
        }
        if (files.isNotEmpty) {
          buffer.writeln('\nImportant files:');
          for (final f in files) {
            buffer.writeln('- $f');
          }
        }
        return buffer.toString();

      case CommandType.impact:
        final symbol = cmd.arguments.isNotEmpty ? cmd.arguments.first : 'main';
        final result = await client.impact(
          projectId: projectId!,
          symbol: symbol,
          cancelToken: cancelToken,
        );
        final severity = result['severity'] ?? 'medium';
        final affected = result['affected_entities'] as List? ?? [];
        final buffer = StringBuffer();
        buffer.writeln('Impact Analysis for $symbol:\n');
        buffer.writeln('risk: $severity\n');
        if (affected.isNotEmpty) {
          buffer.writeln('Affected Entities:');
          for (final a in affected) {
            buffer.writeln('- ${a['name']} (${a['type']})');
          }
        }
        return buffer.toString();

      case CommandType.architecture:
        final result = await client.architecture(
          projectId: projectId!,
          cancelToken: cancelToken,
        );
        final summary = result['overview'] ?? 'Architecture overview';
        final mermaid = result['diagram'] ?? '';
        final buffer = StringBuffer();
        buffer.writeln(summary);
        if (mermaid.isNotEmpty) {
          buffer.writeln('\n```mermaid\n$mermaid\n```');
        }
        return buffer.toString();

      case CommandType.metrics:
        final result = await client.metrics(
          projectId: projectId!,
          cancelToken: cancelToken,
        );
        final modules = result['modules'] as List? ?? [];
        if (modules.isEmpty) return 'No metrics available for this project.';
        final buffer = StringBuffer();
        buffer.writeln('| Module | Risk Score | Coupling | Incoming |');
        buffer.writeln('|--------|------------|----------|----------|');
        for (final m in modules.take(20)) {
          if (m is Map<String, dynamic>) {
            final module = m['module'] ?? m['file_path'] ?? '-';
            final risk = (m['risk_score'] as num?)?.toStringAsFixed(2) ?? '-';
            final coupling = m['efferent_coupling'] ?? m['coupling'] ?? '-';
            final incoming = m['incoming_calls'] ?? '-';
            buffer.writeln('| $module | $risk | $coupling | $incoming |');
          }
        }
        return buffer.toString();

      case CommandType.onboard:
        final result = await client.onboard(
          projectId: projectId!,
          cancelToken: cancelToken,
        );
        return result['guide'] as String? ?? 'Onboarding guide not found.';

      case CommandType.deadCode:
        final result = await client.deadCode(
          projectId: projectId!,
          cancelToken: cancelToken,
        );
        // Backend returns {unused: [...], total_count: N}
        final dead = result['unused'] as List? ?? result['dead_entities'] as List? ?? [];
        if (dead.isEmpty) return 'No dead code detected.';
        final buffer = StringBuffer();
        buffer.writeln('| File | Dead Entity | Type |');
        buffer.writeln('|------|-------------|------|');
        for (final d in dead) {
          if (d is Map<String, dynamic>) {
            buffer.writeln('| ${d['file_path'] ?? ''} | ${d['name'] ?? ''} | ${d['type'] ?? ''} |');
          } else {
            buffer.writeln('| - | $d | - |');
          }
        }
        return buffer.toString();

      case CommandType.dependencies:
        final file = cmd.arguments.isNotEmpty ? cmd.arguments.first : '';
        final result = await client.explain(
          projectId: projectId!,
          topic: 'dependencies of $file',
          dependencies: true,
          cancelToken: cancelToken,
        );
        return result['explanation'] as String? ?? 'No dependency details found.';

      case CommandType.indexRepository:
        final gitUrl = cmd.arguments.isNotEmpty ? cmd.arguments.first : '';
        final name = gitUrl.split('/').last.replaceAll('.git', '');
        final job = await client.startGitIndex(
          gitUrl: gitUrl,
          projectName: name,
          cancelToken: cancelToken,
        );
        return 'Indexing job started. Job ID: ${job.jobId}';

      case CommandType.projects:
        final projects = await client.listProjects(cancelToken: cancelToken);
        if (projects.isEmpty) return 'No projects indexed yet.';
        final buffer = StringBuffer();
        buffer.writeln('| Project Name | Files | Entities | Git URL |');
        buffer.writeln('|--------------|-------|----------|---------|');
        for (final p in projects) {
          buffer.writeln('| ${p.projectName} | ${p.filesCount} | ${p.entitiesCount} | ${p.gitUrl ?? "Local"} |');
        }
        return buffer.toString();

      case CommandType.unknown:
        final result = await client.explain(
          projectId: projectId!,
          topic: rawText,
          cancelToken: cancelToken,
        );
        return result['explanation'] as String? ?? 'No response from server.';
    }
  }

  int _intFlag(ParsedCommand cmd, String name, {required int fallback}) {
    final value = cmd.flagValue(name);
    if (value == null || value == 'true') return fallback;
    return int.tryParse(value) ?? fallback;
  }

  String? _localReplyForUnsupportedMessage(String text) {
    final normalized = text.trim().toLowerCase();
    if (normalized.isEmpty) return null;

    final parsedCommand = CommandParser.parse(text);
    if (text.trimLeft().startsWith('/')) {
      if (parsedCommand.type == CommandType.unknown) {
        return 'Unknown command. Use /search, /explain, /trace, /impact, /architecture, /metrics, /onboard, /dependencies, /projects, or /dead-code.';
      }
      return null;
    }

    if (_looksLikeGarbage(normalized)) {
      return 'I need a real codebase question. Ask about a file, symbol, flow, dependency, architecture, impact, or bug.';
    }

    if (_looksOffTopic(normalized) && !_looksCodeRelated(text)) {
      return 'I only help with this repository. Ask about code, files, architecture, dependencies, impact, search, or debugging.';
    }

    return null;
  }

  bool _looksLikeGarbage(String text) {
    final compact = text.replaceAll(RegExp(r'\s+'), '');
    if (compact.length <= 2) return true;
    if (RegExp(r'^(.)\1{4,}$').hasMatch(compact)) return true;

    final letters = RegExp(r'[a-z0-9]').allMatches(compact).length;
    if (letters == 0) return true;
    final symbolRatio = (compact.length - letters) / compact.length;
    if (compact.length >= 5 && symbolRatio > 0.65) return true;

    final vowels = RegExp(r'[aeiou]').allMatches(compact).length;
    if (compact.length >= 12 && vowels == 0 && !compact.contains('_')) {
      return true;
    }

    return false;
  }

  bool _looksOffTopic(String text) {
    const offTopicTerms = [
      'weather',
      'recipe',
      'cook',
      'cooking',
      'movie',
      'song',
      'lyrics',
      'poem',
      'story',
      'joke',
      'dating',
      'relationship',
      'homework',
      'essay',
      'translate',
      'sports',
      'cricket',
      'football',
      'stock price',
      'bitcoin',
      'horoscope',
      'medical',
      'doctor',
      'legal advice',
      'lawyer',
    ];

    return offTopicTerms.any(text.contains);
  }

  bool _looksCodeRelated(String text) {
    final normalized = text.toLowerCase();
    const codeTerms = [
      'repo',
      'repository',
      'code',
      'file',
      'folder',
      'class',
      'function',
      'method',
      'symbol',
      'module',
      'package',
      'import',
      'dependency',
      'dependencies',
      'architecture',
      'trace',
      'impact',
      'search',
      'explain',
      'debug',
      'bug',
      'error',
      'exception',
      'api',
      'endpoint',
      'database',
      'query',
      'model',
      'provider',
      'widget',
      'screen',
      'service',
      'controller',
      'route',
      'login',
      'auth',
      'state',
      'build',
      'test',
      'config',
      'index',
      'graph',
      'flow',
      'depends',
      'call',
      'calls',
      'used',
      'unused',
    ];

    if (codeTerms.any(normalized.contains)) return true;
    if (RegExp(r'\b[\w\-\/\\]+\.(dart|py|ts|tsx|js|jsx|java|go|rs|json|yaml|yml|md)\b')
        .hasMatch(normalized)) {
      return true;
    }
    if (RegExp(r'\b[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*\b').hasMatch(text)) {
      return true;
    }
    if (RegExp(r'\b[a-z][a-z0-9]*_[a-z0-9_]+\b').hasMatch(normalized)) {
      return true;
    }

    return false;
  }

  Future<void> clearChat() async {
    state = [];
    await _db.deleteAllMessages();
  }
}

final chatProvider = NotifierProvider<ChatNotifier, List<Message>>(ChatNotifier.new);
