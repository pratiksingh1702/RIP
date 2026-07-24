import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../core/api/rip_client.dart';
import 'connection_provider.dart';
import '../../data/models/sandbox.dart';

class SandboxNotifier extends StateNotifier<SandboxState> {
  final RipClient _client;
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;

  SandboxNotifier(this._client) : super(SandboxState.initial());

  Future<void> createSandbox(String projectId, {String environment = 'python'}) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final result = await _client.createSandbox(projectId, environment);
      state = state.copyWith(
        isLoading: false,
        sandbox: Sandbox.fromJson(result),
        terminalOutputs: [],
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
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
    final wsUrl = serverUrl
        .replaceFirst('http', 'ws')
        .replaceFirst('https', 'wss');
    final uri = Uri.parse('$wsUrl/gateway/api/sandbox/$sandboxId/terminal/$sessionId');

    _channel = WebSocketChannel.connect(uri);
    _subscription = _channel!.stream.listen((data) {
      final msg = TerminalOutput.fromJson(jsonDecode(data));
      state = state.copyWith(
        terminalOutputs: [...state.terminalOutputs, msg],
        pendingApproval: msg.approvalNeeded ? msg : null,
      );
    });
    state = state.copyWith(isConnected: true);
  }

  void sendCommand(String command) {
    _channel?.sink.add(jsonEncode({'type': 'input', 'command': command}));
  }

  void approveCommand(String command) {
    _channel?.sink.add(jsonEncode({'type': 'approve', 'command': command}));
  }

  void rejectCommand(String command) {
    _channel?.sink.add(jsonEncode({'type': 'reject', 'command': command}));
  }

  void clearTerminal() {
    state = state.copyWith(terminalOutputs: [], pendingApproval: null);
  }

  Future<void> getStatus(String sandboxId) async {
    try {
      final data = await _client.getSandboxStatus(sandboxId);
      state = state.copyWith(status: SandboxStatus.fromJson(data));
    } catch (_) {}
  }

  @override
  void dispose() {
    _subscription?.cancel();
    _channel?.sink.close();
    super.dispose();
  }
}

class SandboxState {
  final bool isLoading;
  final bool isConnected;
  final String? error;
  final Sandbox? sandbox;
  final SandboxStatus? status;
  final List<SandboxTemplate> templates;
  final List<TerminalOutput> terminalOutputs;
  final TerminalOutput? pendingApproval;

  SandboxState({
    this.isLoading = false,
    this.isConnected = false,
    this.error,
    this.sandbox,
    this.status,
    this.templates = const [],
    this.terminalOutputs = const [],
    this.pendingApproval,
  });

  factory SandboxState.initial() => SandboxState();

  SandboxState copyWith({
    bool? isLoading,
    bool? isConnected,
    String? error,
    Sandbox? sandbox,
    SandboxStatus? status,
    List<SandboxTemplate>? templates,
    List<TerminalOutput>? terminalOutputs,
    TerminalOutput? pendingApproval,
    bool clearPending = false,
  }) => SandboxState(
    isLoading: isLoading ?? this.isLoading,
    isConnected: isConnected ?? this.isConnected,
    error: error,
    sandbox: sandbox ?? this.sandbox,
    status: status ?? this.status,
    templates: templates ?? this.templates,
    terminalOutputs: terminalOutputs ?? this.terminalOutputs,
    pendingApproval: clearPending ? null : (pendingApproval ?? this.pendingApproval),
  );
}

final sandboxProvider = StateNotifierProvider<SandboxNotifier, SandboxState>((ref) {
  final client = ref.read(ripClientProvider);
  return SandboxNotifier(client);
});
