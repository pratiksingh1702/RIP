import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import 'package:rip_app/data/models/supervisor_event.dart';
import 'package:rip_app/presentation/providers/connection_provider.dart';
import 'package:rip_app/presentation/providers/settings_provider.dart';
import 'package:rip_app/presentation/providers/llm_config_provider.dart';

class SupervisorState {
  final String activeTaskId;
  final bool isLoading;
  final bool isPaused;
  final List<SupervisorMessage> messages;
  final List<FilePlanItem> activeFilePlans;
  final String? error;

  const SupervisorState({
    this.activeTaskId = '',
    this.isLoading = false,
    this.isPaused = false,
    this.messages = const [],
    this.activeFilePlans = const [],
    this.error,
  });

  SupervisorState copyWith({
    String? activeTaskId,
    bool? isLoading,
    bool? isPaused,
    List<SupervisorMessage>? messages,
    List<FilePlanItem>? activeFilePlans,
    String? error,
  }) {
    return SupervisorState(
      activeTaskId: activeTaskId ?? this.activeTaskId,
      isLoading: isLoading ?? this.isLoading,
      isPaused: isPaused ?? this.isPaused,
      messages: messages ?? this.messages,
      activeFilePlans: activeFilePlans ?? this.activeFilePlans,
      error: error,
    );
  }
}

class SupervisorNotifier extends StateNotifier<SupervisorState> {
  final Ref _ref;

  SupervisorNotifier(this._ref) : super(const SupervisorState());

  void setActiveTask(String taskId) {
    state = state.copyWith(activeTaskId: taskId, messages: []);
  }

  Future<void> sendMessage(String userMessage) async {
    if (userMessage.trim().isEmpty || state.activeTaskId.isEmpty) return;

    final userMsg = SupervisorMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      taskId: state.activeTaskId,
      sender: 'user',
      content: userMessage,
      timestamp: DateTime.now(),
    );

    state = state.copyWith(
      isLoading: true,
      messages: [...state.messages, userMsg],
      error: null,
    );

    try {
      final baseUrl = _ref.read(serverUrlProvider);
      final apiKey = _ref.read(apiKeyProvider);
      final preferredConfigId = _ref.read(preferredLLMConfigProvider);

      final headers = <String, String>{
        'Content-Type': 'application/json',
        if (apiKey != null && apiKey.isNotEmpty) 'Authorization': 'Bearer $apiKey',
      };

      final response = await http.post(
        Uri.parse('$baseUrl/gateway/api/supervisor/chat'),
        headers: headers,
        body: jsonEncode({
          'task_id': state.activeTaskId,
          'message': userMessage,
          if (preferredConfigId != null) 'llm_config_id': preferredConfigId,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final supervisorMsg = SupervisorMessage.fromJson(data);
        state = state.copyWith(
          isLoading: false,
          messages: [...state.messages, supervisorMsg],
        );
      } else {
        state = state.copyWith(
          isLoading: false,
          error: 'Failed to reach Supervisor (${response.statusCode})',
        );
      }
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Network error: $e',
      );
    }
  }

  Future<void> sendSignal(String signalType, {Map<String, dynamic>? payload}) async {
    if (state.activeTaskId.isEmpty) return;

    try {
      final baseUrl = _ref.read(serverUrlProvider);
      final apiKey = _ref.read(apiKeyProvider);
      final headers = <String, String>{
        'Content-Type': 'application/json',
        if (apiKey != null && apiKey.isNotEmpty) 'Authorization': 'Bearer $apiKey',
      };

      final response = await http.post(
        Uri.parse('$baseUrl/gateway/api/supervisor/signal'),
        headers: headers,
        body: jsonEncode({
          'task_id': state.activeTaskId,
          'signal_type': signalType,
          'payload': payload ?? {},
        }),
      );

      if (response.statusCode == 200) {
        if (signalType == 'pause') {
          state = state.copyWith(isPaused: true);
        } else if (signalType == 'resume') {
          state = state.copyWith(isPaused: false);
        }
      }
    } catch (e) {
      state = state.copyWith(error: 'Signal failed: $e');
    }
  }
}

final supervisorProvider =
    StateNotifierProvider<SupervisorNotifier, SupervisorState>((ref) {
  return SupervisorNotifier(ref);
});
