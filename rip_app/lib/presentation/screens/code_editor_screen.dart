import 'dart:convert';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:highlight/highlight.dart' show highlight, Node;
import 'package:rip_app/core/design/design.dart';
import 'package:rip_app/core/api/rip_client.dart';
import 'package:rip_app/presentation/providers/connection_provider.dart';

/// Vivid Code Highlighting Themes for Dark Mode
final Map<String, Map<String, TextStyle>> kVividCodeThemes = {
  'Atom One Dark': {
    'root': const TextStyle(color: Color(0xFFABB2BF)),
    'keyword': const TextStyle(color: Color(0xFFC678DD), fontWeight: FontWeight.bold),
    'built_in': const TextStyle(color: Color(0xFFE5C07B)),
    'type': const TextStyle(color: Color(0xFF56B6C2), fontWeight: FontWeight.w600),
    'literal': const TextStyle(color: Color(0xFF56B6C2)),
    'number': const TextStyle(color: Color(0xFFD19A66)),
    'regexp': const TextStyle(color: Color(0xFF98C379)),
    'string': const TextStyle(color: Color(0xFF98C379)),
    'subst': const TextStyle(color: Color(0xFFE06C75)),
    'symbol': const TextStyle(color: Color(0xFF61AFEF)),
    'class': const TextStyle(color: Color(0xFFE5C07B), fontWeight: FontWeight.bold),
    'function': const TextStyle(color: Color(0xFF61AFEF), fontWeight: FontWeight.w600),
    'title': const TextStyle(color: Color(0xFF61AFEF), fontWeight: FontWeight.bold),
    'title.function': const TextStyle(color: Color(0xFF61AFEF), fontWeight: FontWeight.bold),
    'title.class': const TextStyle(color: Color(0xFFE5C07B), fontWeight: FontWeight.bold),
    'params': const TextStyle(color: Color(0xFFABB2BF)),
    'comment': const TextStyle(color: Color(0xFF5C6370), fontStyle: FontStyle.italic),
    'meta': const TextStyle(color: Color(0xFFE06C75)),
    'attr': const TextStyle(color: Color(0xFFD19A66)),
    'attribute': const TextStyle(color: Color(0xFF98C379)),
    'variable': const TextStyle(color: Color(0xFFE06C75)),
    'tag': const TextStyle(color: Color(0xFFE06C75)),
    'operator': const TextStyle(color: Color(0xFF56B6C2)),
    'punctuation': const TextStyle(color: Color(0xFFABB2BF)),
  },
  'VS Code Dark': {
    'root': const TextStyle(color: Color(0xFFD4D4D4)),
    'keyword': const TextStyle(color: Color(0xFF569CD6), fontWeight: FontWeight.bold),
    'built_in': const TextStyle(color: Color(0xFF4EC9B0)),
    'type': const TextStyle(color: Color(0xFF4EC9B0)),
    'literal': const TextStyle(color: Color(0xFF569CD6)),
    'number': const TextStyle(color: Color(0xFFB5CEA8)),
    'string': const TextStyle(color: Color(0xFFCE9178)),
    'symbol': const TextStyle(color: Color(0xFFDCDCAA)),
    'class': const TextStyle(color: Color(0xFF4EC9B0), fontWeight: FontWeight.bold),
    'function': const TextStyle(color: Color(0xFFDCDCAA), fontWeight: FontWeight.w600),
    'title': const TextStyle(color: Color(0xFFDCDCAA), fontWeight: FontWeight.bold),
    'title.function': const TextStyle(color: Color(0xFFDCDCAA), fontWeight: FontWeight.bold),
    'title.class': const TextStyle(color: Color(0xFF4EC9B0), fontWeight: FontWeight.bold),
    'comment': const TextStyle(color: Color(0xFF6A9955), fontStyle: FontStyle.italic),
    'variable': const TextStyle(color: Color(0xFF9CDCFE)),
    'tag': const TextStyle(color: Color(0xFF569CD6)),
    'operator': const TextStyle(color: Color(0xFFD4D4D4)),
  },
  'Dracula': {
    'root': const TextStyle(color: Color(0xFFF8F8F2)),
    'keyword': const TextStyle(color: Color(0xFFFF79C6), fontWeight: FontWeight.bold),
    'built_in': const TextStyle(color: Color(0xFF8BE9FD)),
    'type': const TextStyle(color: Color(0xFF8BE9FD)),
    'literal': const TextStyle(color: Color(0xFFBD93F9)),
    'number': const TextStyle(color: Color(0xFFBD93F9)),
    'string': const TextStyle(color: Color(0xFFF1FA8C)),
    'symbol': const TextStyle(color: Color(0xFF50FA7B)),
    'class': const TextStyle(color: Color(0xFF8BE9FD), fontWeight: FontWeight.bold),
    'function': const TextStyle(color: Color(0xFF50FA7B), fontWeight: FontWeight.w600),
    'title': const TextStyle(color: Color(0xFF50FA7B), fontWeight: FontWeight.bold),
    'title.function': const TextStyle(color: Color(0xFF50FA7B), fontWeight: FontWeight.bold),
    'title.class': const TextStyle(color: Color(0xFF8BE9FD), fontWeight: FontWeight.bold),
    'comment': const TextStyle(color: Color(0xFF6272A4), fontStyle: FontStyle.italic),
    'variable': const TextStyle(color: Color(0xFFF8F8F2)),
    'tag': const TextStyle(color: Color(0xFFFF79C6)),
    'operator': const TextStyle(color: Color(0xFFFF79C6)),
  },
  'Monokai': {
    'root': const TextStyle(color: Color(0xFFF8F8F2)),
    'keyword': const TextStyle(color: Color(0xFFF92672), fontWeight: FontWeight.bold),
    'built_in': const TextStyle(color: Color(0xFF66D9EF)),
    'type': const TextStyle(color: Color(0xFF66D9EF)),
    'literal': const TextStyle(color: Color(0xFFAE81FF)),
    'number': const TextStyle(color: Color(0xFFAE81FF)),
    'string': const TextStyle(color: Color(0xFFE6DB74)),
    'symbol': const TextStyle(color: Color(0xFFA6E22E)),
    'class': const TextStyle(color: Color(0xFFA6E22E), fontWeight: FontWeight.bold),
    'function': const TextStyle(color: Color(0xFFA6E22E), fontWeight: FontWeight.w600),
    'title': const TextStyle(color: Color(0xFFA6E22E), fontWeight: FontWeight.bold),
    'title.function': const TextStyle(color: Color(0xFFA6E22E), fontWeight: FontWeight.bold),
    'title.class': const TextStyle(color: Color(0xFFA6E22E), fontWeight: FontWeight.bold),
    'comment': const TextStyle(color: Color(0xFF75715E), fontStyle: FontStyle.italic),
    'variable': const TextStyle(color: Color(0xFFFD971F)),
    'tag': const TextStyle(color: Color(0xFFF92672)),
    'operator': const TextStyle(color: Color(0xFFF92672)),
  },
  'Cyberpunk': {
    'root': const TextStyle(color: Color(0xFF00FF9F)),
    'keyword': const TextStyle(color: Color(0xFFFF007F), fontWeight: FontWeight.bold),
    'built_in': const TextStyle(color: Color(0xFF00E5FF)),
    'type': const TextStyle(color: Color(0xFF00E5FF)),
    'literal': const TextStyle(color: Color(0xFFFFE600)),
    'number': const TextStyle(color: Color(0xFFFFE600)),
    'string': const TextStyle(color: Color(0xFFFFE600)),
    'symbol': const TextStyle(color: Color(0xFF00FF9F)),
    'class': const TextStyle(color: Color(0xFF00E5FF), fontWeight: FontWeight.bold),
    'function': const TextStyle(color: Color(0xFF00FF9F), fontWeight: FontWeight.w600),
    'title': const TextStyle(color: Color(0xFF00FF9F), fontWeight: FontWeight.bold),
    'title.function': const TextStyle(color: Color(0xFF00FF9F), fontWeight: FontWeight.bold),
    'title.class': const TextStyle(color: Color(0xFF00E5FF), fontWeight: FontWeight.bold),
    'comment': const TextStyle(color: Color(0xFF7B2CBF), fontStyle: FontStyle.italic),
    'variable': const TextStyle(color: Color(0xFF00E5FF)),
    'tag': const TextStyle(color: Color(0xFFFF007F)),
    'operator': const TextStyle(color: Color(0xFFFF007F)),
  },
};

