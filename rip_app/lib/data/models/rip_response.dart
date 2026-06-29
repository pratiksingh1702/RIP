enum BlockType {
  text,
  workflowTree,
  mermaid,
  table,
  code,
  fileList,
  impact,
  suggestionChips,
}

enum ImpactSeverity {
  high,
  medium,
  low,
}

class RipResponseBlock {
  final BlockType type;
  final String? title;
  final String? subtitle;
  final String? textContent; // text, mermaid, code
  final List<String>? listContent; // tree nodes, files, chip labels
  final List<String>? tableHeaders;
  final List<List<String>>? tableRows;
  final int? count;
  final String? language; // for code
  final ImpactSeverity? severity; // for impact

  const RipResponseBlock({
    required this.type,
    this.title,
    this.subtitle,
    this.textContent,
    this.listContent,
    this.tableHeaders,
    this.tableRows,
    this.count,
    this.language,
    this.severity,
  });

  Map<String, dynamic> toJson() => {
        'type': type.name,
        'title': title,
        'subtitle': subtitle,
        'textContent': textContent,
        'listContent': listContent,
        'tableHeaders': tableHeaders,
        'tableRows': tableRows,
        'count': count,
        'language': language,
        'severity': severity?.name,
      };

  factory RipResponseBlock.fromJson(Map<String, dynamic> json) => RipResponseBlock(
        type: BlockType.values.firstWhere((e) => e.name == json['type']),
        title: json['title'] as String?,
        subtitle: json['subtitle'] as String?,
        textContent: json['textContent'] as String?,
        listContent: (json['listContent'] as List<dynamic>?)?.map((e) => e as String).toList(),
        tableHeaders: (json['tableHeaders'] as List<dynamic>?)?.map((e) => e as String).toList(),
        tableRows: (json['tableRows'] as List<dynamic>?)
            ?.map((r) => (r as List<dynamic>).map((e) => e as String).toList())
            .toList(),
        count: json['count'] as int?,
        language: json['language'] as String?,
        severity: json['severity'] != null
            ? ImpactSeverity.values.firstWhere((e) => e.name == json['severity'])
            : null,
      );
}
