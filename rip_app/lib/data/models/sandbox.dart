/// Sandbox data models
class Sandbox {
  final String sandboxId;
  final String projectId;
  final String userId;
  final String environment;
  final String status;
  final String image;
  final String createdAt;
  final String? sessionId;

  String get id => sandboxId;

  Sandbox({
    required this.sandboxId,
    required this.projectId,
    this.userId = '',
    required this.environment,
    required this.status,
    this.image = '',
    required this.createdAt,
    this.sessionId,
  });

  factory Sandbox.fromJson(Map<String, dynamic> json) => Sandbox(
    sandboxId: json['sandbox_id'] ?? '',
    projectId: json['project_id'] ?? '',
    userId: json['user_id'] ?? '',
    environment: json['environment'] ?? 'python',
    status: json['status'] ?? 'unknown',
    image: json['image'] ?? '',
    createdAt: json['created_at'] ?? '',
    sessionId: json['session_id'],
  );

  Map<String, dynamic> toJson() => {
    'sandbox_id': sandboxId,
    'project_id': projectId,
    'environment': environment,
  };
}

class SandboxStatus {
  final String sandboxId;
  final String status;
  final double cpuPercent;
  final int memoryUsedBytes;
  final int memoryLimitBytes;
  final double memoryPercent;

  SandboxStatus({
    required this.sandboxId,
    required this.status,
    this.cpuPercent = 0,
    this.memoryUsedBytes = 0,
    this.memoryLimitBytes = 0,
    this.memoryPercent = 0,
  });

  factory SandboxStatus.fromJson(Map<String, dynamic> json) => SandboxStatus(
    sandboxId: json['sandbox_id'] ?? '',
    status: json['status'] ?? 'unknown',
    cpuPercent: (json['cpu_percent'] ?? 0).toDouble(),
    memoryUsedBytes: json['memory_used_bytes'] ?? 0,
    memoryLimitBytes: json['memory_limit_bytes'] ?? 0,
    memoryPercent: (json['memory_percent'] ?? 0).toDouble(),
  );
}

class SandboxTemplate {
  final String id;
  final String name;
  final String description;
  final String icon;
  final String color;

  SandboxTemplate({
    required this.id,
    required this.name,
    required this.description,
    this.icon = 'terminal',
    this.color = '#64748B',
  });

  factory SandboxTemplate.fromJson(Map<String, dynamic> json) => SandboxTemplate(
    id: json['id'] ?? '',
    name: json['name'] ?? '',
    description: json['description'] ?? '',
    icon: json['icon'] ?? 'terminal',
    color: json['color'] ?? '#64748B',
  );
}

class TerminalOutput {
  final String type;
  final String command;
  final String output;
  final int exitCode;
  final int durationMs;
  final String? error;
  final String? reason;
  final String? risk;
  final bool approvalNeeded;

  TerminalOutput({
    required this.type,
    this.command = '',
    this.output = '',
    this.exitCode = 0,
    this.durationMs = 0,
    this.error,
    this.reason,
    this.risk,
    this.approvalNeeded = false,
  });

  factory TerminalOutput.fromJson(Map<String, dynamic> json) => TerminalOutput(
    type: json['type'] ?? 'output',
    command: json['command'] ?? '',
    output: json['output'] ?? '',
    exitCode: json['exit_code'] ?? 0,
    durationMs: json['duration_ms'] ?? 0,
    error: json['error'],
    reason: json['reason'],
    risk: json['risk'],
    approvalNeeded: json['type'] == 'approval_needed',
  );
}