/// High-Performance Robust Custom Highlight Controller
class CustomHighlightCodeController extends TextEditingController {
  String language;
  Map<String, TextStyle> themeStyles;
  String _cachedText = '';
  TextSpan? _cachedSpan;

  CustomHighlightCodeController({
    super.text,
    required this.language,
    required this.themeStyles,
  });

  @override
  TextSpan buildTextSpan({
    required BuildContext context,
    TextStyle? style,
    required bool withComposing,
  }) {
    if (text == _cachedText && _cachedSpan != null) {
      return _cachedSpan!;
    }

    _cachedText = text;
    const defaultColor = Color(0xFFABB2BF);
    final baseStyle = (style ?? const TextStyle()).copyWith(
      fontFamily: 'monospace',
      fontSize: 12.5,
      height: 1.45,
      color: defaultColor,
      backgroundColor: Colors.transparent,
    );

    try {
      final result = highlight.parse(text, language: language.isNotEmpty ? language : null);
      final spans = _convertNodes(result.nodes, baseStyle);
      _cachedSpan = TextSpan(style: baseStyle, children: spans);
      return _cachedSpan!;
    } catch (_) {
      _cachedSpan = TextSpan(style: baseStyle, text: text);
      return _cachedSpan!;
    }
  }

  List<TextSpan> _convertNodes(List<Node>? nodes, TextStyle baseStyle) {
    if (nodes == null || nodes.isEmpty) return [];

    final spans = <TextSpan>[];
    for (final node in nodes) {
      if (node.value != null) {
        final className = node.className;
        TextStyle? nodeStyle;
        if (className != null) {
          nodeStyle = themeStyles[className] ?? _findFallbackStyle(className);
        }
        final merged = nodeStyle != null
            ? baseStyle.merge(nodeStyle).copyWith(backgroundColor: Colors.transparent)
            : baseStyle;
        spans.add(
          TextSpan(
            text: node.value,
            style: merged,
          ),
        );
      } else if (node.children != null) {
        final className = node.className;
        TextStyle? nodeStyle;
        if (className != null) {
          nodeStyle = themeStyles[className] ?? _findFallbackStyle(className);
        }
        final childStyle = nodeStyle != null
            ? baseStyle.merge(nodeStyle).copyWith(backgroundColor: Colors.transparent)
            : baseStyle;
        spans.add(
          TextSpan(
            style: childStyle,
            children: _convertNodes(node.children, childStyle),
          ),
        );
      }
    }
    return spans;
  }

