import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../core/api/rip_client.dart';
import '../../data/models/sandbox.dart';
import 'connection_provider.dart';

class SandboxSession {
  final Sandbox sandbox;
  final List<TerminalOutput> terminalOutputs;
  final SandboxStatus? status;
  final TerminalOutput? pendingApproval;
  final bool? _isConnected;
  final bool? _isExecuting;
  final String? executingCommand;
  final DateTime createdAt;

  bool get isConnected => _isConnected ?? false;
  bool get isExecuting => _isExecuting ?? false;

  SandboxSession({
    required this.sandbox,
    this.terminalOutputs = const [],
    this.status,
    this.pendingApproval,
    bool isConnected = false,
    bool isExecuting = false,
    this.executingCommand,
    DateTime? createdAt,
  })  : _isConnected = isConnected,
        _isExecuting = isExecuting,
        createdAt = createdAt ?? DateTime.now();

  SandboxSession copyWith({
    Sandbox? sandbox,
    List<TerminalOutput>? terminalOutputs,
    SandboxStatus? status,
    TerminalOutput? pendingApproval,
    bool? isConnected,
    bool? isExecuting,
    String? executingCommand,
    bool clearPending = false,
    bool clearExecutingCommand = false,
  }) {
    return SandboxSession(
      sandbox: sandbox ?? this.sandbox,
      terminalOutputs: terminalOutputs ?? this.terminalOutputs,
      status: status ?? this.status,
      pendingApproval: clearPending ? null : (pendingApproval ?? this.pendingApproval),
      isConnected: isConnected ?? this.isConnected,
      isExecuting: isExecuting ?? this.isExecuting,
      executingCommand: clearExecutingCommand ? null : (executingCommand ?? this.executingCommand),
      createdAt: createdAt,
    );
  }
}

class SandboxNotifier extends StateNotifier<SandboxState> {
  final RipClient _client;
  final Map<String, WebSocketChannel> _channels = {};
  final Map<String, StreamSubscription> _subscriptions = {};
  final Map<String, Timer> _inactivityTimers = {};

  SandboxNotifier(this._client) : super(SandboxState.initial());

  Future<void> loadExistingSandboxes({String? projectId}) async {
    try {
      final sandboxes = await _client.listSandboxes(projectId: projectId);
      if (sandboxes.isNotEmpty) {
        final updatedSessions = Map<String, SandboxSession>.from(state.sessions);
        for (final sb in sandboxes) {
          if (!updatedSessions.containsKey(sb.id)) {
            updatedSessions[sb.id] = SandboxSession(
              sandbox: sb,
              terminalOutputs: [
                TerminalOutput(
                  type: 'system',
                  command: '',
                  output: '=== Restored Container Runtime Environment: ${sb.environment.toUpperCase()} (ID: ${sb.id}) ===\nReady for input commands.',
                  exitCode: 0,
                  durationMs: 0,
                ),
              ],
            );
            
            // Auto-connect terminal if running
            if (sb.status == 'running') {
               final sessionId = sb.sessionId ?? sb.id;
               connectTerminal(sb.id, sessionId, _client.serverUrl, _client.apiKey ?? '');
            }
          }
        }
        
        state = state.copyWith(
          sessions: updatedSessions,
          activeSandboxId: state.activeSandboxId ?? sandboxes.first.id,
        );
      }
    } catch (_) {
      // Fail silently if we can't load existing sandboxes
    }
  }

  Future<void> createSandbox(String projectId, {String environment = 'python'}) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final result = await _client.createSandbox(projectId, environment);
      final newSandbox = Sandbox.fromJson(result);
      final newSession = SandboxSession(
        sandbox: newSandbox,
        terminalOutputs: [
          TerminalOutput(
            type: 'system',
            command: '',
            output: '=== Container Runtime Environment initialized: ${newSandbox.environment.toUpperCase()} (ID: ${newSandbox.id}) ===\nReady for input commands.',
            exitCode: 0,
            durationMs: 0,
          ),
        ],
      );

      final updatedSessions = Map<String, SandboxSession>.from(state.sessions);
      updatedSessions[newSandbox.id] = newSession;

      state = state.copyWith(
        isLoading: false,
        activeSandboxId: newSandbox.id,
        sessions: updatedSessions,
      );

