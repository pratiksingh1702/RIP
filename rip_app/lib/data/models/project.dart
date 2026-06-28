import 'package:equatable/equatable.dart';

class Project extends Equatable {
  final String projectId;
  final String projectName;
  final String indexedAt;
  final int filesCount;
  final int entitiesCount;
  final List<String> languages;
  final String? gitUrl;

  const Project({
    required this.projectId,
    required this.projectName,
    required this.indexedAt,
    required this.filesCount,
    required this.entitiesCount,
    required this.languages,
    this.gitUrl,
  });

  factory Project.fromJson(Map<String, dynamic> json) => Project(
        projectId: json['project_id'] as String? ?? '',
        projectName: json['project_name'] as String? ?? '',
        indexedAt: json['indexed_at'] as String? ?? '',
        filesCount: json['files_count'] as int? ?? 0,
        entitiesCount: json['entities_count'] as int? ?? 0,
        languages: (json['languages'] as List<dynamic>?)
                ?.map((l) => l as String)
                .toList() ??
            [],
        gitUrl: json['git_url'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'project_id': projectId,
        'project_name': projectName,
        'indexed_at': indexedAt,
        'files_count': filesCount,
        'entities_count': entitiesCount,
        'languages': languages,
        'git_url': gitUrl,
      };

  @override
  List<Object?> get props => [
        projectId,
        projectName,
        indexedAt,
        filesCount,
        entitiesCount,
        languages,
        gitUrl,
      ];
}