  TextStyle? _findFallbackStyle(String className) {
    if (className.contains('title')) return themeStyles['title'] ?? themeStyles['function'];
    if (className.contains('string')) return themeStyles['string'];
    if (className.contains('keyword')) return themeStyles['keyword'];
    if (className.contains('comment')) return themeStyles['comment'];
    if (className.contains('number')) return themeStyles['number'];
    return themeStyles[className];
  }

  void updateTheme(Map<String, TextStyle> newTheme) {
    themeStyles = newTheme;
    _cachedSpan = null;
    notifyListeners();
  }
}

/// Fullscreen Code Editor Screen
class CodeEditorScreen extends ConsumerStatefulWidget {
  final String projectId;
  final String filePath;
  final String fileName;

  const CodeEditorScreen({
    super.key,
    required this.projectId,
    required this.filePath,
    required this.fileName,
  });

  @override
  ConsumerState<CodeEditorScreen> createState() => _CodeEditorScreenState();
}

class _CodeEditorScreenState extends ConsumerState<CodeEditorScreen> {
  final _scrollController = ScrollController();
  final _horizontalScrollController = ScrollController();
  double _headerT = 0.0;
  late Future<Map<String, dynamic>> _fileFuture;

  TextEditingController? _codeController;
  String _selectedThemeName = 'Atom One Dark';
  int _lineCount = 0;
  bool _isEdited = false;
  bool _isWrapped = false;
  bool _isSaving = false;