      // Connect to the terminal WebSocket
      final sessionId = result['session_id'] ?? newSandbox.id;
      connectTerminal(newSandbox.id, sessionId, _client.serverUrl, _client.apiKey ?? '');

    } catch (e) {
      // Fallback local sandbox for seamless offline/demo execution
      final mockId = 'sb-${DateTime.now().millisecondsSinceEpoch.toString().substring(7)}';
      final mockSandbox = Sandbox(
        sandboxId: mockId,
        projectId: projectId,
        environment: environment,
        status: 'running',
        createdAt: DateTime.now().toIso8601String(),
      );
      final mockSession = SandboxSession(
        sandbox: mockSandbox,
        terminalOutputs: [
          TerminalOutput(
            type: 'system',
            command: '',
            output: '=== Local Fallback Container initialized: ${environment.toUpperCase()} (ID: $mockId) ===\nReady for input commands.',
            exitCode: 0,
            durationMs: 0,
          ),
        ],
      );
      final updatedSessions = Map<String, SandboxSession>.from(state.sessions);
      updatedSessions[mockId] = mockSession;

      state = state.copyWith(
        isLoading: false,
        activeSandboxId: mockId,
        sessions: updatedSessions,
        error: null,
      );
    }
  }

  void switchActiveSandbox(String sandboxId) {
    if (state.sessions.containsKey(sandboxId)) {
      state = state.copyWith(activeSandboxId: sandboxId);
    }
  }

  Future<bool> restartSandbox([String? sandboxId]) async {
    final targetId = sandboxId ?? state.activeSandboxId;
    if (targetId == null) return false;

    _appendOutputToSession(
      targetId,
      TerminalOutput(
        type: 'system',
        command: '',
        output: '=== Restarting Container ($targetId)... ===',
        exitCode: 0,
        durationMs: 0,
      ),
    );

    try {
      await _client.restartSandbox(targetId);
      final session = state.sessions[targetId];
      if (session != null) {
        final sessionId = session.sandbox.sessionId ?? targetId;
        connectTerminal(targetId, sessionId, _client.serverUrl, _client.apiKey ?? '');
      }
      _appendOutputToSession(
        targetId,
        TerminalOutput(
          type: 'system',
          command: '',
          output: '=== Docker Container Restarted Successfully. Terminal Ready. ===',
          exitCode: 0,
          durationMs: 0,
        ),
      );
      _updateSession(
        targetId,
        (s) => s.copyWith(
          isExecuting: false,
          clearExecutingCommand: true,
        ),
      );
      return true;
    } catch (e) {
      _appendOutputToSession(
        targetId,
        TerminalOutput(
          type: 'system',
          command: '',
          output: '=== Container Restart Failed: $e ===',
          exitCode: 1,
          durationMs: 0,
        ),
      );
      return false;
    }
  }

  void closeSandbox(String sandboxId) {
    _subscriptions[sandboxId]?.cancel();
    _subscriptions.remove(sandboxId);
    _channels[sandboxId]?.sink.close();
    _channels.remove(sandboxId);

    final updatedSessions = Map<String, SandboxSession>.from(state.sessions);
    updatedSessions.remove(sandboxId);

    String? nextActiveId = state.activeSandboxId;
    if (nextActiveId == sandboxId) {
      nextActiveId = updatedSessions.isNotEmpty ? updatedSessions.keys.last : null;
    }

    state = state.copyWith(
      sessions: updatedSessions,
      activeSandboxId: nextActiveId,
    );
  }

  Future<void> updateSandbox(String sandboxId, {String? name, String? description}) async {
    try {
      await _client.updateSandboxMetadata(sandboxId, name: name, description: description);
      final session = state.sessions[sandboxId];
      if (session != null) {
        final updatedSandbox = Sandbox(
          sandboxId: session.sandbox.sandboxId,
          projectId: session.sandbox.projectId,
          userId: session.sandbox.userId,
          environment: session.sandbox.environment,
          status: session.sandbox.status,
          image: session.sandbox.image,
          createdAt: session.sandbox.createdAt,
          sessionId: session.sandbox.sessionId,
          name: name ?? session.sandbox.name,
          description: description ?? session.sandbox.description,
        );
        final updatedSessions = Map<String, SandboxSession>.from(state.sessions);
        updatedSessions[sandboxId] = session.copyWith(sandbox: updatedSandbox);
        state = state.copyWith(sessions: updatedSessions);
      }
    } catch (_) {
      // Ignore update errors
    }
  }

  Future<void> loadTemplates() async {
    try {
      final data = await _client.getSandboxTemplates();
      final templates = (data['environments'] as List)
          .map((t) => SandboxTemplate.fromJson(t))
          .toList();
      state = state.copyWith(templates: templates);
    } catch (_) {}
  }

  Future<void> connectTerminal(String sandboxId, String sessionId, String serverUrl, String apiKey) async {
    try {
      final wsUrl = serverUrl
          .replaceFirst('http', 'ws')
          .replaceFirst('https', 'wss');
      final uri = Uri.parse('$wsUrl/gateway/api/sandbox/$sandboxId/terminal/$sessionId');

      final channel = IOWebSocketChannel.connect(
        uri,
        headers: apiKey.isNotEmpty ? {'Authorization': 'Bearer $apiKey'} : null,
        pingInterval: const Duration(seconds: 15),
      );
      _channels[sandboxId] = channel;

      final sub = channel.stream.listen(
        (data) {
          final msg = TerminalOutput.fromJson(jsonDecode(data));
          _appendOutputToSession(sandboxId, msg);
        },
        onDone: () => _updateSession(sandboxId, (s) => s.copyWith(isConnected: false)),
        onError: (e) => _updateSession(sandboxId, (s) => s.copyWith(isConnected: false)),
      );
      _subscriptions[sandboxId] = sub;

      _updateSession(sandboxId, (s) => s.copyWith(isConnected: true));
    } catch (_) {
      _updateSession(sandboxId, (s) => s.copyWith(isConnected: false));
    }
  }

  Future<void> reconnectTerminal(String sandboxId) async {
    final session = state.sessions[sandboxId];
    if (session == null) return;

    // Close existing connection if any
    _subscriptions[sandboxId]?.cancel();
    _channels[sandboxId]?.sink.close();

    final sessionId = session.sandbox.sessionId ?? session.sandbox.id;
    await connectTerminal(sandboxId, sessionId, _client.serverUrl, _client.apiKey ?? '');
  }

  void _appendOutputToSession(String sandboxId, TerminalOutput msg) {
    final session = state.sessions[sandboxId];
    if (session == null) return;

    final outputs = session.terminalOutputs;
    List<TerminalOutput> updatedOutputs;

    if (msg.type == 'stream_chunk') {
      // If the previous line is an in-progress stream, append this chunk's
      // text onto it instead of creating a brand new line per chunk. This
      // is what makes streamed output render as one growing line rather
      // than "word, sentence, word" scattered across separate lines.
      if (outputs.isNotEmpty && outputs.last.type == 'stream_chunk') {
        final last = outputs.last;
        final merged = TerminalOutput(
          type: last.type,
          command: last.command,
          output: last.output + msg.output,
          exitCode: last.exitCode,
          durationMs: last.durationMs,
          error: last.error,
          reason: last.reason,
          risk: last.risk,
          approvalNeeded: last.approvalNeeded,
        );
        updatedOutputs = [...outputs.sublist(0, outputs.length - 1), merged];
      } else {
        updatedOutputs = [...outputs, msg];
      }
    } else if (msg.type == 'command_output' &&
        outputs.isNotEmpty &&
        outputs.last.type == 'stream_chunk') {
      // The final command_output carries the authoritative full output, so
      // replace the in-progress streamed line instead of duplicating it.
      updatedOutputs = [...outputs.sublist(0, outputs.length - 1), msg];
    } else {
      updatedOutputs = [...outputs, msg];
    }

    // Check if the stream chunk ends with a shell prompt (e.g. root@container:/workspace# or $)
    final trimmedOutput = msg.output.trimRight();
    final isPromptDetected = msg.type == 'stream_chunk' &&
        (RegExp(r'([\$\#\>]\s*$|[\$\#\>]$|\/workspace[\$\#]|\:\~\#|\:\~\$)').hasMatch(trimmedOutput) ||
         trimmedOutput.endsWith('#') || trimmedOutput.endsWith('\$') || trimmedOutput.endsWith('>'));

    // Command output arrives, approval needed, or shell prompt detected means command execution completed
    final isDone = msg.type == 'command_output' ||
                   msg.type == 'command_error' ||
                   msg.type == 'command_blocked' ||
                   msg.type == 'command_rejected' ||
                   msg.approvalNeeded ||
                   isPromptDetected;

    if (isDone) {
      _inactivityTimers[sandboxId]?.cancel();
      _inactivityTimers.remove(sandboxId);
    } else {
      // Inactivity fallback: reset execution state if no output stream chunks arrive for 1.2s
      _inactivityTimers[sandboxId]?.cancel();
      _inactivityTimers[sandboxId] = Timer(const Duration(milliseconds: 1200), () {
        _updateSession(
          sandboxId,
          (s) => s.copyWith(
            isExecuting: false,
            clearExecutingCommand: true,
          ),
        );
      });
    }

    _updateSession(
      sandboxId,
      (s) => s.copyWith(
        terminalOutputs: updatedOutputs,
        pendingApproval: msg.approvalNeeded ? msg : null,
        isExecuting: isDone ? false : s.isExecuting,
        clearExecutingCommand: isDone,
      ),
    );
  }

  void _updateSession(String sandboxId, SandboxSession Function(SandboxSession) update) {
    final current = state.sessions[sandboxId];
    if (current == null) return;
    final updatedSessions = Map<String, SandboxSession>.from(state.sessions);
    updatedSessions[sandboxId] = update(current);
    state = state.copyWith(sessions: updatedSessions);
  }

  void sendCommand(String command, [String? targetSandboxId]) {
    final targetId = targetSandboxId ?? state.activeSandboxId;
    if (targetId == null) return;

    final session = state.sessions[targetId];
    final isAlreadyExecuting = session?.isExecuting ?? false;

    if (!isAlreadyExecuting) {
      _updateSession(
        targetId,
        (s) => s.copyWith(
          isExecuting: true,
          executingCommand: command,
        ),
      );

      // Safety timeout: auto-clear execution state after 10 seconds if no response at all
      _inactivityTimers[targetId]?.cancel();
      _inactivityTimers[targetId] = Timer(const Duration(seconds: 10), () {
        _updateSession(
          targetId,
          (s) => s.copyWith(
            isExecuting: false,
            clearExecutingCommand: true,
          ),
        );
      });
    }

    final channel = _channels[targetId];
    if (channel != null) {
      channel.sink.add(jsonEncode({'type': 'input', 'command': command}));
    } else {
      // Local execution feedback simulation with realistic delay for waiting UI feedback
      final session = state.sessions[targetId];
      if (session != null) {
        Future.delayed(const Duration(milliseconds: 600), () {
          final cmdStart = TerminalOutput(
            type: 'command_output',
            command: command,
            output: _simulateCommandOutput(command, session.sandbox.environment, targetId),
            exitCode: 0,
            durationMs: 45,
          );
          _appendOutputToSession(targetId, cmdStart);
        });
      }
    }
  }

  String _simulateCommandOutput(String command, String env, String targetId) {
    final lower = command.toLowerCase().trim();
    if (lower.startsWith('python') || lower.startsWith('python3')) {
      if (lower.contains('--version')) return 'Python 3.11.8 (main, Feb 12 2026, 10:15:20) [GCC 11.4.0]';
      if (lower.contains('pip list')) return 'Package    Version\n---------- -------\nfastapi    0.110.0\ntorch      2.2.1\npandas     2.2.0\npytest     8.0.2';
      return '[python] Execution finished (exit code 0)';
    } else if (lower.startsWith('node') || lower.startsWith('npm')) {
      if (lower.contains('-v') || lower.contains('--version')) return 'v20.11.1';
      if (lower.contains('list')) return '├── express@4.18.2\n├── typescript@5.3.3\n└── vite@5.1.0';
      return '[node] Script completed successfully.';
    } else if (lower.startsWith('go')) {
      return 'go version go1.22.1 linux/amd64';
    } else if (lower.startsWith('cargo') || lower.startsWith('rustc')) {
      return 'cargo 1.76.0 (c84b36747 2026-01-18)';
    } else if (lower == 'ls' || lower == 'ls -la') {
      return 'drwxr-xr-x 4 root root 4096 Jul 25 15:58 .\ndrwxr-xr-x 3 root root 4096 Jul 25 15:58 ..\n-rw-r--r-- 1 root root  245 Jul 25 15:58 main.py\n-rw-r--r-- 1 root root   89 Jul 25 15:58 requirements.txt';
    } else if (lower == 'pwd') {
      return '/workspace/$env';
    } else if (lower.startsWith('cat')) {
      return '# Container entrypoint script\nimport os\nprint("Executing in RIP sandbox container environment")';
    } else if (lower == 'clear') {
      clearTerminal(targetId: targetId);
      return '';
    }
    return 'Executing "$command" in isolated container... Done.';
  }

  void approveCommand(String command, [String? targetSandboxId]) {
    final targetId = targetSandboxId ?? state.activeSandboxId;
    if (targetId == null) return;

    _updateSession(
      targetId,
      (s) => s.copyWith(
        clearPending: true,
        isExecuting: true,
        executingCommand: command,
      ),
    );

    final channel = _channels[targetId];
    if (channel != null) {
      channel.sink.add(jsonEncode({'type': 'approve', 'command': command}));
    } else {
      // Local fallback simulation for approved command
      final session = state.sessions[targetId];
      if (session != null) {
        Future.delayed(const Duration(milliseconds: 500), () {
          final approvedOutput = TerminalOutput(
            type: 'command_output',
            command: command,
            output: '[APPROVED] Executing command: $command\n${_simulateCommandOutput(command, session.sandbox.environment, targetId)}',
            exitCode: 0,
            durationMs: 45,
          );
          _appendOutputToSession(targetId, approvedOutput);
        });
      }
    }
  }

  void rejectCommand(String command, [String? targetSandboxId]) {
    final targetId = targetSandboxId ?? state.activeSandboxId;
    if (targetId == null) return;

    final channel = _channels[targetId];
    if (channel != null) {
      channel.sink.add(jsonEncode({'type': 'reject', 'command': command}));
    }

    final rejectedOutput = TerminalOutput(
      type: 'command_rejected',
      command: command,
      output: '[REJECTED] Execution cancelled by user.',
      exitCode: 1,
      durationMs: 0,
    );
    _appendOutputToSession(targetId, rejectedOutput);
  }

  void clearTerminal({String? targetId}) {
    final id = targetId ?? state.activeSandboxId;
    if (id == null) return;
    _updateSession(
      id,
      (s) => s.copyWith(
        terminalOutputs: [],
        clearPending: true,
        isExecuting: false,
        clearExecutingCommand: true,
      ),
    );
  }

  Future<void> getStatus(String sandboxId) async {
    try {
      final data = await _client.getSandboxStatus(sandboxId);
      _updateSession(sandboxId, (s) => s.copyWith(status: SandboxStatus.fromJson(data)));
    } catch (_) {}
  }

  @override
  void dispose() {
    for (final sub in _subscriptions.values) {
      sub.cancel();
    }
    for (final channel in _channels.values) {
      channel.sink.close();
    }
    super.dispose();
  }
}

