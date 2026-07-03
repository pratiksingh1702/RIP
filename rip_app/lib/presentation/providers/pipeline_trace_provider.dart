import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../data/models/pipeline_trace.dart';
import 'connection_provider.dart';

final pipelineStreamProvider = StreamProvider.autoDispose
    .family<PipelineTrace, PipelineStreamArgs>((ref, args) async* {
  final client = ref.watch(ripClientProvider);
  var trace = args.initialTrace ?? PipelineTrace.empty(args.sessionId);
  var lastSeq = trace.lastSeq;

  while (true) {
    final uri = client.chatPipelineWebSocketUri(args.sessionId, afterSeq: lastSeq);
    final channel = WebSocketChannel.connect(uri);
    ref.onDispose(() => channel.sink.close());

    await for (final raw in channel.stream) {
      final decoded = jsonDecode(raw as String) as Map<String, dynamic>;
      final event = PipelineEvent.fromJson(decoded);
      trace = trace.fold(event);
      lastSeq = trace.lastSeq;
      yield trace;
      if (event.stage == 'done' || event.stage == 'pipeline_failed') {
        await channel.sink.close();
        return;
      }
    }

    await Future<void>.delayed(const Duration(milliseconds: 600));
  }
});

class PipelineStreamArgs {
  final String sessionId;
  final PipelineTrace? initialTrace;

  const PipelineStreamArgs({
    required this.sessionId,
    this.initialTrace,
  });

  @override
  bool operator ==(Object other) {
    return other is PipelineStreamArgs &&
        other.sessionId == sessionId &&
        other.initialTrace?.lastSeq == initialTrace?.lastSeq;
  }

  @override
  int get hashCode => Object.hash(sessionId, initialTrace?.lastSeq);
}
