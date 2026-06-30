import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/design/app_colors.dart';
import '../common/section_card.dart';

class MermaidBlock extends StatefulWidget {
  final String title;
  final String? subtitle;
  final String diagramCode;

  const MermaidBlock({
    super.key,
    required this.title,
    this.subtitle,
    required this.diagramCode,
  });

  @override
  State<MermaidBlock> createState() => _MermaidBlockState();
}

class _MermaidBlockState extends State<MermaidBlock> {
  final TransformationController _controller = TransformationController();
  late _MermaidGraph _graph;

  @override
  void initState() {
    super.initState();
    _graph = _MermaidGraph.parse(widget.diagramCode);
  }

  @override
  void didUpdateWidget(covariant MermaidBlock oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.diagramCode != widget.diagramCode) {
      _graph = _MermaidGraph.parse(widget.diagramCode);
      _controller.value = Matrix4.identity();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      icon: Icons.account_tree_rounded,
      iconColor: AppColors.iconMermaid,
      title: widget.title,
      subtitle: widget.subtitle ?? 'Interactive architecture graph',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            height: 330,
            clipBehavior: Clip.antiAlias,
            decoration: BoxDecoration(
              color: AppColors.surfaceVariant,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.border),
            ),
            child: _graph.nodes.isEmpty
                ? _MermaidFallback(
                    diagramCode: widget.diagramCode,
                    onSource: _showSource,
                  )
                : Stack(
                    children: [
                      GestureDetector(
                        behavior: HitTestBehavior.opaque,
                        onTapUp: _handleTap,
                        child: InteractiveViewer(
                          transformationController: _controller,
                          minScale: 0.55,
                          maxScale: 2.8,
                          boundaryMargin: const EdgeInsets.all(240),
                          child: CustomPaint(
                            size: _graph.canvasSize,
                            painter: _MermaidGraphPainter(_graph),
                          ),
                        ),
                      ),
                      Positioned(
                        right: 10,
                        top: 10,
                        child: _DiagramToolbar(
                          onZoomIn: () => _scaleBy(1.18),
                          onZoomOut: () => _scaleBy(0.84),
                          onReset: () => _controller.value = Matrix4.identity(),
                          onSource: _showSource,
                        ),
                      ),
                      Positioned(
                        left: 12,
                        bottom: 10,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            color: Colors.black.withValues(alpha: 0.42),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                            child: Text(
                              'Pan, zoom, tap symbols',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  void _handleTap(TapUpDetails details) {
    final scenePoint = _controller.toScene(details.localPosition);
    for (final node in _graph.nodes.reversed) {
      if (node.rect.contains(scenePoint)) {
        _showSymbol(node);
        return;
      }
    }
  }

  void _scaleBy(double factor) {
    final next = _controller.value.clone()..scale(factor);
    _controller.value = next;
  }

  void _showSymbol(_MermaidNode node) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      builder: (context) {
        final outgoing = _graph.edges
            .where((edge) => edge.from == node.id)
            .map((edge) => edge.toLabel)
            .toList();
        final incoming = _graph.edges
            .where((edge) => edge.to == node.id)
            .map((edge) => edge.fromLabel)
            .toList();
        return Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                node.label,
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                '${incoming.length} incoming · ${outgoing.length} outgoing relationships',
                style: const TextStyle(color: AppColors.textSecondary),
              ),
              const SizedBox(height: 14),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _SymbolChip(label: 'Trace ${node.label}'),
                  _SymbolChip(label: 'Impact ${node.label}'),
                  _SymbolChip(label: 'Dependencies ${node.label}'),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  void _showSource() {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      isScrollControlled: true,
      builder: (context) {
        return DraggableScrollableSheet(
          expand: false,
          initialChildSize: 0.55,
          minChildSize: 0.28,
          maxChildSize: 0.9,
          builder: (context, controller) {
            return Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      const Expanded(
                        child: Text(
                          'Mermaid source',
                          style: TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 16,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ),
                      TextButton.icon(
                        onPressed: () {
                          Clipboard.setData(ClipboardData(text: widget.diagramCode));
                          Navigator.pop(context);
                        },
                        icon: const Icon(Icons.copy_rounded, size: 16),
                        label: const Text('Copy'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Expanded(
                    child: SingleChildScrollView(
                      controller: controller,
                      child: SelectableText(
                        widget.diagramCode,
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontFamily: 'monospace',
                          fontSize: 12,
                          height: 1.45,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}

class _DiagramToolbar extends StatelessWidget {
  const _DiagramToolbar({
    required this.onZoomIn,
    required this.onZoomOut,
    required this.onReset,
    required this.onSource,
  });

  final VoidCallback onZoomIn;
  final VoidCallback onZoomOut;
  final VoidCallback onReset;
  final VoidCallback onSource;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.surface.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _ToolIcon(icon: Icons.add_rounded, onTap: onZoomIn),
          _ToolIcon(icon: Icons.remove_rounded, onTap: onZoomOut),
          _ToolIcon(icon: Icons.center_focus_strong_rounded, onTap: onReset),
          _ToolIcon(icon: Icons.code_rounded, onTap: onSource),
        ],
      ),
    );
  }
}

class _ToolIcon extends StatelessWidget {
  const _ToolIcon({required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: SizedBox(
        width: 36,
        height: 36,
        child: Icon(icon, color: AppColors.textSecondary, size: 18),
      ),
    );
  }
}

class _MermaidFallback extends StatelessWidget {
  const _MermaidFallback({required this.diagramCode, required this.onSource});

  final String diagramCode;
  final VoidCallback onSource;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.schema_rounded, color: AppColors.iconMermaid, size: 34),
          const SizedBox(height: 10),
          const Text(
            'Diagram could not be rendered',
            style: TextStyle(
              color: AppColors.textPrimary,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          TextButton.icon(
            onPressed: onSource,
            icon: const Icon(Icons.code_rounded),
            label: const Text('Open source'),
          ),
        ],
      ),
    );
  }
}

class _SymbolChip extends StatelessWidget {
  const _SymbolChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return ActionChip(
      label: Text(label),
      onPressed: () {
        Clipboard.setData(ClipboardData(text: label));
        Navigator.pop(context);
      },
    );
  }
}

class _MermaidGraph {
  _MermaidGraph({required this.nodes, required this.edges, required this.canvasSize});

  final List<_MermaidNode> nodes;
  final List<_MermaidEdge> edges;
  final Size canvasSize;

  static _MermaidGraph parse(String source) {
    final nodesById = <String, _MermaidNode>{};
    final edges = <_MermaidEdge>[];
    final edgeRegex = RegExp(r'(.+?)\s*(?:-->|---|-.->)\s*(?:\|([^|]+)\|)?\s*(.+)');

    for (final rawLine in source.split('\n')) {
      final line = rawLine.trim();
      if (line.isEmpty ||
          line.startsWith('graph ') ||
          line.startsWith('flowchart ') ||
          line.startsWith('sequenceDiagram') ||
          line.startsWith('```')) {
        continue;
      }
      final match = edgeRegex.firstMatch(line);
      if (match == null) continue;

      final from = _parseNodeToken(match.group(1) ?? '');
      final to = _parseNodeToken(match.group(3) ?? '');
      if (from.id.isEmpty || to.id.isEmpty) continue;
      nodesById.putIfAbsent(from.id, () => from);
      nodesById.putIfAbsent(to.id, () => to);
      edges.add(_MermaidEdge(
        from: from.id,
        to: to.id,
        fromLabel: from.label,
        toLabel: to.label,
        label: (match.group(2) ?? '').trim(),
      ));
    }

    final nodes = nodesById.values.toList();
    _layout(nodes, edges);
    return _MermaidGraph(
      nodes: nodes,
      edges: edges,
      canvasSize: _canvasSize(nodes),
    );
  }

  static _MermaidNode _parseNodeToken(String token) {
    final cleaned = token.trim().replaceAll(';', '');
    final idMatch = RegExp(r'^([A-Za-z0-9_./:-]+)').firstMatch(cleaned);
    final id = idMatch?.group(1) ?? '';
    var label = id;
    final labelMatch = RegExp(r'[\[\(\{]"?([^"\]\)\}]+)"?[\]\)\}]').firstMatch(cleaned);
    if (labelMatch != null) label = labelMatch.group(1)?.trim() ?? id;
    return _MermaidNode(id: id, label: label);
  }

  static void _layout(List<_MermaidNode> nodes, List<_MermaidEdge> edges) {
    final indegree = {for (final node in nodes) node.id: 0};
    for (final edge in edges) {
      indegree[edge.to] = (indegree[edge.to] ?? 0) + 1;
    }

    final level = <String, int>{};
    final queue = nodes.where((node) => (indegree[node.id] ?? 0) == 0).toList();
    for (final node in queue) {
      level[node.id] = 0;
    }

    var guard = 0;
    while (queue.isNotEmpty && guard < 1000) {
      guard++;
      final node = queue.removeAt(0);
      final current = level[node.id] ?? 0;
      for (final edge in edges.where((edge) => edge.from == node.id)) {
        level[edge.to] = math.max(level[edge.to] ?? 0, current + 1);
        queue.add(nodes.firstWhere((item) => item.id == edge.to));
      }
    }

    final byLevel = <int, List<_MermaidNode>>{};
    for (var i = 0; i < nodes.length; i++) {
      final node = nodes[i];
      final nodeLevel = level[node.id] ?? i ~/ 3;
      byLevel.putIfAbsent(nodeLevel, () => []).add(node);
    }

    const nodeWidth = 172.0;
    const nodeHeight = 58.0;
    const xGap = 94.0;
    const yGap = 34.0;
    byLevel.forEach((nodeLevel, levelNodes) {
      for (var i = 0; i < levelNodes.length; i++) {
        final node = levelNodes[i];
        node.rect = Rect.fromLTWH(
          42 + nodeLevel * (nodeWidth + xGap),
          42 + i * (nodeHeight + yGap),
          nodeWidth,
          nodeHeight,
        );
      }
    });
  }

  static Size _canvasSize(List<_MermaidNode> nodes) {
    if (nodes.isEmpty) return const Size(780, 320);
    final maxRight = nodes.map((node) => node.rect.right).reduce(math.max);
    final maxBottom = nodes.map((node) => node.rect.bottom).reduce(math.max);
    return Size(math.max(780, maxRight + 70), math.max(320, maxBottom + 70));
  }
}

class _MermaidNode {
  _MermaidNode({required this.id, required this.label});

  final String id;
  final String label;
  Rect rect = Rect.zero;
}

class _MermaidEdge {
  _MermaidEdge({
    required this.from,
    required this.to,
    required this.fromLabel,
    required this.toLabel,
    required this.label,
  });

  final String from;
  final String to;
  final String fromLabel;
  final String toLabel;
  final String label;
}

class _MermaidGraphPainter extends CustomPainter {
  _MermaidGraphPainter(this.graph);

  final _MermaidGraph graph;

  @override
  void paint(Canvas canvas, Size size) {
    final edgePaint = Paint()
      ..color = AppColors.iconMermaid.withValues(alpha: 0.58)
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;
    final nodePaint = Paint()..color = AppColors.surface;
    final borderPaint = Paint()
      ..color = AppColors.iconMermaid.withValues(alpha: 0.72)
      ..strokeWidth = 1.3
      ..style = PaintingStyle.stroke;

    for (final edge in graph.edges) {
      final from = graph.nodes.firstWhere((node) => node.id == edge.from);
      final to = graph.nodes.firstWhere((node) => node.id == edge.to);
      final start = Offset(from.rect.right, from.rect.center.dy);
      final end = Offset(to.rect.left, to.rect.center.dy);
      final controlDx = math.max(36.0, (end.dx - start.dx).abs() * 0.42);
      final path = Path()
        ..moveTo(start.dx, start.dy)
        ..cubicTo(
          start.dx + controlDx,
          start.dy,
          end.dx - controlDx,
          end.dy,
          end.dx,
          end.dy,
        );
      canvas.drawPath(path, edgePaint);
      _drawArrow(canvas, end, edgePaint.color);
    }

    for (final node in graph.nodes) {
      final rrect = RRect.fromRectAndRadius(node.rect, const Radius.circular(16));
      canvas.drawRRect(rrect, nodePaint);
      canvas.drawRRect(rrect, borderPaint);
      _drawText(canvas, node.label, node.rect);
    }
  }

  void _drawArrow(Canvas canvas, Offset tip, Color color) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.fill;
    final path = Path()
      ..moveTo(tip.dx, tip.dy)
      ..lineTo(tip.dx - 9, tip.dy - 5)
      ..lineTo(tip.dx - 9, tip.dy + 5)
      ..close();
    canvas.drawPath(path, paint);
  }

  void _drawText(Canvas canvas, String text, Rect rect) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: const TextStyle(
          color: AppColors.textPrimary,
          fontSize: 12,
          fontWeight: FontWeight.w800,
        ),
      ),
      maxLines: 2,
      ellipsis: '...',
      textAlign: TextAlign.center,
      textDirection: TextDirection.ltr,
    )..layout(maxWidth: rect.width - 22);
    painter.paint(
      canvas,
      Offset(
        rect.left + (rect.width - painter.width) / 2,
        rect.top + (rect.height - painter.height) / 2,
      ),
    );
  }

  @override
  bool shouldRepaint(covariant _MermaidGraphPainter oldDelegate) {
    return oldDelegate.graph != graph;
  }
}
