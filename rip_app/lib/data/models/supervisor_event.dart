import 'package:flutter/foundation.dart';

@immutable
class SupervisorMessage {
  final String id;
  final String taskId;
  final String sender; // 'user' | 'supervisor'
  final String content;
  final String tier; // 'tier1' | 'tier2'
  final DateTime timestamp;
  final List<String> actions;

  const SupervisorMessage({
    required this.id,
    required this.taskId,
    required this.sender,
    required this.content,
    this.tier = 'tier1',
    required this.timestamp,
    this.actions = const [],
  });

  factory SupervisorMessage.fromJson(Map<String, dynamic> json) {
    return SupervisorMessage(
      id: json['id'] as String? ?? DateTime.now().millisecondsSinceEpoch.toString(),
      taskId: json['task_id'] as String? ?? '',
      sender: json['sender'] as String? ?? 'supervisor',
      content: json['answer'] as String? ?? json['content'] as String? ?? '',
      tier: json['tier'] as String? ?? 'tier1',
      timestamp: json['timestamp'] != null
          ? DateTime.parse(json['timestamp'] as String)
          : DateTime.now(),
      actions: (json['actions'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
    );
  }
}

@immutable
class FilePlanItem {
  final String filePath;
  final String rationale;
  final String proposedDiff;
  final bool hasHighFanIn;
  final int dependentCount;

  const FilePlanItem({
    required this.filePath,
    this.rationale = '',
    this.proposedDiff = '',
    this.hasHighFanIn = false,
    this.dependentCount = 0,
  });

  factory FilePlanItem.fromJson(Map<String, dynamic> json) {
    return FilePlanItem(
      filePath: json['file_path'] as String? ?? '',
      rationale: json['rationale'] as String? ?? '',
      proposedDiff: json['proposed_diff'] as String? ?? '',
      hasHighFanIn: json['has_high_fan_in'] as bool? ?? false,
      dependentCount: json['dependent_count'] as int? ?? 0,
    );
  }
}
