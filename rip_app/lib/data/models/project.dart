import 'package:equatable/equatable.dart';

class Project extends Equatable {
  final String projectId;
  final String projectName;
  final String indexedAt;
  final int filesCount;
  final int entitiesCount;
  final List<String> languages;
  final String? root;
  final String? gitUrl;
  final String? branch;
  final String? author;

  const Project({
    required this.projectId,
    required this.projectName,
    required this.indexedAt,
    required this.filesCount,
    required this.entitiesCount,
    required this.languages,
    this.root,
    this.gitUrl,
    this.branch,
    this.author,
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
        root: json['root'] as String? ?? json['root_path'] as String?,
        gitUrl: json['git_url'] as String?,
        branch: json['branch'] as String? ?? json['git_branch'] as String?,
        author: json['author'] as String? ??
            json['owner'] as String? ??
            json['created_by'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'project_id': projectId,
        'project_name': projectName,
        'indexed_at': indexedAt,
        'files_count': filesCount,
        'entities_count': entitiesCount,
        'languages': languages,
        'root': root,
        'git_url': gitUrl,
        'branch': branch,
        'author': author,
      };

  String? get repositoryOwner {
    if (author != null && author!.trim().isNotEmpty) return author;
    if (gitUrl == null || gitUrl!.trim().isEmpty) return null;

    final cleaned = gitUrl!
        .replaceFirst(RegExp(r'^https?://'), '')
        .replaceFirst(RegExp(r'^git@'), '')
        .replaceFirst(':', '/')
        .replaceAll(RegExp(r'\.git$'), '');
    final parts = cleaned.split('/').where((part) => part.isNotEmpty).toList();
    if (parts.length >= 2) return parts[parts.length - 2];
    return null;
  }

  String get locationLabel {
    if (root != null && root!.trim().isNotEmpty) return root!;
    if (gitUrl != null && gitUrl!.trim().isNotEmpty) return gitUrl!;
    return 'Local indexed workspace';
  }

  @override
  List<Object?> get props => [
        projectId,
        projectName,
        indexedAt,
        filesCount,
        entitiesCount,
        languages,
        root,
        gitUrl,
        branch,
        author,
      ];
}
