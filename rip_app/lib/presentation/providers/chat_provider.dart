import 'dart:convert';
import 'dart:developer';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import 'package:drift/drift.dart' show Value;
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../data/models/message.dart';
import '../../data/models/pipeline_trace.dart';
import '../../data/models/rip_response.dart';
import '../../data/local/app_database.dart';
import '../../domain/enums/message_type.dart';
import '../../utils/command_parser.dart';
import '../../utils/response_parser.dart';
import '../../core/exceptions.dart';
import 'connection_provider.dart';
import 'gateway_provider.dart';
import 'project_provider.dart';
import 'chat_session_provider.dart';

const uuid = Uuid();

final databaseProvider = Provider<AppDatabase>((ref) {
  return AppDatabase();
});

final isAssistantBusyProvider = StateProvider<bool>((ref) => false);

class ChatNotifier extends Notifier<List<Message>> {
  late AppDatabase _db;
  CancelToken? _activeCancelToken;
  String? _activePendingId;
  String? _lastGatewaySessionId;
  String? _currentSessionId;

  @override
  List<Message> build() {
    _db = ref.watch(databaseProvider);
    _loadDefaultMessages();
    return [];
  }

  Future<void> _loadDefaultMessages() async {
    // Try to load default session or first available session
    final sessions = await _db.getAllChatSessions();
    if (sessions.isNotEmpty) {
      final defaultSession = sessions.firstWhere(
        (s) => s.id == 'default-session',
        orElse: () => sessions.first,
      );
      await loadSessionMessages(defaultSession.id);
      ref.read(activeChatSessionIdProvider.notifier).state = defaultSession.id;
    } else {
      // No sessions yet, just initialize with empty state
      state = [];
    }
  }

  Future<void> loadSessionMessages(String sessionId) async {
    _currentSessionId = sessionId;
    final dbMessages = await _db.getMessagesForSession(sessionId);
    state = dbMessages.map((dbMsg) {
      List<RipResponseBlock>? blocks;
      PipelineTrace? trace;
      if (dbMsg.metadata != null && dbMsg.metadata!.isNotEmpty) {
        try {
          final decoded = jsonDecode(dbMsg.metadata!);
          if (decoded is List) {
            blocks = decoded
                .map((j) => RipResponseBlock.fromJson(j as Map<String, dynamic>))
                .toList();
          } else if (decoded is Map<String, dynamic>) {
            final blockData = decoded['blocks'] as List? ?? const [];
            blocks = blockData
                .map((j) => RipResponseBlock.fromJson(j as Map<String, dynamic>))
                .toList();
            final traceData = decoded['trace'];
            if (traceData is Map<String, dynamic>) {
              trace = PipelineTrace.fromJson(traceData);
            }
          }
        } catch (e) {
          log('Error decoding metadata: $e');
        }
      }
      return Message(
        id: dbMsg.id,
        content: dbMsg.content,
        isUser: dbMsg.isUser,
        type: dbMsg.messageType,
        timestamp: dbMsg.timestamp,
        blocks: blocks,
        trace: trace,
      );
    }).toList();
  }

  Future<void> addMessage(Message message) async {
    if (_currentSessionId == null) {
      // No active session, create one first
      final activeProjectId = ref.read(activeProjectIdProvider);
      await ref.read(chatSessionNotifierProvider.notifier).createNewChat(
            projectId: activeProjectId,
          );
      _currentSessionId = ref.read(activeChatSessionIdProvider);
    }

    state = [...state, message];
    await _db.insertMessage(ChatMessagesCompanion(
      id: Value(message.id),
      chatSessionId: Value(_currentSessionId!),
      content: Value(message.content),
      isUser: Value(message.isUser),
      messageType: Value(message.type),
      timestamp: Value(message.timestamp),
      metadata: message.blocks != null || message.trace != null
          ? Value(_encodeMetadata(message.blocks, message.trace))
          : const Value.absent(),
    ));
  }