  // LLM Code Analysis state
  bool _isAnalyzing = false;
  String? _aiAnalysisText;
  String? _aiSuggestedCode;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_handleScroll);
    _fetchContent();
  }

  @override
  void dispose() {
    _scrollController
      ..removeListener(_handleScroll)
      ..dispose();
    _horizontalScrollController.dispose();
    _codeController?.dispose();
    super.dispose();
  }

  void _handleScroll() {
    if (!_scrollController.hasClients) return;
    final offset = _scrollController.offset;
    final nextHeaderT = (offset / 80).clamp(0.0, 1.0);
    if ((nextHeaderT - _headerT).abs() > 0.02) {
      setState(() => _headerT = nextHeaderT);
    }
  }

  void _fetchContent() {
    _isEdited = false;
    _aiAnalysisText = null;
    _aiSuggestedCode = null;
    _fileFuture = ref.read(ripClientProvider).getFileContent(widget.projectId, widget.filePath);
  }

  void _initCodeController(String initialContent) {
    if (_codeController == null) {
      final lang = _detectLanguage(widget.fileName);
      final theme = kVividCodeThemes[_selectedThemeName] ?? kVividCodeThemes['Atom One Dark']!;

      _codeController = CustomHighlightCodeController(
        text: initialContent,
        language: lang,
        themeStyles: theme,
      );

      _lineCount = initialContent.split('\n').length;

      _codeController!.addListener(() {
        final currentText = _codeController!.text;
        final newLines = currentText.split('\n').length;
        if (newLines != _lineCount || !_isEdited) {
          setState(() {
            _lineCount = newLines;
            _isEdited = true;
          });
        }
      });
    }
  }

  String _detectLanguage(String fileName) {
    final ext = fileName.contains('.') ? fileName.split('.').last.toLowerCase() : '';
    switch (ext) {
      case 'dart':
        return 'dart';
      case 'py':
        return 'python';
      case 'js':
      case 'jsx':
        return 'javascript';
      case 'ts':
      case 'tsx':
        return 'typescript';
      case 'json':
        return 'json';
      case 'yaml':
      case 'yml':
        return 'yaml';
      case 'html':
      case 'xml':
        return 'xml';
      case 'css':
      case 'scss':
        return 'css';
      case 'cpp':
      case 'cxx':
      case 'h':
      case 'hpp':
      case 'c':
        return 'cpp';
      case 'java':
        return 'java';
      case 'go':
        return 'go';
      case 'rs':
        return 'rust';
      case 'md':
        return 'markdown';
      case 'sql':
        return 'sql';
      case 'sh':
      case 'bash':
      case 'zsh':
        return 'bash';
      default:
        return 'plaintext';
    }
  }

  void _switchTheme(String themeName) {
    final theme = kVividCodeThemes[themeName];
    if (theme != null && _codeController is CustomHighlightCodeController) {
      setState(() {
        _selectedThemeName = themeName;
        (_codeController as CustomHighlightCodeController).updateTheme(theme);
      });
      HapticFeedback.selectionClick();
    }
  }

  void _showThemeSelectorModal(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        return Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: const Color(0xFF14141A),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
            border: Border.all(color: Colors.white12),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Code Syntax Color Theme',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close_rounded, size: 20, color: Colors.white70),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: kVividCodeThemes.keys.map((themeName) {
                  final isSelected = themeName == _selectedThemeName;
                  return ChoiceChip(
                    label: Text(themeName),
                    selected: isSelected,
                    selectedColor: const Color(0xFF22C55E).withOpacity(0.25),
                    backgroundColor: Colors.white10,
                    labelStyle: TextStyle(
                      color: isSelected ? const Color(0xFF4ADE80) : Colors.white70,
                      fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                    ),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    onSelected: (_) {
                      _switchTheme(themeName);
                      Navigator.pop(ctx);
                    },
                  );
                }).toList(),
              ),
              const SizedBox(height: 16),
            ],
          ),
        );
      },
    );
  }

  void _copyContentToClipboard() {
    final content = _codeController?.text ?? '';
    if (content.isNotEmpty) {
      Clipboard.setData(ClipboardData(text: content));
      HapticFeedback.mediumImpact();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Copied code to clipboard'),
          duration: Duration(seconds: 2),
          backgroundColor: Color(0xFF22C55E),
        ),
      );
    }
  }

  void _toggleWrap() {
    setState(() {
      _isWrapped = !_isWrapped;
    });
    HapticFeedback.selectionClick();
  }

  /// Perform Dynamic LLM Code Analysis & Refactoring via gateway/api/context API
  Future<void> _runLlmCodeAnalysis(String promptType) async {
    final codeText = _codeController?.text ?? '';
    if (codeText.isEmpty) return;

    setState(() {
      _isAnalyzing = true;
      _aiAnalysisText = null;
      _aiSuggestedCode = null;
    });

    try {
      final String actionHeader = switch (promptType) {
        'refactor' => 'Suggest refactoring, optimizations, and clean code fixes for ${widget.fileName}.',
        'audit' => 'Perform a security and bug audit on ${widget.fileName}.',
        _ => 'Provide an architectural overview and code explanation for ${widget.fileName}.',
      };

      final String sessionId = 'editor_${widget.fileName}_${DateTime.now().millisecondsSinceEpoch}';
      final String taskPrompt = '$actionHeader\n\nFile Path: ${widget.filePath}\n\nCode Content:\n```\n$codeText\n```';

      final result = await ref.read(ripClientProvider).gatewayContext(
        task: taskPrompt,
        sessionId: sessionId,
        projectId: widget.projectId,
        role: 'developer',
      );

      // Extract synthesis / summary / context items from Gateway Context response
      String textResult = '';
      if (result['synthesis'] != null && (result['synthesis'] as String).isNotEmpty) {
        textResult = result['synthesis'];
      } else if (result['summary'] != null && (result['summary'] as String).isNotEmpty) {
        textResult = result['summary'];
      } else if (result['context'] is List && (result['context'] as List).isNotEmpty) {
        final contextItems = result['context'] as List;
        textResult = contextItems.map((c) => (c is Map ? c['content'] : c.toString())).join('\n\n---\n\n');
      } else {
        textResult = 'Gateway analysis completed for ${widget.fileName}.';
      }

      // Extract suggested code blocks if present
      String? extractedCode;
      if (textResult.contains('```')) {
        final parts = textResult.split('```');
        if (parts.length >= 3) {
          final block = parts[1];
          final lines = block.split('\n');
          extractedCode = lines.length > 1 ? lines.sublist(1).join('\n') : block;
        }
      }

      setState(() {
        _isAnalyzing = false;
        _aiAnalysisText = textResult;
        _aiSuggestedCode = extractedCode;
      });
    } catch (e) {
      setState(() {
        _isAnalyzing = false;
        _aiAnalysisText = 'Gateway Context Error: $e\n\nEnsure Gateway Context API is online with active LLM router pool.';
      });
    }
  }

  /// Open LLM Assistant Drawer with Code Insights & Refactoring Actions
  void _openAiAssistantModal(BuildContext context) {
    if (_aiAnalysisText == null && !_isAnalyzing) {
      _runLlmCodeAnalysis('explain');
    }

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return Container(
              height: MediaQuery.of(context).size.height * 0.75,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFF121218),
                borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
                border: Border.all(color: const Color(0xFF8B5CF6).withOpacity(0.3)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Glass Header Pill with AI Sparkle
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              gradient: const LinearGradient(
                                colors: [Color(0xFF8B5CF6), Color(0xFF3B82F6)],
                              ),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: const Icon(Icons.auto_awesome_rounded, color: Colors.white, size: 18),
                          ),
                          const SizedBox(width: 10),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'AI Context Gateway Assistant',
                                style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
                              ),
                              Text(
                                'API: /gateway/api/context (LLM Router Pool)',
                                style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 11),
                              ),
                            ],
                          ),
                        ],
                      ),
                      IconButton(
                        icon: const Icon(Icons.close_rounded, color: Colors.white70, size: 20),
                        onPressed: () => Navigator.pop(ctx),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Action Chips: Explain, Refactor, Audit
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: [
                        ActionChip(
                          avatar: const Icon(Icons.psychology_rounded, size: 16, color: Color(0xFFA7F3D0)),
                          label: const Text('Overview'),
                          backgroundColor: Colors.white10,
                          labelStyle: const TextStyle(color: Colors.white),
                          onPressed: () {
                            setModalState(() => _isAnalyzing = true);
                            _runLlmCodeAnalysis('explain').then((_) => setModalState(() {}));
                          },
                        ),
                        const SizedBox(width: 8),
                        ActionChip(
                          avatar: const Icon(Icons.build_circle_rounded, size: 16, color: Color(0xFFFDE68A)),
                          label: const Text('Suggest Refactor'),
                          backgroundColor: Colors.white10,
                          labelStyle: const TextStyle(color: Colors.white),
                          onPressed: () {
                            setModalState(() => _isAnalyzing = true);
                            _runLlmCodeAnalysis('refactor').then((_) => setModalState(() {}));
                          },
                        ),
                        const SizedBox(width: 8),
                        ActionChip(
                          avatar: const Icon(Icons.security_rounded, size: 16, color: Color(0xFFFCA5A5)),
                          label: const Text('Security Audit'),
                          backgroundColor: Colors.white10,
                          labelStyle: const TextStyle(color: Colors.white),
                          onPressed: () {
                            setModalState(() => _isAnalyzing = true);
                            _runLlmCodeAnalysis('audit').then((_) => setModalState(() {}));
                          },
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Analysis Content Box
                  Expanded(
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: Colors.black26,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(color: Colors.white12),
                      ),
                      child: _isAnalyzing
                          ? const Center(
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF8B5CF6)),
                                  SizedBox(height: 12),
                                  Text(
                                    'Executing Gateway Context LLM Orchestration...',
                                    style: TextStyle(color: Colors.white70, fontSize: 13),
                                  ),
                                ],
                              ),
                            )
                          : SingleChildScrollView(
                              child: Text(
                                _aiAnalysisText ?? 'Tap an action above to analyze code.',
                                style: const TextStyle(
                                  color: Color(0xFFE2E8F0),
                                  fontSize: 13,
                                  height: 1.5,
                                  fontFamily: 'monospace',
                                ),
                              ),
                            ),
                    ),
                  ),

                  // Apply Refactor Button if code suggestions are detected
                  if (_aiSuggestedCode != null && _aiSuggestedCode!.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        icon: const Icon(Icons.auto_fix_high_rounded, size: 18),
                        label: const Text('Apply AI Refactor to Editor'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF8B5CF6),
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        onPressed: () {
                          if (_codeController != null) {
                            setState(() {
                              _codeController!.text = _aiSuggestedCode!;
                              _isEdited = true;
                            });
                            Navigator.pop(ctx);
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text('Applied AI code suggestion to editor!'),
                                backgroundColor: Color(0xFF8B5CF6),
                              ),
                            );
                          }
                        },
                      ),
                    ),
                  ],
                ],
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _handleSaveAndCommit() async {
    if (_codeController == null || !_isEdited) return;

    final commitMsgController = TextEditingController();
    bool saveWithCommit = false;

    await showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF14141A),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: Colors.white12),
        ),
        title: const Text('Save File', style: TextStyle(color: Colors.white)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Optionally enter a commit message to automatically commit these changes to git.',
              style: TextStyle(color: Colors.white70, fontSize: 13),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: commitMsgController,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: 'e.g. update ${widget.fileName}',
                hintStyle: const TextStyle(color: Colors.white38),
                filled: true,
                fillColor: Colors.white10,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel', style: TextStyle(color: Colors.white54)),
          ),
          TextButton(
            onPressed: () {
              saveWithCommit = true;
              Navigator.pop(ctx);
            },
            child: const Text('Save & Commit', style: TextStyle(color: Color(0xFF22C55E), fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );

    if (saveWithCommit) {
      setState(() => _isSaving = true);
      try {
        final content = _codeController!.text;
        final message = commitMsgController.text;
        final res = await ref.read(ripClientProvider).updateFileContent(
          widget.projectId,
          widget.filePath,
          content,
          commitMessage: message.isNotEmpty ? message : 'Update ${widget.fileName}',
        );
        
        setState(() {
          _isEdited = false;
          _isSaving = false;
        });
        
        if (mounted) {
          final commitStatus = res['commit_status'];
          final isSuccess = commitStatus == 'success';
          
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(isSuccess ? 'File saved & committed successfully' : 'Saved! Commit info: $commitStatus'),
              backgroundColor: isSuccess ? const Color(0xFF22C55E) : const Color(0xFFEAB308),
            ),
          );
        }
      } catch (e) {
        setState(() => _isSaving = false);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Failed to save file: $e'),
              backgroundColor: Colors.redAccent,
            ),
          );
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    const bgColor = Color(0xFF09090D);
    const mutedTextColor = Colors.white38;
    final topPadding = MediaQuery.of(context).padding.top;
    final bottomPadding = MediaQuery.of(context).padding.bottom;

    // Force Dark ThemeData across whole widget tree to eliminate light mode white backgrounds
    return Theme(
      data: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: bgColor,
        canvasColor: bgColor,
        dialogBackgroundColor: bgColor,
        cardColor: bgColor,
        colorScheme: const ColorScheme.dark(
          surface: bgColor,
          background: bgColor,
        ),
      ),
      child: Scaffold(
        extendBodyBehindAppBar: true,
        backgroundColor: bgColor,
        body: FutureBuilder<Map<String, dynamic>>(
          future: _fileFuture,
          builder: (context, snapshot) {
            final data = snapshot.data;
            final initialContent = data?['content'] as String? ?? '';
            final fileType = data?['type'] as String? ?? '';

            if (data != null && fileType == 'text') {
              _initCodeController(initialContent);
            }

            final sizeBytes = (data?['size_bytes'] as num?)?.toInt() ?? (_codeController?.text.length ?? initialContent.length);

            Widget codeEditorWidget;
            if (_codeController == null) {
              codeEditorWidget = const SizedBox.shrink();
            } else {
              final textField = Theme(
                data: ThemeData.dark().copyWith(
                  textSelectionTheme: const TextSelectionThemeData(
                    selectionColor: Color(0x40528BFF),
                    selectionHandleColor: Color(0xFF528BFF),
                    cursorColor: Color(0xFF528BFF),
                  ),
                ),
                child: TextField(
                  controller: _codeController,
                  maxLines: null,
                  keyboardType: TextInputType.multiline,
                  enableSuggestions: false,
                  autocorrect: false,
                  cursorColor: const Color(0xFF528BFF),
                  cursorWidth: 2,
                  style: const TextStyle(
                    fontSize: 12.5,
                    fontFamily: 'monospace',
                    height: 1.45,
                    color: Color(0xFFABB2BF),
                    backgroundColor: Colors.transparent,
                  ),
                  decoration: const InputDecoration(
                    isDense: true,
                    contentPadding: EdgeInsets.zero,
                    border: InputBorder.none,
                    focusedBorder: InputBorder.none,
                    enabledBorder: InputBorder.none,
                    fillColor: Colors.transparent,
                    filled: false,
                  ),
                ),
              );

              if (_isWrapped) {
                // Wrapped Mode: No horizontal scroll, no line numbers
                codeEditorWidget = Padding(
                  padding: const EdgeInsets.only(left: 4),
                  child: textField,
                );
              } else {
                // Default Mode: Horizontal Scroll, showing line numbers
                codeEditorWidget = SingleChildScrollView(
                  controller: _horizontalScrollController,
                  scrollDirection: Axis.horizontal,
                  physics: const BouncingScrollPhysics(),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Compact Right-Aligned Line Numbers
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: List.generate(_lineCount, (index) {
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 2),
                            child: Text(
                              '${index + 1}',
                              style: TextStyle(
                                color: mutedTextColor.withOpacity(0.35),
                                fontSize: 12.5,
                                fontFamily: 'monospace',
                                height: 1.45,
                              ),
                            ),
                          );
                        }),
                      ),
                      const SizedBox(width: 8),
                      IntrinsicWidth(child: textField),
                    ],
                  ),
                );
              }
            }

            return Stack(
              children: [
                // 1. Background Base Color (Enforced Dark `#09090D`)
                const ColoredBox(color: bgColor),

                // 2. Pure Edge-to-Edge Compact Highlighting Code Viewport
                if (snapshot.connectionState == ConnectionState.waiting)
                  Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.grey),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Parsing code AST & language tokens...',
                          style: TextStyle(color: mutedTextColor, fontSize: 13),
                        ),
                      ],
                    ),
                  )
                else if (snapshot.hasError || !snapshot.hasData)
                  Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.error_outline_rounded, color: Colors.redAccent, size: 40),
                          const SizedBox(height: 12),
                          const Text(
                            'Failed to read workspace file',
                            style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            '${snapshot.error ?? "File path not accessible"}',
                            textAlign: TextAlign.center,
                            style: const TextStyle(color: mutedTextColor, fontSize: 12),
                          ),
                          const SizedBox(height: 16),
                          OutlinedButton.icon(
                            onPressed: () => setState(() => _fetchContent()),
                            icon: const Icon(Icons.refresh_rounded, size: 16),
                            label: const Text('Retry Scan'),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: Colors.white,
                              side: const BorderSide(color: Colors.white24),
                            ),
                          ),
                        ],
                      ),
                    ),
                  )
                else if (fileType == 'image' && data?['content_base64'] != null)
                  Center(
                    child: Padding(
                      padding: EdgeInsets.fromLTRB(12, topPadding + 90, 12, bottomPadding + 30),
                      child: InteractiveViewer(
                        minScale: 0.5,
                        maxScale: 4.0,
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(12),
                          child: Image.memory(
                            base64.decode(data!['content_base64']),
                            fit: BoxFit.contain,
                            errorBuilder: (_, __, ___) => const Center(
                              child: Text('Unable to render image preview', style: TextStyle(color: mutedTextColor)),
                            ),
                          ),
                        ),
                      ),
                    ),
                  )
                else if (fileType == 'binary')
                  Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.inventory_2_outlined, size: 52, color: mutedTextColor),
                        const SizedBox(height: 16),
                        Text(
                          'Binary File (${data?['extension'] ?? ""})',
                          style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Size: ${_formatBytes(sizeBytes)}',
                          style: const TextStyle(color: mutedTextColor, fontSize: 13, fontFamily: 'monospace'),
                        ),
                      ],
                    ),
                  )
                else
                  // CLEAN NATIVE COMPACT HIGHLIGHTING TEXTFIELD CANVAS
                  SingleChildScrollView(
                    controller: _scrollController,
                    physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
                    padding: EdgeInsets.fromLTRB(
                      8,
                      topPadding + 92,
                      8,
                      bottomPadding + 40,
                    ),
                    child: codeEditorWidget,
                  ),

                // 3. TOP FADE GRADIENT OVERLAY
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  height: topPadding + 105,
                  child: IgnorePointer(
                    child: Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          colors: [
                            bgColor,
                            bgColor.withValues(alpha: 0.85),
                            bgColor.withValues(alpha: 0.0),
                          ],
                          stops: const [0.0, 0.60, 1.0],
                        ),
                      ),
                    ),
                  ),
                ),

                // 4. BOTTOM FADE GRADIENT OVERLAY
                Positioned(
                  bottom: 0,
                  left: 0,
                  right: 0,
                  height: bottomPadding + 50,
                  child: IgnorePointer(
                    child: Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.bottomCenter,
                          end: Alignment.topCenter,
                          colors: [
                            bgColor,
                            bgColor.withValues(alpha: 0.85),
                            bgColor.withValues(alpha: 0.0),
                          ],
                          stops: const [0.0, 0.60, 1.0],
                        ),
                      ),
                    ),
                  ),
                ),

                // 5. MAIN TOP FLOATING GLASSBAR (Back, Expanded Filename Pill, AI Assistant & Actions Pill)
                _CodeEditorGlassHeader(
                  progress: _headerT,
                  fileName: widget.fileName,
                  language: _detectLanguage(widget.fileName),
                  themeName: _selectedThemeName,
                  isEdited: _isEdited,
                  isWrapped: _isWrapped,
                  isSaving: _isSaving,
                  onBackTap: () {
                    HapticFeedback.selectionClick();
                    Navigator.of(context).pop();
                  },
                  onThemeTap: () => _showThemeSelectorModal(context),
                  onCopyTap: _copyContentToClipboard,
                  onReloadTap: () {
                    HapticFeedback.selectionClick();
                    _codeController = null;
                    setState(() => _fetchContent());
                  },
                  onWrapTap: _toggleWrap,
                  onSaveTap: _isEdited && !_isSaving ? _handleSaveAndCommit : null,
                  onAiAssistantTap: () => _openAiAssistantModal(context),
                ),

                // 6. SEPARATE FLOATING GLASS COMPONENT UNDER COPY/RELOAD BUTTON (LOC & File Size Metrics)
                if (_lineCount > 0)
                  Positioned(
                    top: topPadding + 56,
                    right: 10,
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: BackdropFilter(
                        filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: const Color(0xFF181820).withValues(alpha: 0.85 + (_headerT * 0.10)),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: Colors.white12),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Container(
                                width: 6,
                                height: 6,
                                decoration: BoxDecoration(
                                  color: _isEdited ? const Color(0xFFEAB308) : const Color(0xFF22C55E),
                                  shape: BoxShape.circle,
                                ),
                              ),
                              const SizedBox(width: 6),
                              Text(
                                '${_isWrapped ? 'WRAPPED' : '$_lineCount LOC'} • ${_formatBytes(sizeBytes)}',
                                style: const TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.white70,
                                  fontFamily: 'monospace',
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }

  String _formatBytes(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
}

/// Floating Glassmorphic Top Header with Actions (AI Sparkle, Wrap, Save/Theme, Copy)
class _CodeEditorGlassHeader extends StatelessWidget {
  const _CodeEditorGlassHeader({
    required this.progress,
    required this.fileName,
    required this.language,
    required this.themeName,
    required this.isEdited,
    required this.isWrapped,
    required this.isSaving,
    required this.onBackTap,
    required this.onThemeTap,
    required this.onCopyTap,
    required this.onReloadTap,
    required this.onWrapTap,
    required this.onSaveTap,
    required this.onAiAssistantTap,
  });

  final double progress;
  final String fileName;
  final String language;
  final String themeName;
  final bool isEdited;
  final bool isWrapped;
  final bool isSaving;
  final VoidCallback onBackTap;
  final VoidCallback onThemeTap;
  final VoidCallback onCopyTap;
  final VoidCallback onReloadTap;
  final VoidCallback onWrapTap;
  final VoidCallback? onSaveTap;
  final VoidCallback onAiAssistantTap;

  @override
  Widget build(BuildContext context) {
    final topPadding = MediaQuery.of(context).padding.top;
    final glassColor = const Color(0xFF181820).withValues(alpha: 0.85 + (progress * 0.10));
    const border = Border.fromBorderSide(BorderSide(color: Colors.white12));

    return Positioned(
      top: topPadding + 6,
      left: 10,
      right: 10,
      child: Row(
        children: [
          // 1. Back Arrow Glass Pill (Fixed Width 44px)
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
              child: Container(
                height: 44,
                width: 44,
                decoration: BoxDecoration(
                  color: glassColor,
                  borderRadius: BorderRadius.circular(16),
                  border: border,
                ),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: onBackTap,
                    borderRadius: BorderRadius.circular(16),
                    child: const Center(
                      child: Icon(
                        Icons.arrow_back_rounded,
                        size: 20,
                        color: Colors.white70,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 6),

          // 2. Expanded Glass Pill (Absorbs available space seamlessly)
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
                child: Container(
                  height: 44,
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  decoration: BoxDecoration(
                    color: glassColor,
                    borderRadius: BorderRadius.circular(16),
                    border: border,
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 7,
                        height: 7,
                        decoration: BoxDecoration(
                          color: isEdited ? const Color(0xFFEAB308) : const Color(0xFF22C55E),
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          fileName,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 6),

          // 3. Actions Glass Pill (AI Assistant Sparkle, Wrap, Save/Theme, Copy)
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
              child: Container(
                height: 44,
                padding: const EdgeInsets.symmetric(horizontal: 2),
                decoration: BoxDecoration(
                  color: glassColor,
                  borderRadius: BorderRadius.circular(16),
                  border: border,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // AI Assistant Button with Purple/Blue Sparkle
                    IconButton(
                      icon: const Icon(Icons.auto_awesome_rounded, size: 18, color: Color(0xFFA78BFA)),
                      onPressed: onAiAssistantTap,
                      tooltip: 'AI Code Assistant & Suggestions',
                    ),
                    IconButton(
                      icon: Icon(
                        isWrapped ? Icons.wrap_text_rounded : Icons.subject_rounded,
                        size: 18,
                        color: isWrapped ? const Color(0xFF61AFEF) : Colors.white70,
                      ),
                      onPressed: onWrapTap,
                      tooltip: 'Toggle Word Wrap',
                    ),
                    if (isEdited)
                      IconButton(
                        icon: isSaving 
                            ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF22C55E)))
                            : const Icon(Icons.save_rounded, size: 18, color: Color(0xFF22C55E)),
                        onPressed: onSaveTap,
                        tooltip: 'Save & Commit',
                      )
                    else
                      IconButton(
                        icon: const Icon(Icons.palette_rounded, size: 18, color: Colors.white70),
                        onPressed: onThemeTap,
                        tooltip: 'Change Theme',
                      ),
                    IconButton(
                      icon: const Icon(Icons.copy_rounded, size: 18, color: Colors.white70),
                      onPressed: onCopyTap,
                      tooltip: 'Copy Code',
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
