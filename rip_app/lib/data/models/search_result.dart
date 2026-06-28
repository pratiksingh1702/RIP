import 'package:equatable/equatable.dart';

class SearchResult extends Equatable {
  final String entityId;
  final String entityType;
  final String name;
  final String filePath;
  final String language;
  final double score;
  final String? rawCode;

  const SearchResult({
    required this.entityId,
    required this.entityType,
    required this.name,
    required this.filePath,
    required this.language,
    required this.score,
    this.rawCode,
  });

  factory SearchResult.fromJson(Map<String, dynamic> json) => SearchResult(
        entityId: json['entity_id'] as String? ?? '',
        entityType: json['entity_type'] as String? ?? 'unknown',
        name: json['name'] as String? ?? '',
        filePath: json['file_path'] as String? ?? '',
        language: json['language'] as String? ?? '',
        score: (json['score'] as num?)?.toDouble() ?? 0.0,
        rawCode: json['raw_code'] as String?,
      );

  @override
  List<Object?> get props => [
        entityId,
        entityType,
        name,
        filePath,
        language,
        score,
        rawCode,
      ];
}
