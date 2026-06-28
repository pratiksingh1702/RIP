class MarkdownParser {
  static String extractFirstCodeBlock(String markdown) {
    final RegExp codeBlockRegex = RegExp(r'```[\s\S]*?```');
    final match = codeBlockRegex.firstMatch(markdown);
    if (match != null) {
      return match.group(0)!;
    }
    return '';
  }

  static String extractPlainText(String markdown) {
    // Remove code blocks first
    String text = markdown.replaceAll(RegExp(r'```[\s\S]*?```'), '');
    // Remove headers, links, etc.
    text = text.replaceAll(RegExp(r'#+ '), '');
    text = text.replaceAll(RegExp(r'\[([^\]]+)\]\([^)]+\)'), r'$1');
    return text.trim();
  }
}