  Future<void> sendMessage(String text) async {
    if (_currentSessionId == null) {
      // No active session, create one first
      final activeProjectId = ref.read(activeProjectIdProvider);
      await ref.read(chatSessionNotifierProvider.notifier).createNewChat(
            projectId: activeProjectId,
          );
      _currentSessionId = ref.read(activeChatSessionIdProvider);
    }

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
      chatSessionId: Value(_currentSessionId!),
      content: Value(userMsg.content),
      isUser: Value(userMsg.isUser),
      messageType: Value(userMsg.type),
      timestamp: Value(userMsg.timestamp),
    ));

    // 2. Add temporary loading/typing indicator message
    final pendingId = uuid.v4();
    final pendingMsg = Message(
      id: pendingId,
      content: 'Working on it...',
      isUser: false,
      type: MessageType.text,
      timestamp: DateTime.now(),
      trace: PipelineTrace.empty(pendingId),
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
      final useGatewayPipeline = parsedCmd.type == CommandType.unknown;
      _lastGatewaySessionId = null;
      final traceCollector = useGatewayPipeline
          ? _collectPipelineTrace(pendingId, cancelToken)
          : Future.value(PipelineTrace.empty(pendingId));
      final rawResponse = await _executeCommand(
        parsedCmd,
        trimmedText,
        gatewaySessionId: useGatewayPipeline ? pendingId : null,
        cancelToken: cancelToken,
      );
      final trace = await traceCollector.timeout(
        const Duration(seconds: 2),
        onTimeout: () {
          for (final message in state) {
            if (message.id == pendingId && message.trace != null) {
              return message.trace!;
            }
          }
          return PipelineTrace.empty(pendingId);
        },
      );
      final persistedTrace = useGatewayPipeline && _lastGatewaySessionId != null
          ? trace.withSessionId(_lastGatewaySessionId!)
          : trace;

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
        trace: persistedTrace.hasEvents ? persistedTrace : null,
        isLoading: false,
      );

      // 6. Update state (replace pendingMsg with ripMsg)
      state = state.map((m) => m.id == pendingId ? ripMsg : m).toList();

      // 7. Save to DB
      await _db.insertMessage(ChatMessagesCompanion(
        id: Value(ripMsg.id),
        chatSessionId: Value(_currentSessionId!),
        content: Value(ripMsg.content),
        isUser: Value(ripMsg.isUser),
        messageType: Value(ripMsg.type),
        timestamp: Value(ripMsg.timestamp),
        metadata: Value(_encodeMetadata(blocks, ripMsg.trace)),
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
        chatSessionId: Value(_currentSessionId!),
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
      chatSessionId: Value(_currentSessionId!),
      content: Value(stoppedMsg.content),
      isUser: Value(stoppedMsg.isUser),
      messageType: Value(stoppedMsg.type),
      timestamp: Value(stoppedMsg.timestamp),
    ));
  }

  Future<void> clearMessages() async {
    state = [];
  }

  Future<void> clearChat() async {
    if (_currentSessionId != null) {
      await _db.deleteMessagesForSession(_currentSessionId!);
    }
    state = [];
  }

  Future<String> _executeCommand(
    ParsedCommand cmd,
    String rawText, {
    String? gatewaySessionId,
    required CancelToken cancelToken,
  }) async {
    final client = ref.read(ripClientProvider);
    final projectId = ref.read(activeProjectIdProvider);

    if (projectId == null &&
        cmd.type != CommandType.indexRepository &&
        cmd.type != CommandType.projects &&
        cmd.type != CommandType.workflow &&
        cmd.type != CommandType.unknown) {
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
        if (gitUrl.isEmpty) {
          return 'Use `/index <git_url> --folder <clone-folder-name>` to index a repository.';
        }
        final folderName = cmd.flagValue('folder') ?? cmd.flagValue('folder-name');
        if (folderName == null || folderName.trim().isEmpty) {
          return 'Choose a clone folder first: `/index $gitUrl --folder <clone-folder-name>`.';
        }
        final name = cmd.flagValue('project-name') ?? gitUrl.split('/').last.replaceAll('.git', '');
        final branch = cmd.flagValue('branch') ?? 'main';
        final subdirectory = cmd.flagValue('subdir') ?? cmd.flagValue('subdirectory');
        final job = await client.startGitIndex(
          gitUrl: gitUrl,
          projectName: name,
          folderName: folderName.trim(),
          subdirectory: subdirectory?.trim(),
          branch: branch,
          cancelToken: cancelToken,
        );
        final target = subdirectory == null || subdirectory.trim().isEmpty
            ? (job.folderName ?? folderName)
            : '${job.folderName ?? folderName}/${subdirectory.trim()}';
        return 'Indexing job started in `$target`. Job ID: ${job.jobId}';

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

      case CommandType.workflow:
        if (cmd.arguments.isEmpty) {
          return 'Type `/workflow`, pick a workflow, then add the message to run it with.';
        }
        final workflowId = cmd.arguments.first;
        final triggerText = cmd.arguments.skip(1).join(' ').trim();
        final run = await client.runGatewayWorkflow(
          draftId: workflowId,
          query: triggerText.isEmpty ? rawText : triggerText,
          projectId: projectId,
          cancelToken: cancelToken,
        );
        final runId = run['run_id']?.toString() ?? '';
        return [
          'Workflow run started.',
          '',
          '- workflow_id: $workflowId',
          if (runId.isNotEmpty) '- run_id: $runId',
          '- status: ${run['status'] ?? 'pending'}',
          '',
          'Open Workflows to inspect completed, running, waiting, or broken blocks.',
        ].join('\n');

      case CommandType.unknown:
        final projectId = ref.read(activeProjectIdProvider);
        final result = await client.gatewayContext(
          task: rawText,
          sessionId: gatewaySessionId ?? uuid.v4(),
          projectId: projectId,
          role: ref.read(gatewayRoleProvider),
          cancelToken: cancelToken,
        );
        return _formatGatewayContext(result);
    }
  }

  Future<PipelineTrace> _collectPipelineTrace(
    String sessionId,
    CancelToken cancelToken,
  ) async {
    var trace = PipelineTrace.empty(sessionId);
    WebSocketChannel? channel;
    try {
      final client = ref.read(ripClientProvider);
      channel = WebSocketChannel.connect(
        client.chatPipelineWebSocketUri(sessionId),
      );
      cancelToken.whenCancel.then((_) => channel?.sink.close());
      await for (final raw in channel.stream) {
        final decoded = jsonDecode(raw as String) as Map<String, dynamic>;
        trace = trace.fold(PipelineEvent.fromJson(decoded));
        state = state
            .map((message) => message.id == sessionId
                ? message.copyWith(trace: trace)
                : message)
            .toList();
        if (trace.isComplete) break;
      }
    } catch (e) {
      log('Pipeline stream unavailable: $e');
    } finally {
      await channel?.sink.close();
    }
    return trace;
  }

  String _formatGatewayContext(Map<String, dynamic> result) {
    final buffer = StringBuffer();
    final intent = result['intent'];
    final domain = result['domain'];
    _lastGatewaySessionId = result['session_id'] as String?;
    if (intent != null || domain != null) {
      buffer.writeln('Intent: ${intent ?? 'unknown'} - Domain: ${domain ?? 'general'}\n');
    }
    final context = result['context'] as List? ?? const [];
    if (context.isEmpty) {
      return buffer.isEmpty ? 'No context returned.' : buffer.toString();
    }
    for (final item in context.take(6)) {
      if (item is Map<String, dynamic>) {
        final source = item['source'] ?? 'source';
        final score = (item['score'] as num?)?.toStringAsFixed(2);
        buffer.writeln('### $source${score == null ? '' : ' - score $score'}');
        buffer.writeln(item['content'] ?? '');
        buffer.writeln();
      }
    }
    final tokenAllocation = result['token_allocation'];
    if (tokenAllocation is Map && tokenAllocation.isNotEmpty) {
      buffer.writeln('Token allocation:');
      tokenAllocation.forEach((source, tokens) {
        buffer.writeln('- $source: $tokens');
      });
    }
    return buffer.toString();
  }

  String _encodeMetadata(
    List<RipResponseBlock>? blocks,
    PipelineTrace? trace,
  ) {
    return jsonEncode({
      'blocks': blocks?.map((block) => block.toJson()).toList() ?? const [],
      if (trace != null) 'trace': trace.toJson(),
    });
  }

  int _intFlag(ParsedCommand cmd, String name, {required int fallback}) {
    final value = cmd.flagValue(name);
    if (value == null || value == 'true') return fallback;
    return int.tryParse(value) ?? fallback;
  }
}

final chatProvider = NotifierProvider<ChatNotifier, List<Message>>(ChatNotifier.new);
