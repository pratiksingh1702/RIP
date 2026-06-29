import '../data/models/rip_response.dart';

class ResponseParser {
  static List<RipResponseBlock> parse(String text, {String? commandSymbol}) {
    final List<_ParsedChunk> chunks = [];

    // 1. Find Mermaid diagrams
    final mermaidRegex = RegExp(r'```mermaid\s*\n([\s\S]*?)```');
    for (final match in mermaidRegex.allMatches(text)) {
      chunks.add(_ParsedChunk(
        startIndex: match.start,
        endIndex: match.end,
        block: RipResponseBlock(
          type: BlockType.mermaid,
          title: 'Mermaid Diagram',
          subtitle: 'Visual representation of the flow',
          textContent: match.group(1)?.trim(),
        ),
      ));
    }

    // 2. Find general code blocks (excluding mermaid)
    final codeRegex = RegExp(r'```(\w*)\s*\n([\s\S]*?)```');
    for (final match in codeRegex.allMatches(text)) {
      final lang = match.group(1)?.trim() ?? 'text';
      if (lang.toLowerCase() == 'mermaid') continue;
      chunks.add(_ParsedChunk(
        startIndex: match.start,
        endIndex: match.end,
        block: RipResponseBlock(
          type: BlockType.code,
          title: 'Code Block',
          subtitle: lang.isNotEmpty ? '$lang source' : null,
          textContent: match.group(2)?.trim(),
          language: lang,
        ),
      ));
    }

    // 3. Find Markdown Tables
    final tableRegex = RegExp(
      r'((?:^|\n)\|[^\n]+\|\n\|[ :|-]+\|\n(?:\|[^\n]+\|(?:\n|$))*)',
      multiLine: true,
    );
    for (final match in tableRegex.allMatches(text)) {
      final tableStr = match.group(1)?.trim() ?? '';
      if (tableStr.isEmpty) continue;
      
      // Parse table headers and rows
      final lines = tableStr.split('\n').map((l) => l.trim()).where((l) => l.startsWith('|')).toList();
      if (lines.length >= 3) {
        final headers = lines[0].split('|').map((s) => s.trim()).where((s) => s.isNotEmpty).toList();
        final rows = lines.skip(2).map((line) {
          return line.split('|').map((s) => s.trim()).where((s) => s.isNotEmpty).toList();
        }).toList();

        chunks.add(_ParsedChunk(
          startIndex: match.start,
          endIndex: match.end,
          block: RipResponseBlock(
            type: BlockType.table,
            title: 'Data Table',
            tableHeaders: headers,
            tableRows: rows,
          ),
        ));
      }
    }

    // Now we need to handle the remaining regions (non-overlapping text regions)
    // Let's sort the chunks by startIndex
    chunks.sort((a, b) => a.startIndex.compareTo(b.startIndex));

    // Fill in the text regions in between chunks
    final List<RipResponseBlock> finalBlocks = [];
    int lastIndex = 0;

    for (final chunk in chunks) {
      if (chunk.startIndex > lastIndex) {
        final remainingText = text.substring(lastIndex, chunk.startIndex);
        finalBlocks.addAll(_parseTextRegion(remainingText, commandSymbol));
      }
      finalBlocks.add(chunk.block);
      lastIndex = chunk.endIndex;
    }

    if (lastIndex < text.length) {
      final remainingText = text.substring(lastIndex);
      finalBlocks.addAll(_parseTextRegion(remainingText, commandSymbol));
    }

    // Post-processing: if any follow-up chips can be inferred or suggestions are needed, we can append them
    final suggestionChips = _extractSuggestionChips(text);
    if (suggestionChips.isNotEmpty) {
      finalBlocks.add(RipResponseBlock(
        type: BlockType.suggestionChips,
        listContent: suggestionChips,
      ));
    }

    return finalBlocks;
  }

  static List<RipResponseBlock> _parseTextRegion(String text, String? symbol) {
    final List<RipResponseBlock> blocks = [];
    final lines = text.split('\n');

    final List<String> currentTextLines = [];
    final List<String> filePaths = [];
    
    // For detecting workflow tree or impact
    String? workflowChain;
    ImpactSeverity? severity;

    final fileRegex = RegExp(
      r'^\s*[-*•]\s+([\w./\\-]+\.(?:py|ts|tsx|js|jsx|dart|java|go|rs|md|toml|yaml|yml|json))',
      caseSensitive: false,
    );

    for (final line in lines) {
      final trimmed = line.trim();
      if (trimmed.isEmpty) {
        if (currentTextLines.isNotEmpty) {
          currentTextLines.add('');
        }
        continue;
      }

      // Check if it's a file reference
      final fileMatch = fileRegex.firstMatch(line);
      if (fileMatch != null) {
        filePaths.add(fileMatch.group(1)!);
        continue;
      }

      // Check if it's a workflow chain
      if (trimmed.contains('→') || trimmed.contains('->')) {
        workflowChain = trimmed;
        continue;
      }

      // Check if it specifies impact severity
      final severityMatch = RegExp(r'(?:severity|risk)[:\s]+(high|medium|low)', caseSensitive: false).firstMatch(trimmed);
      if (severityMatch != null) {
        final sev = severityMatch.group(1)!.toLowerCase();
        severity = sev == 'high' ? ImpactSeverity.high
            : sev == 'medium' ? ImpactSeverity.medium
            : ImpactSeverity.low;
        continue;
      }

      // Default text line
      currentTextLines.add(line);
    }

    // Flush text block
    final textContent = currentTextLines.join('\n').trim();
    if (textContent.isNotEmpty) {
      blocks.add(RipResponseBlock(
        type: BlockType.text,
        textContent: textContent,
      ));
    }

    // Flush workflow tree block
    if (workflowChain != null) {
      final nodes = workflowChain
          .split(RegExp(r'→|->'))
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty)
          .toList();
      blocks.add(RipResponseBlock(
        type: BlockType.workflowTree,
        title: 'Workflow Tree',
        subtitle: workflowChain,
        listContent: nodes,
        count: nodes.length,
      ));
    }

    // Flush file list block
    if (filePaths.isNotEmpty) {
      blocks.add(RipResponseBlock(
        type: BlockType.fileList,
        title: 'Important Files',
        subtitle: 'Key files involved in ${symbol ?? "this flow"}',
        listContent: filePaths,
        count: filePaths.length,
      ));
    }

    // Flush impact block
    if (severity != null) {
      blocks.add(RipResponseBlock(
        type: BlockType.impact,
        title: 'Impact Analysis',
        subtitle: 'What will be affected if this changes',
        severity: severity,
      ));
    }

    return blocks;
  }

  static List<String> _extractSuggestionChips(String text) {
    return ['Show state flow', 'Show impact', 'Show consumers', 'Find similar'];
  }
}

class _ParsedChunk {
  final int startIndex;
  final int endIndex;
  final RipResponseBlock block;

  _ParsedChunk({
    required this.startIndex,
    required this.endIndex,
    required this.block,
  });
}
