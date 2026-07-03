class PipelineEvent {
  final String sessionId;
  final String stage;
  final String status;
  final String detail;
  final String? source;
  final Map<String, dynamic> meta;
  final int seq;
  final DateTime timestamp;

  const PipelineEvent({
    required this.sessionId,
    required this.stage,
    required this.status,
    required this.detail,
    required this.meta,
    required this.seq,
    required this.timestamp,
    this.source,
  });

  factory PipelineEvent.fromJson(Map<String, dynamic> json) {
    return PipelineEvent(
      sessionId: json['session_id'] as String? ?? '',
      stage: json['stage'] as String? ?? '',
      status: json['status'] as String? ?? '',
      detail: json['detail'] as String? ?? '',
      source: json['source'] as String?,
      meta: Map<String, dynamic>.from(json['meta'] as Map? ?? const {}),
      seq: (json['seq'] as num?)?.toInt() ?? 0,
      timestamp: DateTime.tryParse(json['ts'] as String? ?? '') ?? DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'session_id': sessionId,
      'stage': stage,
      'status': status,
      'detail': detail,
      'source': source,
      'meta': meta,
      'seq': seq,
      'ts': timestamp.toUtc().toIso8601String(),
    };
  }

  String get rowKey => source == null || source!.isEmpty ? stage : '$stage:$source';
}

class PipelineTrace {
  final String sessionId;
  final List<PipelineEvent> events;

  const PipelineTrace({
    required this.sessionId,
    required this.events,
  });

  factory PipelineTrace.empty(String sessionId) {
    return PipelineTrace(sessionId: sessionId, events: const []);
  }

  factory PipelineTrace.fromJson(Map<String, dynamic> json) {
    final events = (json['events'] as List? ?? const [])
        .whereType<Map>()
        .map((event) => PipelineEvent.fromJson(Map<String, dynamic>.from(event)))
        .toList()
      ..sort((a, b) => a.seq.compareTo(b.seq));
    return PipelineTrace(
      sessionId: json['session_id'] as String? ??
          (events.isNotEmpty ? events.first.sessionId : ''),
      events: events,
    );
  }

  int get lastSeq => events.isEmpty ? 0 : events.last.seq;
  bool get isComplete => events.any((event) => event.stage == 'done');
  bool get hasEvents => events.isNotEmpty;

  PipelineTrace withSessionId(String value) {
    return PipelineTrace(sessionId: value, events: events);
  }

  PipelineTrace fold(PipelineEvent event) {
    final next = [...events];
    final updateIndex = event.source == null
        ? -1
        : next.indexWhere((existing) =>
            existing.source == event.source &&
            existing.stage.startsWith('source_') &&
            event.stage.startsWith('source_'));
    if (updateIndex >= 0) {
      next[updateIndex] = event;
    } else if (!next.any((existing) => existing.seq == event.seq)) {
      next.add(event);
    }
    next.sort((a, b) => a.seq.compareTo(b.seq));
    return PipelineTrace(sessionId: sessionId, events: next);
  }

  Map<String, dynamic> toJson() {
    return {
      'session_id': sessionId,
      'events': events.map((event) => event.toJson()).toList(),
    };
  }

  String summaryLabel() {
    final intent = _lastWhereOrNull(events, (event) => event.stage == 'intent');
    final sourceEvents = events.where((event) => event.stage == 'source_done').toList();
    final compress = _lastWhereOrNull(events, (event) => event.stage == 'compress');
    final done = _lastWhereOrNull(events, (event) => event.stage == 'done');
    final first = events.isEmpty ? null : events.first;
    final elapsed = first == null || done == null
        ? null
        : done.timestamp.difference(first.timestamp).inMilliseconds;
    final pieces = <String>[
      if (intent != null) intent.meta['intent']?.toString() ?? intent.detail,
      if (sourceEvents.isNotEmpty) '${sourceEvents.length} sources',
      if (compress?.meta['after_tokens'] != null) '${compress!.meta['after_tokens']} tokens',
      if (elapsed != null) '${(elapsed / 1000).toStringAsFixed(1)}s',
    ];
    return pieces.isEmpty ? 'Pipeline trace' : pieces.join(' - ');
  }

  T? _lastWhereOrNull<T>(List<T> values, bool Function(T value) test) {
    for (var index = values.length - 1; index >= 0; index--) {
      if (test(values[index])) return values[index];
    }
    return null;
  }
}