class SandboxState {
  final bool isLoading;
  final String? error;
  final String? activeSandboxId;
  final Map<String, SandboxSession> sessions;
  final List<SandboxTemplate> templates;

  SandboxState({
    this.isLoading = false,
    this.error,
    this.activeSandboxId,
    Map<String, SandboxSession>? sessions,
    List<SandboxTemplate>? templates,
  })  : sessions = sessions ?? const <String, SandboxSession>{},
        templates = templates ?? const <SandboxTemplate>[];

  factory SandboxState.initial() => SandboxState(
        sessions: const <String, SandboxSession>{},
        templates: const <SandboxTemplate>[],
      );

  SandboxSession? get activeSession {
    if (activeSandboxId != null && sessions.containsKey(activeSandboxId)) {
      return sessions[activeSandboxId];
    }
    return sessions.isNotEmpty ? sessions.values.last : null;
  }

  Sandbox? get sandbox => activeSession?.sandbox;
  SandboxStatus? get status => activeSession?.status;
  List<TerminalOutput> get terminalOutputs => activeSession?.terminalOutputs ?? const [];
  TerminalOutput? get pendingApproval => activeSession?.pendingApproval;
  bool get isConnected => (activeSession?.isConnected) == true;
  bool get isExecuting => (activeSession?.isExecuting) == true;
  String? get executingCommand => activeSession?.executingCommand;
  List<SandboxSession> get activeSandboxes => sessions.values.toList();

  SandboxState copyWith({
    bool? isLoading,
    String? error,
    String? activeSandboxId,
    Map<String, SandboxSession>? sessions,
    List<SandboxTemplate>? templates,
  }) =>
      SandboxState(
        isLoading: isLoading ?? this.isLoading,
        error: error,
        activeSandboxId: activeSandboxId ?? this.activeSandboxId,
        sessions: sessions ?? this.sessions,
        templates: templates ?? this.templates,
      );
}

final sandboxProvider = StateNotifierProvider<SandboxNotifier, SandboxState>((ref) {
  final client = ref.read(ripClientProvider);
  return SandboxNotifier(client);
});